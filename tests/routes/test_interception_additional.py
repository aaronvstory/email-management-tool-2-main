import sqlite3
import time
from pathlib import Path

from email.message import EmailMessage
from types import SimpleNamespace

import pytest

from app.routes import interception as route
from app.utils.db import get_db
from app.utils.crypto import encrypt_credential


class _FakeSocket:
    def __init__(self, *args, **kwargs):
        self._closed = False
        self.calls = []

    def settimeout(self, value):
        self.calls.append(("timeout", value))

    def connect_ex(self, addr):
        self.calls.append(("connect", addr))
        return 0

    def close(self):
        self._closed = True


def _prepare_email(conn, email_id=1, account_id=1, status="HELD", original_uid=456, message_id="<msg@example.com>"):
    conn.execute(
        """
        INSERT OR REPLACE INTO email_accounts
        (id, account_name, email_address, imap_host, imap_port, imap_username, imap_password, imap_use_ssl, is_active, last_checked, last_error)
        VALUES (?, 'Test', ?, 'imap.test', 993, 'imap_user', ?, 1, 1, datetime('now'), NULL)
        """,
        (account_id, f"account{account_id}@example.com", encrypt_credential("secret")),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO email_messages
        (id, account_id, interception_status, status, subject, body_text, original_uid, quarantine_folder, direction, created_at, message_id)
        VALUES (?, ?, ?, ?, 'Subject', 'Body', ?, 'Quarantine', 'inbound', datetime('now'), ?)
        """,
        (email_id, account_id, status, status, original_uid, message_id),
    )
    conn.commit()


def _login(client):
    conn = get_db()
    conn.execute(
        """
        INSERT OR REPLACE INTO email_messages
        (id, interception_status, status, subject, body_text, recipients, direction, created_at)
        VALUES (9999, 'HELD', 'PENDING', 'Seed Subject', 'Seed Body', 'seed@example.com', 'inbound', datetime('now'))
        """
    )
    conn.commit()
    client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)


def test_healthz_reports_status_and_cache(client, monkeypatch):
    monkeypatch.setenv("IMAP_DISABLE_IDLE", "1")
    monkeypatch.setenv("IMAP_POLL_INTERVAL", "60")
    monkeypatch.setenv("IMAP_LOG_VERBOSE", "1")
    monkeypatch.setenv("IMAP_CIRCUIT_THRESHOLD", "6")

    fake_socket = _FakeSocket()
    original_socket = route.socket
    monkeypatch.setattr(
        route,
        "socket",
        SimpleNamespace(
            socket=lambda *args, **kwargs: fake_socket,
            AF_INET=original_socket.AF_INET,
            SOCK_STREAM=original_socket.SOCK_STREAM,
        ),
    )

    route._HEALTH_CACHE = {"ts": 0.0, "payload": None}
    client.application.config["SECRET_KEY"] = "x" * 40

    conn = get_db()
    conn.execute("DELETE FROM worker_heartbeats")
    conn.execute("DELETE FROM email_messages")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS system_status (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.execute("INSERT OR REPLACE INTO worker_heartbeats(worker_id, last_heartbeat, status, error_count) VALUES ('imap_1', datetime('now'), 'ok', 0)")
    conn.execute(
        "INSERT OR REPLACE INTO system_status(key, value) VALUES ('smtp_last_selfcheck', '2024-01-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT OR REPLACE INTO email_messages(id, interception_status, status, latency_ms, direction, created_at) VALUES (999, 'HELD', 'PENDING', 42, 'inbound', datetime('now'))"
    )
    conn.commit()

    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["held_count"] == 1
    assert data["smtp"]["listening"] is True
    assert data["security"]["secret_key_configured"] is True

    cached = client.get("/healthz").get_json()
    assert cached["cached"] is True


def test_healthz_handles_db_error(client, monkeypatch):
    route._HEALTH_CACHE = {"ts": 0.0, "payload": None}
    monkeypatch.setattr(route, "_db", lambda: (_ for _ in ()).throw(sqlite3.OperationalError("boom")))

    resp = client.get("/healthz")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["ok"] is False
    assert "error" in data


def test_healthz_returns_cached_payload(client):
    route._HEALTH_CACHE = {"ts": time.time(), "payload": {"ok": True, "cached": False}}
    resp = client.get("/healthz")
    assert resp.get_json()["cached"] is True


def test_healthz_handles_security_exception(client, monkeypatch):
    original_config = dict(client.application.config)

    class BrokenConfig(dict):
        def get(self, key, default=None):
            if key == "SECRET_KEY":
                raise RuntimeError("config boom")
            return super().get(key, default)

    client.application.config = BrokenConfig(original_config)
    route._HEALTH_CACHE = {"ts": 0.0, "payload": None}
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json()["security"]["status"] == "unavailable"
    client.application.config = original_config


def test_healthz_handles_imap_config_exception(client, monkeypatch):
    def failing_getenv(key, default=None):
        if key == "IMAP_DISABLE_IDLE":
            raise RuntimeError("env boom")
        return route.os.getenv(key, default)

    monkeypatch.setattr(route.os, "getenv", failing_getenv)
    route._HEALTH_CACHE = {"ts": 0.0, "payload": None}
    resp = client.get("/healthz")
    data = resp.get_json()
    assert data["imap_config"]["status"] == "unavailable"


def test_api_smtp_health_reports_status(client, monkeypatch):
    fake_socket = _FakeSocket()
    original_socket = route.socket
    monkeypatch.setattr(
        route,
        "socket",
        SimpleNamespace(
            socket=lambda *args, **kwargs: fake_socket,
            AF_INET=original_socket.AF_INET,
            SOCK_STREAM=original_socket.SOCK_STREAM,
        ),
    )

    conn = get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS system_status (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR REPLACE INTO system_status(key, value) VALUES ('smtp_last_selfcheck', '2024-01-01T00:00:00Z')")
    conn.commit()

    resp = client.get("/api/smtp-health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["last_selfcheck_ts"] == "2024-01-01T00:00:00Z"


def test_metrics_updates_counts(client, monkeypatch):
    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    conn.execute(
        "INSERT INTO email_messages (id, interception_status, status) VALUES (1, 'HELD', 'PENDING')"
    )
    conn.execute(
        "INSERT INTO email_messages (id, interception_status, status) VALUES (2, 'RELEASED', 'DELIVERED')"
    )
    conn.commit()

    updates = {}

    monkeypatch.setattr("app.utils.metrics.update_held_count", lambda value: updates.setdefault("held", value))
    monkeypatch.setattr("app.utils.metrics.update_pending_count", lambda value: updates.setdefault("pending", value))
    monkeypatch.setattr(route, "generate_latest", lambda: b"metrics")

    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.data == b"metrics"
    assert resp.headers["Content-Type"] == route.CONTENT_TYPE_LATEST
    assert updates == {"held": 1, "pending": 1}


def test_metrics_handles_exception(client, monkeypatch):
    monkeypatch.setattr(route, "_db", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    monkeypatch.setattr(route, "generate_latest", lambda: b"empty")

    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.data == b"empty"


def test_api_email_edit_updates_fields(client):
    _login(client)
    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    conn.execute(
        """
        INSERT INTO email_messages (id, interception_status, status, subject, body_text, body_html)
        VALUES (1, 'HELD', 'PENDING', 'Old', 'Old body', '<p>Old</p>')
        """
    )
    conn.commit()

    resp = client.post(
        "/api/email/1/edit",
        json={"subject": "New subject", "body_text": "New body"},
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert set(data["updated_fields"]) == {"subject", "body_text"}

    updated = get_db().execute("SELECT subject, body_text FROM email_messages WHERE id=1").fetchone()
    assert updated["subject"] == "New subject"
    assert updated["body_text"] == "New body"


def test_api_email_edit_requires_fields(client):
    _login(client)
    resp = client.post(
        "/api/email/1/edit",
        json={},
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "no-fields"


class _FakeIMAP:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def starttls(self):
        return None

    def login(self, username, password):
        self.logged_in = (username, password)

    def select(self, mailbox="INBOX"):
        return "OK", [b"1"]

    def logout(self):
        self.logged_out = True


def test_api_email_intercept_success(monkeypatch, client):
    _login(client)
    monkeypatch.setattr(route, "_ensure_quarantine", lambda imap_obj, folder: folder)
    monkeypatch.setattr(route, "_move_uid_to_quarantine", lambda imap_obj, uid, folder: True)
    monkeypatch.setattr(route, "imaplib", SimpleNamespace(IMAP4=_FakeIMAP, IMAP4_SSL=_FakeIMAP))

    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    _prepare_email(conn, email_id=5, account_id=7, status="PENDING")

    resp = client.post("/api/email/5/intercept")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["remote_move"] is True
    assert data["quarantine_folder"] == "Quarantine"


def test_api_email_intercept_handles_imap_error(monkeypatch, client):
    _login(client)
    monkeypatch.setattr(route, "decrypt_credential", lambda value: None)

    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    _prepare_email(conn, email_id=9, account_id=3, status="PENDING")

    resp = client.post("/api/email/9/intercept")
    assert resp.status_code == 502
    data = resp.get_json()
    assert data["success"] is False
    assert "error" in data["note"].lower()


def test_api_email_intercept_resolves_uid(monkeypatch, client):
    _login(client)

    resolved_uid = b"789"

    class SearchIMAP(_FakeIMAP):
        def __init__(self, host, port):
            super().__init__(host, port)

        def uid(self, command, *args, **kwargs):
            if command == "SEARCH":
                return "OK", [resolved_uid]
            return "NO", []

    monkeypatch.setattr(route, "imaplib", SimpleNamespace(IMAP4=_FakeIMAP, IMAP4_SSL=SearchIMAP))
    monkeypatch.setattr(route, "_ensure_quarantine", lambda imap_obj, folder: folder)
    monkeypatch.setattr(route, "_move_uid_to_quarantine", lambda imap_obj, uid, folder: True)

    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    _prepare_email(conn, email_id=11, account_id=11, status="PENDING", original_uid=None, message_id="<findme@example.com>")
    conn.commit()

    resp = client.post("/api/email/11/intercept")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    row = get_db().execute("SELECT original_uid, latency_ms FROM email_messages WHERE id=11").fetchone()
    assert row["original_uid"] == int(resolved_uid)
    assert row["latency_ms"] is not None


def test_api_interception_get_includes_snippet_and_diff(client, tmp_path):
    _login(client)
    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    raw_file = tmp_path / "sample.eml"
    em = EmailMessage()
    em["Subject"] = "Demo"
    em.set_content("Plain section")
    em.add_alternative("<p>Hello <strong>world</strong></p>", subtype="html")
    raw_file.write_bytes(em.as_bytes())
    conn.execute(
        """
        INSERT INTO email_messages
        (id, interception_status, status, raw_path, body_text, direction)
        VALUES (21, 'HELD', 'PENDING', ?, 'Changed body', 'inbound')
        """,
        (str(raw_file),),
    )
    conn.commit()

    resp = client.get("/api/interception/held/21?include_diff=1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "preview_snippet" in data and "Changed body" in data["body_diff"][-1]


def test_api_interception_get_html_single_part(client, tmp_path):
    _login(client)
    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    raw_file = tmp_path / "html_only.eml"
    raw_file.write_text("Subject: Demo\r\nContent-Type: text/html\r\n\r\n<p>Hello world</p>")
    conn.execute(
        """
        INSERT INTO email_messages
        (id, interception_status, status, raw_path, direction)
        VALUES (22, 'HELD', 'PENDING', ?, 'inbound')
        """,
        (str(raw_file),),
    )
    conn.commit()

    resp = client.get("/api/interception/held/22")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "Hello world" in data["preview_snippet"]


def test_api_interception_get_multipart_html_fallback(client, tmp_path):
    _login(client)
    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    raw_file = tmp_path / "multipart_html.eml"
    raw_file.write_text(
        "Subject: Demo\r\n"
        "MIME-Version: 1.0\r\n"
        "Content-Type: multipart/alternative; boundary=\"BOUND\"\r\n"
        "\r\n"
        "--BOUND\r\n"
        "Content-Type: text/html; charset=\"utf-8\"\r\n"
        "\r\n"
        "<p>Fallback Content</p>\r\n"
        "--BOUND--\r\n"
    )
    conn.execute(
        """
        INSERT INTO email_messages
        (id, interception_status, status, raw_path, direction)
        VALUES (23, 'HELD', 'PENDING', ?, 'inbound')
        """,
        (str(raw_file),),
    )
    conn.commit()

    resp = client.get("/api/interception/held/23")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "Fallback Content" in data["preview_snippet"]


def test_interception_dashboard_redirects(client):
    _login(client)
    resp = client.get("/interception", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert resp.headers["Location"].endswith("/emails-unified?status=HELD")


def test_interception_dashboard_legacy_template(client, monkeypatch):
    _login(client)
    monkeypatch.setattr(route, "render_template", lambda template: f"rendered:{template}")
    resp = client.get("/interception-legacy")
    assert resp.data.decode() == "rendered:dashboard_interception.html"


def test_api_email_intercept_gmail_search(monkeypatch, client):
    _login(client)

    class GmailIMAP(_FakeIMAP):
        def __init__(self, host, port):
            super().__init__(host, port)
            self.search_calls = 0

        def uid(self, command, *args, **kwargs):
            if command == "SEARCH" and args[1] == "HEADER":
                self.search_calls += 1
                return "OK", [b""]
            if command == "SEARCH" and "X-GM-RAW" in args:
                return "OK", [b"999"]
            return "NO", [b""]

    monkeypatch.setattr(route, "imaplib", SimpleNamespace(IMAP4=_FakeIMAP, IMAP4_SSL=GmailIMAP))
    monkeypatch.setattr(route, "_ensure_quarantine", lambda imap_obj, folder: folder)
    monkeypatch.setattr(route, "_move_uid_to_quarantine", lambda imap_obj, uid, folder: True)

    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    conn.execute("DELETE FROM email_accounts")
    _prepare_email(
        conn,
        email_id=15,
        account_id=15,
        status="PENDING",
        original_uid=None,
        message_id="<gmail-123@example.com>",
    )
    conn.execute("UPDATE email_accounts SET imap_host='imap.gmail.com' WHERE id=15")
    conn.commit()

    resp = client.post("/api/email/15/intercept")
    assert resp.status_code == 200
    row = get_db().execute("SELECT original_uid FROM email_messages WHERE id=15").fetchone()
    assert row["original_uid"] == 999


def test_api_inbox_filters(client):
    _login(client)
    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    conn.execute(
        """
        INSERT INTO email_messages
        (id, interception_status, status, sender, subject, body_text, direction)
        VALUES (31, 'HELD', 'PENDING', 'match@example.com', 'Match Subject', 'Body text', 'inbound')
        """
    )
    conn.execute(
        """
        INSERT INTO email_messages
        (id, interception_status, status, sender, subject, body_text, direction)
        VALUES (32, 'RELEASED', 'DELIVERED', 'other@example.com', 'Other Subject', 'Body text', 'inbound')
        """
    )
    conn.commit()

    resp = client.get("/api/inbox?status=HELD&q=match")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 1
    assert data["messages"][0]["subject"] == "Match Subject"


def test_api_interception_get_not_found(client):
    _login(client)
    resp = client.get("/api/interception/held/999999")
    assert resp.status_code == 404


def test_api_email_edit_not_held_returns_conflict(client):
    _login(client)
    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    conn.execute(
        """
        INSERT INTO email_messages (id, interception_status, status, subject, body_text)
        VALUES (200, 'RELEASED', 'DELIVERED', 'Done', 'Body')
        """
    )
    conn.commit()

    resp = client.post(
        "/api/email/200/edit",
        json={"subject": "Attempt"},
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "not-held"
