import os
import smtplib
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from email.message import EmailMessage
from uuid import uuid4

import pytest
from imapclient import IMAPClient

from app.services.imap_watcher import AccountConfig, ImapWatcher


EMAIL_TABLE_SQL = """
CREATE TABLE email_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT,
    sender TEXT,
    recipients TEXT,
    subject TEXT,
    body_text TEXT,
    body_html TEXT,
    raw_content BLOB,
    account_id INTEGER,
    interception_status TEXT,
    direction TEXT,
    original_uid INTEGER,
    original_internaldate TEXT,
    original_message_id TEXT,
    risk_score INTEGER,
    keywords_matched TEXT,
    created_at TEXT,
    status TEXT DEFAULT 'PENDING',
    quarantine_folder TEXT,
    action_taken_at TEXT,
    latency_ms INTEGER
);
"""


RULES_TABLE_SQL = """
CREATE TABLE moderation_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT,
    rule_type TEXT,
    condition_field TEXT,
    condition_operator TEXT,
    condition_value TEXT,
    action TEXT,
    priority INTEGER,
    is_active INTEGER DEFAULT 1
);
"""


def _create_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(EMAIL_TABLE_SQL)
    conn.execute(RULES_TABLE_SQL)
    conn.execute(
        """
        INSERT INTO moderation_rules (rule_name, rule_type, condition_field, condition_operator, condition_value, action, priority, is_active)
        VALUES ('Hold invoices', 'KEYWORD', 'BODY', 'CONTAINS', 'invoice', 'HOLD', 10, 1)
        """
    )
    conn.commit()
    conn.close()


def _build_email(subject: str, body: str, from_addr: str, to_addr: str) -> EmailMessage:
    msg = EmailMessage()
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg['Message-ID'] = f"<{uuid4()}@quarantine-test>"
    msg.set_content(body)
    return msg


@contextmanager
def _smtp_connection(host: str, port: int, *, use_ssl: bool, username: str, password: str):
    if use_ssl:
        server = smtplib.SMTP_SSL(host, port)
    else:
        server = smtplib.SMTP(host, port)
        server.ehlo()
        server.starttls()
    try:
        server.login(username, password)
        yield server
    finally:
        try:
            server.quit()
        except Exception:
            pass


def _require_env(var: str) -> str:
    value = os.getenv(var)
    if not value:
        raise RuntimeError(f"Environment variable {var} is required for live email tests")
    return value


@pytest.mark.live
def test_quarantine_flow_e2e(tmp_path, monkeypatch):
    if os.getenv('ENABLE_LIVE_EMAIL_TESTS', '0').lower() not in ('1', 'true', 'yes'):
        pytest.skip('ENABLE_LIVE_EMAIL_TESTS not enabled')

    account_choice = os.getenv('LIVE_EMAIL_ACCOUNT', 'gmail').lower()

    if account_choice == 'gmail':
        address = _require_env('GMAIL_ADDRESS')
        password = _require_env('GMAIL_PASSWORD')
        imap_host = 'imap.gmail.com'
        imap_port = 993
        use_ssl = True
        smtp_host = 'smtp.gmail.com'
        smtp_port = 587
        smtp_ssl = False
    elif account_choice == 'hostinger':
        address = _require_env('HOSTINGER_ADDRESS')
        password = _require_env('HOSTINGER_PASSWORD')
        imap_host = 'imap.hostinger.com'
        imap_port = 993
        use_ssl = True
        smtp_host = 'smtp.hostinger.com'
        smtp_port = 465
        smtp_ssl = True
    else:
        raise RuntimeError(f"Unsupported LIVE_EMAIL_ACCOUNT: {account_choice}")

    db_path = tmp_path / 'quarantine_live.db'
    _create_db(str(db_path))
    monkeypatch.setenv('TEST_DB_PATH', str(db_path))

    subject = f"Quarantine Flow {uuid4()}"
    body = 'Automated quarantine flow test with invoice keyword.'
    email_msg = _build_email(subject, f"{body}\nInvoice ID: {uuid4()}", address, address)

    with _smtp_connection(smtp_host, smtp_port, use_ssl=smtp_ssl, username=address, password=password) as server:
        server.send_message(email_msg)

    # Allow delivery time and poll IMAP for the new message
    client = IMAPClient(imap_host, port=imap_port, ssl=use_ssl)
    client.login(address, password)
    client.select_folder('INBOX', readonly=False)

    uid = None
    deadline = time.time() + 60
    while time.time() < deadline:
        ids = client.search(['SUBJECT', subject])
        if ids:
            uid = int(ids[-1])
            break
        time.sleep(5)
    if uid is None:
        client.logout()
        pytest.skip('Test email did not arrive in INBOX within timeout')

    cfg = AccountConfig(
        imap_host=imap_host,
        imap_port=imap_port,
        username=address,
        password=password,
        use_ssl=use_ssl,
        account_id=99,
        db_path=str(db_path),
    )
    watcher = ImapWatcher(cfg)
    watcher._client = client

    held_uids = watcher._store_in_database(client, [uid])
    assert held_uids == [uid]

    watcher._move(held_uids)
    watcher._update_message_status(held_uids, 'HELD')

    client.select_folder('INBOX', readonly=True)
    still_there = client.search(['UID', str(uid)])
    assert not still_there, 'Email should have been moved out of INBOX'

    quarantine_folder = watcher.cfg.quarantine
    client.select_folder(quarantine_folder, readonly=True)
    in_quarantine = client.search(['SUBJECT', subject])
    assert in_quarantine, 'Email should be present in Quarantine folder'

    # Check database state
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        'SELECT interception_status, status, quarantine_folder FROM email_messages WHERE original_uid=?',
        (uid,),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row['interception_status'] == 'HELD'
    assert row['status'] == 'PENDING'
    assert row['quarantine_folder'] == quarantine_folder

    # Cleanup: move message back to INBOX for subsequent runs
    try:
        client.select_folder(quarantine_folder, readonly=False)
        client.move(in_quarantine, 'INBOX')
    except Exception:
        pass
    finally:
        try:
            client.logout()
        except Exception:
            pass
