import os
import sqlite3
from datetime import datetime, timezone

import pytest

from simple_app import app


EMAIL_TABLE_SQL = """
CREATE TABLE email_messages (
    id INTEGER PRIMARY KEY,
    account_id INTEGER,
    interception_status TEXT,
    status TEXT,
    quarantine_folder TEXT,
    action_taken_at TEXT,
    created_at TEXT,
    original_uid INTEGER,
    message_id TEXT,
    subject TEXT,
    raw_content BLOB,
    direction TEXT
)
"""


ACCOUNT_TABLE_SQL = """
CREATE TABLE email_accounts (
    id INTEGER PRIMARY KEY,
    imap_host TEXT,
    imap_port INTEGER,
    imap_username TEXT,
    imap_password TEXT,
    is_active INTEGER DEFAULT 1
)
"""


USERS_TABLE_SQL = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    password_hash TEXT
)
"""


class FakeIMAP:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.mailbox = 'INBOX'

    def starttls(self):
        return 'OK', []

    def login(self, username, password):
        return 'OK', []

    def select(self, mailbox='INBOX'):
        self.mailbox = mailbox
        return 'OK', [b'']

    def uid(self, *args, **kwargs):
        return 'OK', [b'123']

    def logout(self):
        return 'OK', []


def _setup_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(EMAIL_TABLE_SQL)
    conn.execute(ACCOUNT_TABLE_SQL)
    conn.execute(USERS_TABLE_SQL)
    conn.execute(
        """
        INSERT INTO users (id, username, password_hash)
        VALUES (1, 'admin', 'hash')
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = tmp_path / 'manual_intercept.db'
    _setup_db(str(db_path))
    monkeypatch.setenv('TEST_DB_PATH', str(db_path))
    yield str(db_path)


@pytest.fixture
def client(test_db):
    app.config['TESTING'] = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['_user_id'] = '1'
            sess['_fresh'] = True
        yield client


def _insert_email(db_path: str, *, interception_status: str = 'FETCHED') -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO email_accounts (id, imap_host, imap_port, imap_username, imap_password, is_active)
        VALUES (1, 'imap.test', 993, 'user@test', 'encrypted', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO email_messages (id, account_id, interception_status, status, quarantine_folder, action_taken_at, created_at, original_uid, message_id, subject, raw_content, direction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            100,
            1,
            interception_status,
            'PENDING',
            None,
            None,
            datetime.now(timezone.utc).isoformat(),
            456,
            '<test-message-id>',
            'Manual intercept test',
            b'raw',
            'inbound',
        ),
    )
    conn.commit()
    conn.close()


def _query_message(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT interception_status, quarantine_folder FROM email_messages WHERE id=100').fetchone()
    conn.close()
    return row


def test_manual_intercept_sets_held_on_success(client, test_db, monkeypatch):
    _insert_email(test_db)

    called = {}

    monkeypatch.setattr('app.routes.interception.decrypt_credential', lambda _: 'secret')
    monkeypatch.setattr('app.routes.interception._ensure_quarantine', lambda *args, **kwargs: 'Quarantine')
    monkeypatch.setattr('app.routes.interception._move_uid_to_quarantine', lambda *args, **kwargs: called.setdefault('moved', True))
    monkeypatch.setattr('imaplib.IMAP4_SSL', FakeIMAP)
    monkeypatch.setattr('imaplib.IMAP4', FakeIMAP)

    response = client.post('/api/email/100/intercept')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['remote_move'] is True

    row = _query_message(test_db)
    assert row['interception_status'] == 'HELD'
    assert row['quarantine_folder'] == 'Quarantine'


def test_manual_intercept_returns_error_when_move_fails(client, test_db, monkeypatch):
    _insert_email(test_db, interception_status='FETCHED')

    monkeypatch.setattr('app.routes.interception.decrypt_credential', lambda _: 'secret')
    monkeypatch.setattr('app.routes.interception._ensure_quarantine', lambda *args, **kwargs: 'Quarantine')
    monkeypatch.setattr('app.routes.interception._move_uid_to_quarantine', lambda *args, **kwargs: False)
    monkeypatch.setattr('imaplib.IMAP4_SSL', FakeIMAP)
    monkeypatch.setattr('imaplib.IMAP4', FakeIMAP)

    response = client.post('/api/email/100/intercept')
    assert response.status_code == 409
    payload = response.get_json()
    assert payload['success'] is False

    row = _query_message(test_db)
    assert row['interception_status'] == 'FETCHED'
