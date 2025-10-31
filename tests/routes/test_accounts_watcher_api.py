import sqlite3
from types import SimpleNamespace

import pytest

import simple_app
from app.utils.crypto import encrypt_credential
from app.utils.db import get_db


class _FakeThread:
    def __init__(self, alive: bool = True):
        self._alive = alive

    def is_alive(self) -> bool:
        return self._alive


def _seed_account(account_id: int = 1, *, is_active: int = 0, with_credentials: bool = True) -> None:
    conn = get_db()
    conn.execute("DELETE FROM email_accounts WHERE id=?", (account_id,))
    imap_password = encrypt_credential("imap-pass") if with_credentials else None
    smtp_password = encrypt_credential("smtp-pass")
    conn.execute(
        """
        INSERT INTO email_accounts (
            id, account_name, email_address,
            imap_host, imap_port, imap_username, imap_password, imap_use_ssl,
            smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_ssl,
            is_active
        ) VALUES (?, 'Test Account', ?, 'imap.test', 993, ?, ?, 1,
                  'smtp.test', 587, ?, ?, 0, ?)
        """,
        (
            account_id,
            f"test{account_id}@example.com",
            f"imap-user-{account_id}",
            imap_password,
            f"smtp-user-{account_id}",
            smtp_password,
            is_active,
        ),
    )
    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def _reset_threads(monkeypatch):
    original_threads = simple_app.imap_threads
    monkeypatch.setattr(simple_app, "imap_threads", {}, raising=False)
    yield
    simple_app.imap_threads = original_threads


@pytest.fixture
def _clear_worker_heartbeats():
    conn = get_db()
    conn.execute("DELETE FROM worker_heartbeats")
    conn.commit()
    conn.close()


def test_monitor_start_returns_state_payload(authenticated_client, monkeypatch, _clear_worker_heartbeats):
    account_id = 1
    _seed_account(account_id, is_active=0)

    monkeypatch.setattr(simple_app, "start_imap_watcher_for_account", lambda aid: aid == account_id)
    simple_app.imap_threads[account_id] = _FakeThread(True)

    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO worker_heartbeats(worker_id, last_heartbeat, status) VALUES (?, datetime('now'), 'ok')",
        (f"imap_{account_id}",),
    )
    conn.commit()
    conn.close()

    resp = authenticated_client.post(f"/api/accounts/{account_id}/monitor/start")
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["ok"] is True
    assert data["state"] in {"running", "starting"}
    assert "detail" in data and isinstance(data["detail"], str)


def test_monitor_stop_returns_state_payload(authenticated_client, monkeypatch):
    account_id = 2
    _seed_account(account_id, is_active=1)

    def _stop_watcher(aid):
        simple_app.imap_threads[aid] = _FakeThread(False)

    monkeypatch.setattr(simple_app, "stop_imap_watcher_for_account", _stop_watcher)
    simple_app.imap_threads[account_id] = _FakeThread(True)

    resp = authenticated_client.post(f"/api/accounts/{account_id}/monitor/stop")
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["ok"] is True
    assert data["state"] in {"stopping", "stopped"}
    assert "detail" in data


def test_monitor_start_missing_credentials_returns_error(authenticated_client, _clear_worker_heartbeats):
    account_id = 3
    _seed_account(account_id, is_active=0, with_credentials=False)

    conn = get_db()
    row = conn.execute("SELECT id FROM email_accounts WHERE id=?", (account_id,)).fetchone()
    conn.close()
    assert row is not None

    resp = authenticated_client.post(f"/api/accounts/{account_id}/monitor/start")
    data = resp.get_json()

    assert resp.status_code == 400
    assert data["ok"] is False
    assert "IMAP credentials" in data["detail"]
    assert data["state"] in {"unknown", "stopped"}
