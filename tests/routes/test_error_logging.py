"""Tests that key error handlers emit structured logging for failure paths."""

import logging
import sqlite3

from app.utils.crypto import encrypt_credential


class _FakeIMAPStartTLSFailure:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def starttls(self):
        raise RuntimeError('STARTTLS negotiation failed')

    def login(self, username, password):
        return 'OK', []

    def select(self, mailbox):
        return 'OK', [b'']

    def uid(self, command, *args):
        if command == 'SEARCH':
            return 'OK', [b'']
        return 'OK', []

    def logout(self):
        return 'BYE', []


class _FailingIMAPRelease:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def login(self, username, password):  # pragma: no cover - simple failure path
        raise RuntimeError('Login rejected')

    def logout(self):
        return 'BYE', []


def _insert_account(conn: sqlite3.Connection, *, account_id: int) -> None:
    encrypted_password = encrypt_credential('password123')
    email = f'tester{account_id}@example.com'
    conn.execute(
        """
        INSERT INTO email_accounts (
            id, email_address, imap_host, imap_port, imap_username, imap_password,
            imap_use_ssl, smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_ssl, is_active
        )
        VALUES (?, ?, 'imap.example.com', 143, ?, ?, 0,
                'smtp.example.com', 587, ?, ?, 0, 1)
        """,
        (
            account_id,
            email,
            email,
            encrypted_password,
            email,
            encrypted_password,
        ),
    )


def test_fetch_emails_logs_starttls_failure(monkeypatch, client, test_db_path, caplog):
    account_id = 101
    from app.utils.db import get_db
    with get_db() as conn:
        _insert_account(conn, account_id=account_id)
        conn.commit()

    monkeypatch.setattr('app.routes.emails.DB_PATH', test_db_path, raising=False)
    monkeypatch.setattr('app.routes.emails.imaplib.IMAP4', _FakeIMAPStartTLSFailure)

    caplog.set_level(logging.WARNING, logger='app.routes.emails')

    client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)

    response = client.post('/api/fetch-emails', json={'account_id': account_id})

    assert response.status_code == 200
    assert any('STARTTLS failed' in record.message for record in caplog.records)


def test_release_logs_imap_failure(monkeypatch, client, test_db_path, caplog):
    from app.utils.db import get_db
    with get_db() as conn:
        _insert_account(conn, account_id=2)
        cursor = conn.execute(
            """
            INSERT INTO email_messages (
                account_id, direction, interception_status, status, subject, body_text, raw_content
            )
            VALUES (2, 'inbound', 'HELD', 'PENDING', 'Subject', 'Body', ?)
            """,
            ('Raw email content',),
        )
        email_id = cursor.lastrowid
        conn.commit()

    monkeypatch.setattr('app.routes.interception.imaplib.IMAP4_SSL', _FailingIMAPRelease)

    caplog.set_level(logging.ERROR, logger='app.routes.interception')

    client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)

    response = client.post(f'/api/interception/release/{email_id}', json={})

    assert response.status_code == 500
    # Accept either log message variant (append failed or runtime failure)
    assert any('[interception::release] append failed' in record.message or '[interception::release] runtime failure' in record.message for record in caplog.records)
