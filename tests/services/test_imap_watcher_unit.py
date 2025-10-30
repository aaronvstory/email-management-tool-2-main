import os
import sqlite3
from datetime import datetime
from email.message import EmailMessage

import pytest

from app.services.imap_watcher import ImapWatcher, AccountConfig
from tests.conftest import _create_test_schema


@pytest.fixture
def watcher_setup(tmp_path, monkeypatch):
    db_path = tmp_path / "imap_unit.db"
    with sqlite3.connect(db_path) as conn:
        _create_test_schema(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO email_accounts
            (id, account_name, email_address, imap_host, imap_port, imap_username, imap_password, imap_use_ssl, is_active, last_checked, last_error)
            VALUES (1, 'Watcher', 'watcher@example.com', 'imap.example.com', 993, 'user', 'secret', 1, 1, datetime('now'), NULL)
            """
        )
        conn.commit()
    cfg = AccountConfig(
        account_id=1,
        imap_host="imap.example.com",
        imap_port=993,
        username="user",
        password="secret",
        use_ssl=True,
        db_path=str(db_path),
    )
    watcher = ImapWatcher(cfg)
    monkeypatch.setenv("IMAP_FORCE_COPY_PURGE", "0")
    monkeypatch.setenv("IMAP_CIRCUIT_THRESHOLD", "5")
    return watcher, str(db_path)


def test_record_failure_trips_circuit(monkeypatch, watcher_setup):
    watcher, db_path = watcher_setup
    monkeypatch.setenv("IMAP_CIRCUIT_THRESHOLD", "1")

    watcher._record_failure("socket-error")

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT is_active, last_error FROM email_accounts WHERE id=1").fetchone()
        hb = conn.execute("SELECT error_count FROM worker_heartbeats WHERE worker_id='imap_1'").fetchone()

    assert row[0] == 0
    assert row[1].startswith("circuit_open")
    assert hb[0] >= 1


def test_update_heartbeat_resets_error_count(watcher_setup):
    watcher, db_path = watcher_setup
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM worker_heartbeats WHERE worker_id='imap_1'")
        conn.execute(
            "INSERT INTO worker_heartbeats(worker_id, error_count, status) VALUES ('imap_1', 5, 'error')"
        )
        conn.commit()

    watcher._update_heartbeat("active")

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT error_count, status FROM worker_heartbeats WHERE worker_id='imap_1'").fetchone()
    assert row[0] == 0
    assert row[1] == "active"


def test_should_stop_checks_account_flag(watcher_setup):
    watcher, db_path = watcher_setup
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE email_accounts SET is_active=0 WHERE id=1")
        conn.commit()
    assert watcher._should_stop() is True


def test_should_stop_missing_account_returns_true(watcher_setup, tmp_path):
    watcher, db_path = watcher_setup
    watcher.cfg.account_id = 999
    assert watcher._should_stop() is True


def test_get_last_processed_uid_reads_max(watcher_setup):
    watcher, db_path = watcher_setup
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO email_messages (account_id, original_uid, interception_status) VALUES (1, 10, 'HELD')"
        )
        conn.execute(
            "INSERT INTO email_messages (account_id, original_uid, interception_status) VALUES (1, 25, 'HELD')"
        )
        conn.commit()
    assert watcher._get_last_processed_uid() == 25


def test_supports_uid_move(monkeypatch, watcher_setup):
    watcher, _ = watcher_setup

    class FakeClient:
        def capabilities(self):
            return [b"MOVE"]

    watcher._client = FakeClient()
    assert watcher._supports_uid_move() is True
    monkeypatch.setenv("IMAP_FORCE_COPY_PURGE", "1")
    assert watcher._supports_uid_move() is False


class FakeIMAPClient:
    def __init__(self):
        self.selected = []
        self.copied = []
        self.added_flags = []
        self.expunged = False

    def select_folder(self, folder, readonly=False):
        self.selected.append((folder, readonly))

    def create_folder(self, folder):
        self.created = folder

    def copy(self, uids, folder):
        self.copied.append((tuple(uids), folder))

    def add_flags(self, uids, flags):
        self.added_flags.append((tuple(uids), tuple(flags)))

    def expunge(self):
        self.expunged = True

    def capabilities(self):
        return [b"UIDPLUS"]

    def uid_expunge(self, uids):
        self.uid_expunge_called = True

    def delete_messages(self, uids, silent=False):
        self.delete_messages_called = True


def test_copy_purge_success(monkeypatch, watcher_setup):
    watcher, _ = watcher_setup
    fake_client = FakeIMAPClient()
    watcher._client = fake_client
    watcher.cfg.quarantine = "Quarantine"
    watcher.cfg.inbox = "INBOX"

    watcher._copy_purge([101, 102])

    assert fake_client.copied[0][1].endswith("Quarantine")
    assert fake_client.expunged is True
    assert watcher.cfg.quarantine.endswith("Quarantine")


def test_move_falls_back_to_copy(monkeypatch, watcher_setup):
    watcher, _ = watcher_setup
    events = []

    class MoveClient:
        def move(self, uids, folder):
            raise RuntimeError("no move")

    watcher._client = MoveClient()
    monkeypatch.setattr(watcher, "_copy_purge", lambda uids: events.append(("copy_purge", uids)))
    watcher._move([1, 2, 3])
    assert events == [("copy_purge", [1, 2, 3])]


class FetchClient:
    def __init__(self, message_bytes):
        self._data = {
            b"RFC822": message_bytes,
            b"INTERNALDATE": datetime(2024, 1, 1, 12, 0, 0),
        }

    def fetch(self, uids, parts):
        return {uids[0]: self._data}


def test_store_in_database_persists_and_holds(monkeypatch, watcher_setup):
    watcher, db_path = watcher_setup
    email = EmailMessage()
    email["Subject"] = "Hold this"
    email["From"] = "sender@example.com"
    email["To"] = "recipient@example.com"
    email.set_content("Plain body")

    monkeypatch.setattr("app.services.imap_watcher.evaluate_rules", lambda *args, **kwargs: {"should_hold": True, "risk_score": 80, "keywords": ["invoice"]})

    held = watcher._store_in_database(FetchClient(email.as_bytes()), [321])
    assert held == [321]

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT subject, interception_status FROM email_messages WHERE original_uid=321").fetchone()
    assert row[0] == "Hold this"
    assert row[1] == "INTERCEPTED"


def test_store_in_database_skips_duplicate(monkeypatch, watcher_setup):
    watcher, db_path = watcher_setup
    email = EmailMessage()
    email["Subject"] = "Duplicate"
    email["From"] = "dup@example.com"
    email["To"] = "dup@example.com"
    email["Message-ID"] = "<dup@example.com>"
    email.set_content("body")

    monkeypatch.setattr("app.services.imap_watcher.evaluate_rules", lambda *args, **kwargs: {"should_hold": False, "risk_score": 0, "keywords": []})

    watcher._store_in_database(FetchClient(email.as_bytes()), [900])
    result = watcher._store_in_database(FetchClient(email.as_bytes()), [900])

    assert result == []
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM email_messages WHERE message_id='<dup@example.com>'").fetchone()[0]
    assert count == 1


def test_store_in_database_non_hold(monkeypatch, watcher_setup):
    watcher, db_path = watcher_setup
    email = EmailMessage()
    email["Subject"] = "Information"
    email["From"] = "info@example.com"
    email["To"] = "recipient@example.com"
    email.set_content("Body goes here")

    monkeypatch.setattr("app.services.imap_watcher.evaluate_rules", lambda *args, **kwargs: {"should_hold": False, "risk_score": 0, "keywords": []})

    held = watcher._store_in_database(FetchClient(email.as_bytes()), [402])
    assert held == []
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT interception_status FROM email_messages WHERE original_uid=402").fetchone()
    assert row[0] == "FETCHED"


def test_update_message_status_sets_latency(watcher_setup, monkeypatch):
    watcher, db_path = watcher_setup
    watcher.cfg.quarantine = "Quarantine"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO email_messages
            (id, account_id, original_uid, interception_status, status, created_at, latency_ms)
            VALUES (501, 1, 501, 'INTERCEPTED', 'PENDING', datetime('now','-5 minutes'), NULL)
            """
        )
        conn.commit()

    watcher._update_message_status([501], "HELD")

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT interception_status, status, latency_ms FROM email_messages WHERE original_uid=501").fetchone()
    assert row[0] == "HELD"
    assert row[1] == "PENDING"
    assert row[2] is not None


class HandleClient:
    def __init__(self):
        self.selected = []

    def select_folder(self, folder, readonly=False):
        self.selected.append((folder, readonly))

    def folder_status(self, folder, keys):
        return {b"UIDNEXT": 160}

    def search(self, criterion):
        if criterion == "ALL":
            return [150, 155, 159]
        if criterion == "UNSEEN":
            return [159]
        return []


def test_handle_new_messages_moves_and_updates(monkeypatch, watcher_setup):
    watcher, db_path = watcher_setup
    watcher.cfg.quarantine = "Quarantine"
    client = HandleClient()
    watcher._client = client

    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM email_messages")
        conn.execute(
            "INSERT INTO email_messages (account_id, original_uid, interception_status) VALUES (1, 150, 'INTERCEPTED')"
        )
        conn.commit()

    called = {}
    monkeypatch.setattr(watcher, "_store_in_database", lambda client, uids: [uids[-1]])
    monkeypatch.setattr(watcher, "_supports_uid_move", lambda: True)
    monkeypatch.setattr(watcher, "_move", lambda uids: called.setdefault("move", []).append(tuple(uids)))
    monkeypatch.setattr(watcher, "_update_message_status", lambda uids, status: called.setdefault("update", []).append((tuple(uids), status)))

    watcher._handle_new_messages(client, {})

    assert called["move"] == [(159,)]
    assert called["update"] == [((159,), "HELD")]
    assert watcher._last_uidnext >= 160


def test_handle_new_messages_no_new_uids(watcher_setup):
    watcher, _ = watcher_setup

    class EmptyClient:
        def select_folder(self, *args, **kwargs):
            pass

        def folder_status(self, *args, **kwargs):
            return {b"UIDNEXT": watcher._last_uidnext}

        def search(self, *args, **kwargs):
            return []

    watcher._handle_new_messages(EmptyClient(), {})


def test_handle_new_messages_copy_fallback(monkeypatch, watcher_setup):
    watcher, _ = watcher_setup
    watcher.cfg.quarantine = "Quarantine"
    events = {}

    class CopyClient(HandleClient):
        pass

    client = CopyClient()
    monkeypatch.setattr(watcher, "_store_in_database", lambda client, uids: [uids[-1]])
    monkeypatch.setattr(watcher, "_supports_uid_move", lambda: False)
    monkeypatch.setattr(watcher, "_copy_purge", lambda uids: events.setdefault("copy", []).append(tuple(uids)))
    monkeypatch.setattr(watcher, "_update_message_status", lambda uids, status: events.setdefault("update", []).append((tuple(uids), status)))

    watcher._handle_new_messages(client, {})
    assert events["copy"] == [(159,)]
    assert events["update"] == [((159,), "HELD")]


def test_handle_new_messages_all_seen_advances_pointer(watcher_setup):
    watcher, db_path = watcher_setup
    watcher._last_uidnext = 140

    class SeenClient(HandleClient):
        pass

    client = SeenClient()
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM email_messages")
        conn.execute("INSERT INTO email_messages (account_id, original_uid, interception_status) VALUES (1, 150, 'HELD')")
        conn.execute("INSERT INTO email_messages (account_id, original_uid, interception_status) VALUES (1, 159, 'HELD')")
        conn.commit()

    watcher._handle_new_messages(client, {})
    assert watcher._last_uidnext >= 160


def test_copy_purge_no_client_does_nothing(watcher_setup):
    watcher, _ = watcher_setup
    watcher._client = None
    watcher._copy_purge([1, 2, 3])  # should not raise


def test_connect_initializes_quarantine(monkeypatch, watcher_setup):
    watcher, db_path = watcher_setup

    class FakeConnectClient:
        def __init__(self, host, port, ssl, ssl_context, timeout):
            self.host = host
            self.logins = []
            self.selected = []

        def login(self, username, password):
            self.logins.append((username, password))

        def capabilities(self):
            return [b"UIDPLUS", b"MOVE"]

        def select_folder(self, folder, readonly=False):
            self.selected.append((folder, readonly))

        def create_folder(self, folder):
            self.created = folder

        def list_folders(self):
            return [((), b"/", "INBOX")]

        def folder_status(self, folder, keys):
            return {b"UIDNEXT": 500}

    monkeypatch.setattr("app.services.imap_watcher.sslmod.create_default_context", lambda: None)
    monkeypatch.setattr("app.services.imap_watcher.IMAPClient", FakeConnectClient)
    monkeypatch.setattr(watcher, "_get_last_processed_uid", lambda: 200)

    client = watcher._connect()

    assert isinstance(client, FakeConnectClient)
    assert watcher._last_uidnext == 201
    assert watcher.cfg.quarantine.endswith("Quarantine")


def test_connect_failure_records_reason(monkeypatch, watcher_setup):
    watcher, _ = watcher_setup

    class BoomClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Authentication failed")

    monkeypatch.setattr("app.services.imap_watcher.sslmod.create_default_context", lambda: None)
    monkeypatch.setattr("app.services.imap_watcher.IMAPClient", BoomClient)
    recorded = {}
    monkeypatch.setattr(watcher, "_record_failure", lambda reason: recorded.setdefault("reason", reason))

    client = watcher._connect()
    assert client is None
    assert recorded["reason"] == "auth_failed"
def test_check_connection_alive_handles_exception(watcher_setup):
    watcher, _ = watcher_setup

    class BadClient:
        def noop(self):
            raise RuntimeError("no connection")

    assert watcher._check_connection_alive(None) is False
    assert watcher._check_connection_alive(BadClient()) is False
