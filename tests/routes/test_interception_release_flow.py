import app.routes.interception as route
import pytest
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default as default_policy
from types import SimpleNamespace
from app.utils.crypto import encrypt_credential
from app.utils.db import get_db
from tests.routes.test_interception_additional import _login


class ReleaseIMAP:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.current_folder = None
        self.appended = False
        self.mailboxes = {
            "INBOX": {},
            "Quarantine": {},
            "[Gmail]/Trash": {}
        }
        self.deleted_uids = []
        self.gmail_operations = []  # Track Gmail-specific operations
        # Simulate Gmail capabilities (MOVE, UIDPLUS, X-GM-EXT-1 for Gmail extensions)
        self.capabilities = ('IMAP4REV1', 'MOVE', 'UIDPLUS', 'IDLE', 'X-GM-EXT-1')

    def capability(self):
        """Return IMAP capabilities including Gmail extensions."""
        caps = b' '.join(cap.encode() if isinstance(cap, str) else cap for cap in self.capabilities)
        return "OK", [caps]

    def preload(self, folder, uid, message_id):
        self.mailboxes.setdefault(folder, {})[uid] = message_id

    def login(self, username, password):
        self.username = username
        self.password = password

    def list(self):
        """Simulate Gmail LIST response with special-use flags."""
        mailboxes = [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren) "/" "Quarantine"',
            b'(\\All \\HasNoChildren) "/" "[Gmail]/All Mail"',
            b'(\\Trash \\HasNoChildren) "/" "[Gmail]/Trash"',
        ]
        return "OK", mailboxes

    def select(self, mailbox, readonly=True):
        self.current_folder = mailbox
        # Track All Mail selection
        if mailbox in ['[Gmail]/All Mail', '[Google Mail]/All Mail']:
            self.gmail_operations.append(('select', mailbox))
        return "OK", [b"1"]

    def search(self, charset, criterion, header, value):
        if self.current_folder not in self.mailboxes:
            return "NO", [b""]
        matches = [uid for uid, msgid in self.mailboxes[self.current_folder].items() if msgid == value]
        result = b" ".join(str(uid).encode() for uid in matches) if matches else b""
        return "OK", [result]

    def append(self, folder, flags, date_time, message_bytes):
        self.appended = True
        msg = BytesParser(policy=default_policy).parsebytes(message_bytes)
        mid = (msg["Message-ID"] or "").strip()
        mailbox = self.mailboxes.setdefault(folder, {})
        new_uid = max(mailbox.keys() or [400]) + 1
        mailbox[new_uid] = mid
        return "OK", [b"APPEND completed"]

    def uid(self, command, *args):
        if command == 'SEARCH':
            # Handle different SEARCH argument patterns
            if len(args) == 2 and args[0] is None:
                # Simple search like (None, 'ALL')
                criterion = args[1]
                data = None
            elif len(args) >= 3:
                _, criterion, data = args[0], args[1], args[2]
            else:
                return "NO", [b"Invalid SEARCH arguments"]
            # Handle X-GM-RAW searches (Gmail extension)
            if criterion == 'X-GM-RAW' and self.current_folder in self.mailboxes:
                raw_query = data
                # Simple matching: look for message ID in query
                matches = []
                for uid, msgid in self.mailboxes[self.current_folder].items():
                    # Extract clean message ID for matching
                    clean_msgid = msgid.strip('<>').strip()
                    if clean_msgid in raw_query or msgid in raw_query:
                        matches.append(uid)
                result = b" ".join(str(uid).encode() for uid in matches) if matches else b""
                # Track All Mail search
                if self.current_folder in ['[Gmail]/All Mail', '[Google Mail]/All Mail']:
                    self.gmail_operations.append(('uid_search', self.current_folder, raw_query, 'X-GM-RAW'))
                return "OK", [result]
            # Handle HEADER X-Google-Original-Message-ID searches
            if criterion == 'HEADER' and len(args) > 3:
                header_name = data
                value = args[3]
                if header_name == 'X-Google-Original-Message-ID' and self.current_folder in self.mailboxes:
                    matches = [uid for uid, msgid in self.mailboxes[self.current_folder].items() if msgid.strip('<>').strip() == value.strip('<>').strip()]
                    result = b" ".join(str(uid).encode() for uid in matches) if matches else b""
                    if self.current_folder in ['[Gmail]/All Mail', '[Google Mail]/All Mail']:
                        self.gmail_operations.append(('uid_search', self.current_folder, value, 'HEADER-XGOOG'))
                    return "OK", [result]
            # Handle regular HEADER Message-ID searches
            if criterion == 'HEADER' and len(args) > 3 and self.current_folder in self.mailboxes:
                value = args[3]
                # Support both exact and stripped message ID matching
                # (e.g., "<id@example.com>" should match both "<id@example.com>" and "id@example.com")
                value_stripped = value.strip('<>').strip()
                matches = [
                    uid for uid, msgid in self.mailboxes[self.current_folder].items()
                    if msgid == value or msgid.strip('<>').strip() == value_stripped
                ]
                result = b" ".join(str(uid).encode() for uid in matches) if matches else b""
                # Track All Mail search
                if self.current_folder in ['[Gmail]/All Mail', '[Google Mail]/All Mail']:
                    self.gmail_operations.append(('uid_search', self.current_folder, value))
                return "OK", [result]
            if criterion == 'UID':
                value = int(args[2])
                matches = [value] if value in self.mailboxes.get(self.current_folder, {}) else []
                return "OK", [b" ".join(str(uid).encode() for uid in matches) if matches else b""]
        if command == 'MOVE':
            # RFC 6851 MOVE command
            uid = int(args[0])
            dest_folder = args[1]
            if self.current_folder in self.mailboxes and uid in self.mailboxes[self.current_folder]:
                msgid = self.mailboxes[self.current_folder].pop(uid)
                self.mailboxes.setdefault(dest_folder, {})[uid] = msgid
                # Track Gmail MOVE operations
                if self.current_folder in ['[Gmail]/All Mail', '[Google Mail]/All Mail']:
                    self.gmail_operations.append(('uid_move', uid, self.current_folder, dest_folder))
                return "OK", [b"MOVE completed"]
            return "NO", [b"UID not found"]
        if command == 'COPY':
            # Traditional COPY command
            uid = int(args[0])
            dest_folder = args[1]
            if self.current_folder in self.mailboxes and uid in self.mailboxes[self.current_folder]:
                msgid = self.mailboxes[self.current_folder][uid]
                self.mailboxes.setdefault(dest_folder, {})[uid] = msgid
                # Track Gmail COPY operations
                if self.current_folder in ['[Gmail]/All Mail', '[Google Mail]/All Mail']:
                    self.gmail_operations.append(('uid_copy', uid, self.current_folder, dest_folder))
                return "OK", [b"COPY completed"]
            return "NO", [b"UID not found"]
        if command == 'STORE':
            uid = args[0] if isinstance(args[0], str) else int(args[0])
            operation = args[1] if len(args) > 1 else None
            label = args[2] if len(args) > 2 else None

            # Track Gmail X-GM-LABELS operations (deprecated in new approach)
            if operation and 'X-GM-LABELS' in operation:
                self.gmail_operations.append(('uid_store', uid, operation, label))

            # Handle FLAGS operations (+FLAGS, -FLAGS)
            if operation and 'FLAGS' in operation:
                if self.current_folder in ['[Gmail]/All Mail', '[Google Mail]/All Mail']:
                    self.gmail_operations.append(('uid_store_flags', uid, operation, label))
                # Mark message as deleted (handle various flag formats: \Deleted, \\Deleted, (\\Deleted))
                if label and ('Deleted' in str(label)):
                    if self.current_folder in self.mailboxes and int(uid) in self.mailboxes[self.current_folder]:
                        self.deleted_uids.append(int(uid))
            return "OK", [b"OK"]
        if command == 'EXPUNGE':
            # RFC 4315 UID EXPUNGE - expunges specific UIDs
            uid_set = args[0] if args else None
            if uid_set:
                uids_to_expunge = [int(u) for u in uid_set.split(',')]
                for uid in uids_to_expunge:
                    if self.current_folder in self.mailboxes:
                        self.mailboxes[self.current_folder].pop(uid, None)
                if self.current_folder in ['[Gmail]/All Mail', '[Google Mail]/All Mail']:
                    self.gmail_operations.append(('uid_expunge', uids_to_expunge))
            return "OK", [b"EXPUNGE completed"]
        return "OK", [b""]

    def expunge(self):
        """Traditional EXPUNGE - removes all \\Deleted messages."""
        if self.current_folder in self.mailboxes:
            for uid in self.deleted_uids:
                self.mailboxes[self.current_folder].pop(uid, None)
            if self.current_folder in ['[Gmail]/All Mail', '[Google Mail]/All Mail']:
                self.gmail_operations.append(('expunge', self.deleted_uids.copy()))
        self.deleted_uids.clear()
        return "OK", [b"EXPUNGE completed"]

    def logout(self):
        return "BYE", []


def _prepare_release_fixture(raw_path, account_id=1, email_id=1):
    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    conn.execute("DELETE FROM email_accounts")
    conn.execute(
        """
        INSERT INTO email_accounts
        (id, account_name, email_address, imap_host, imap_port, imap_username, imap_password, imap_use_ssl, is_active)
        VALUES (?, 'Test Release', 'test@example.com', 'imap.example.com', 993, 'testuser', ?, 1, 1)
        """,
        (account_id, encrypt_credential("testpassword")),
    )
    conn.execute(
        """
        INSERT INTO email_messages
        (id, account_id, interception_status, status, subject, body_text, raw_path, direction, original_uid, message_id)
        VALUES (?, ?, 'HELD', 'PENDING', 'Test Subject', 'Test Body', ?, 'inbound', 123, '<test@example.com>')
        """,
        (email_id, account_id, raw_path),
    )
    conn.commit()


def test_release_basic(monkeypatch, client, tmp_path):
    _login(client)

    raw_file = tmp_path / "test1.eml"
    msg = EmailMessage()
    msg["Subject"] = "Test"
    msg.set_content("Body")
    raw_file.write_bytes(msg.as_bytes())

    _prepare_release_fixture(str(raw_file))

    fake_imap = ReleaseIMAP("imap.example.com", 993)
    fake_imap.preload("Quarantine", 123, "<test@example.com>")

    monkeypatch.setattr(route, "imaplib", SimpleNamespace(IMAP4_SSL=lambda *args, **kwargs: fake_imap, Time2Internaldate=route.imaplib.Time2Internaldate, IMAP4=route.imaplib.IMAP4))
    monkeypatch.setattr(route, "_ensure_quarantine", lambda imap_obj, folder: folder)

    response = client.post(
        "/api/interception/release/1",
        json={"target_folder": "INBOX"},
        headers={"Content-Type": "application/json"},
    )
    if response.status_code != 200:
        print(f"ERROR RESPONSE: {response.get_json()}")
    assert response.status_code == 200
    assert fake_imap.appended


def test_release_with_edits_multipart(monkeypatch, client, tmp_path):
    _login(client)

    raw_file = tmp_path / "multipart.eml"
    msg = EmailMessage()
    msg["Subject"] = "Original Subject"
    msg.set_content("Original plain text")
    msg.add_alternative("<p>Original HTML</p>", subtype="html")
    raw_file.write_bytes(msg.as_bytes())

    _prepare_release_fixture(str(raw_file))

    fake_imap = ReleaseIMAP("imap.example.com", 993)
    fake_imap.preload("Quarantine", 123, "<test@example.com>")

    monkeypatch.setattr(route, "imaplib", SimpleNamespace(IMAP4_SSL=lambda *args, **kwargs: fake_imap, Time2Internaldate=route.imaplib.Time2Internaldate, IMAP4=route.imaplib.IMAP4))
    monkeypatch.setattr(route, "_ensure_quarantine", lambda imap_obj, folder: folder)

    response = client.post(
        "/api/interception/release/1",
        json={
            "edited_subject": "Edited Subject",
            "edited_body": "Edited body text",
            "target_folder": "INBOX",
        },
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200


def test_release_idempotent_already_released(monkeypatch, client, tmp_path):
    _login(client)

    raw_file = tmp_path / "test2.eml"
    msg = EmailMessage()
    msg["Subject"] = "Test"
    msg.set_content("Body")
    raw_file.write_bytes(msg.as_bytes())

    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    conn.execute("DELETE FROM email_accounts")
    conn.execute(
        """
        INSERT INTO email_accounts
        (id, account_name, email_address, imap_host, imap_port, imap_username, imap_password, imap_use_ssl, is_active)
        VALUES (1, 'Test', 'test@example.com', 'imap.example.com', 993, 'user', ?, 1, 1)
        """,
        (encrypt_credential("password"),),
    )
    conn.execute(
        """
        INSERT INTO email_messages
        (id, account_id, interception_status, status, subject, body_text, raw_path, direction, original_uid, message_id)
        VALUES (99, 1, 'RELEASED', 'DELIVERED', 'Test', 'Body', ?, 'inbound', 123, '<test@example.com>')
        """,
        (str(raw_file),),
    )
    conn.commit()

    fake_imap = ReleaseIMAP("imap.example.com", 993)
    monkeypatch.setattr(route, "imaplib", SimpleNamespace(IMAP4_SSL=lambda *args, **kwargs: fake_imap, Time2Internaldate=route.imaplib.Time2Internaldate, IMAP4=route.imaplib.IMAP4))

    response = client.post("/api/interception/release/99")
    assert response.status_code == 200
    assert response.get_json()["reason"] == "already-released"


def test_release_discarded_cannot_release(monkeypatch, client, tmp_path):
    _login(client)

    raw_file = tmp_path / "test3.eml"
    msg = EmailMessage()
    msg["Subject"] = "Test"
    msg.set_content("Body")
    raw_file.write_bytes(msg.as_bytes())

    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    conn.execute("DELETE FROM email_accounts")
    conn.execute(
        """
        INSERT INTO email_accounts
        (id, account_name, email_address, imap_host, imap_port, imap_username, imap_password, imap_use_ssl, is_active)
        VALUES (1, 'Test', 'test@example.com', 'imap.example.com', 993, 'user', ?, 1, 1)
        """,
        (encrypt_credential("password"),),
    )
    conn.execute(
        """
        INSERT INTO email_messages
        (id, account_id, interception_status, status, subject, body_text, raw_path, direction, original_uid, message_id)
        VALUES (98, 1, 'DISCARDED', 'REJECTED', 'Test', 'Body', ?, 'inbound', 123, '<test@example.com>')
        """,
        (str(raw_file),),
    )
    conn.commit()

    response = client.post("/api/interception/release/98")
    assert response.status_code == 409
    assert response.get_json()["reason"] == "discarded"


def test_release_raw_content_missing(monkeypatch, client, tmp_path):
    _login(client)

    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    conn.execute("DELETE FROM email_accounts")
    conn.execute(
        """
        INSERT INTO email_accounts
        (id, account_name, email_address, imap_host, imap_port, imap_username, imap_password, imap_use_ssl, is_active)
        VALUES (5, 'Missing Raw', 'missing@example.com', 'imap.example.com', 993, 'user', ?, 1, 1)
        """,
        (encrypt_credential("password"),),
    )
    conn.execute(
        """
        INSERT INTO email_messages
        (id, account_id, interception_status, status, subject, body_text, raw_path, direction, original_uid, message_id)
        VALUES (120, 5, 'HELD', 'PENDING', 'Test', 'Body', '/fake/path/raw.eml', 'inbound', 123, '<missing@example.com>')
        """
    )
    conn.commit()

    fake_imap = ReleaseIMAP("imap.missing.test", 993)
    monkeypatch.setattr(route, "imaplib", SimpleNamespace(IMAP4_SSL=lambda *args, **kwargs: fake_imap, Time2Internaldate=route.imaplib.Time2Internaldate, IMAP4=route.imaplib.IMAP4))
    monkeypatch.setattr(route, "_ensure_quarantine", lambda imap_obj, folder: folder)

    resp = client.post(
        "/api/interception/release/120",
        json={"target_folder": "INBOX"},
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 500
    assert resp.get_json()["reason"] == "raw-missing"


def test_release_removes_original_from_inbox_if_present(monkeypatch, client, tmp_path):
    _login(client)

    # Build a basic raw message to store
    msg = EmailMessage()
    msg["Subject"] = "Orig Subject"
    msg.set_content("Plain body")

    raw_file = tmp_path / "release_inbox_cleanup.eml"
    raw_file.write_bytes(msg.as_bytes())

    # Prepare DB with HELD message and known original Message-ID
    email_id = 171
    account_id = 7
    original_mid = "<inbox-cleanup@example.com>"

    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    conn.execute("DELETE FROM email_accounts")
    conn.execute(
        """
        INSERT INTO email_accounts
        (id, account_name, email_address, imap_host, imap_port, imap_username, imap_password, imap_use_ssl, is_active)
        VALUES (?, 'Cleanup Account', 'cleanup7@example.com', 'imap.gmail.com', 993, 'cleanup_user', ?, 1, 1)
        """,
        (account_id, encrypt_credential("cleanup-secret")),
    )
    conn.execute(
        """
        INSERT INTO email_messages
        (id, account_id, interception_status, status, subject, body_text, raw_path, direction, original_uid, message_id)
        VALUES (?, ?, 'HELD', 'PENDING', 'Orig Subject', 'Body', ?, 'inbound', 999, ?)
        """,
        (email_id, account_id, str(raw_file), original_mid),
    )
    conn.commit()

    # Fake IMAP with original present in both Quarantine and INBOX
    fake_imap = ReleaseIMAP("imap.gmail.com", 993)
    fake_imap.preload("Quarantine", 999, original_mid)
    fake_imap.preload("INBOX", 555, original_mid)  # simulate stray original in INBOX

    # Patch imaplib usage in route
    monkeypatch.setattr(route, "imaplib", SimpleNamespace(IMAP4_SSL=lambda *args, **kwargs: fake_imap, Time2Internaldate=route.imaplib.Time2Internaldate, IMAP4=route.imaplib.IMAP4))
    monkeypatch.setattr(route, "_ensure_quarantine", lambda imap_obj, folder: folder)

    # Release
    response = client.post(
        f"/api/interception/release/{email_id}",
        json={"target_folder": "INBOX"},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200

    # Original should be removed from INBOX and Quarantine; only the edited should remain in INBOX
    assert original_mid not in list(fake_imap.mailboxes.get("INBOX", {}).values())
    assert fake_imap.mailboxes.get("Quarantine", {}) == {}
