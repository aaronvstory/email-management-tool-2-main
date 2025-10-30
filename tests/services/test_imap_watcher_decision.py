import sqlite3
from datetime import datetime, timezone
from email.message import EmailMessage

import pytest

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


def _make_email(subject: str, body: str, *, sender: str = 'raywecuya@gmail.com', to: str = 'user@example.com') -> bytes:
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = to
    msg['Subject'] = subject
    msg['Message-ID'] = f"<{subject.replace(' ', '_')}@example.com>"
    msg.set_content(body)
    return msg.as_bytes()


class FakeClient:
    def __init__(self, fetch_map):
        self.fetch_map = fetch_map

    def fetch(self, uids, _parts):
        return {uid: self.fetch_map[uid] for uid in uids}


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = tmp_path / 'imap_watcher.db'
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
    monkeypatch.setenv('TEST_DB_PATH', str(db_path))
    yield str(db_path)


def test_store_in_database_returns_only_rule_matched_uids(test_db, monkeypatch):
    held_email = _make_email('Invoice update', 'Please review invoice ASAP')
    normal_email = _make_email('Hello', 'General update')
    now = datetime.now(timezone.utc)

    fetch_map = {
        1: {b'RFC822': held_email, b'INTERNALDATE': now},
        2: {b'RFC822': normal_email, b'INTERNALDATE': now},
    }
    client = FakeClient(fetch_map)

    def fake_eval(subject=None, body_text=None, sender=None, recipients=None, db_path=None):
        should_hold = 'invoice' in (subject or '').lower() or 'invoice' in (body_text or '').lower()
        return {
            'matched_rules': [{'id': 1, 'rule_name': 'Hold invoices', 'action': 'HOLD', 'priority': 10}] if should_hold else [],
            'risk_score': 10 if should_hold else 0,
            'keywords': ['invoice'] if should_hold else [],
            'actions': ['HOLD'] if should_hold else [],
            'should_hold': should_hold,
        }

    monkeypatch.setattr('app.services.imap_watcher.evaluate_rules', fake_eval)

    cfg = AccountConfig(
        imap_host='imap.test',
        username='user@test',
        password='secret',
        account_id=3,
        db_path=test_db,
    )
    watcher = ImapWatcher(cfg)

    held_uids = watcher._store_in_database(client, [1, 2])
    assert sorted(held_uids) == [1]

    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    rows = {
        row['original_uid']: row
        for row in conn.execute('SELECT original_uid, interception_status FROM email_messages')
    }
    conn.close()

    assert rows[1]['interception_status'] == 'INTERCEPTED'
    assert rows[2]['interception_status'] == 'FETCHED'


def test_update_message_status_sets_held_and_pending(test_db):
    conn = sqlite3.connect(test_db)
    conn.execute(
        """
        INSERT INTO email_messages (
            message_id, sender, recipients, subject, body_text, body_html, raw_content,
            account_id, interception_status, direction, original_uid, original_internaldate,
            original_message_id, risk_score, keywords_matched, created_at, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
        """,
        (
            'mid-1', 'sender@example.com', 'user@example.com', 'Invoice update', 'Body', '', b'raw',
            3, 'INTERCEPTED', 'inbound', 42, None, 'mid-1', 5, '[]', 'PENDING'
        ),
    )
    conn.commit()
    conn.close()

    cfg = AccountConfig(
        imap_host='imap.test',
        username='user@test',
        password='secret',
        account_id=3,
        db_path=test_db,
    )
    watcher = ImapWatcher(cfg)
    watcher._update_message_status([42], 'HELD')

    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        'SELECT interception_status, status, quarantine_folder FROM email_messages WHERE original_uid=?',
        (42,),
    ).fetchone()
    conn.close()

    assert row['interception_status'] == 'HELD'
    assert row['status'] == 'PENDING'
    assert row['quarantine_folder'] == cfg.quarantine
