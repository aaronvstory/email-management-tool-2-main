import sqlite3

import pytest

from app.utils import db


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE email_messages (id INTEGER PRIMARY KEY, account_id INTEGER, status TEXT, interception_status TEXT, direction TEXT)")
    conn.execute("CREATE TABLE moderation_rules (id INTEGER PRIMARY KEY, is_active INTEGER)")
    conn.execute("CREATE TABLE worker_heartbeats (worker_id TEXT PRIMARY KEY)")
    return conn


def test_maybe_conn_uses_provided_connection(memory_conn):
    with db.maybe_conn(memory_conn) as conn:
        conn.execute("INSERT INTO email_messages (account_id, status) VALUES (1, 'PENDING')")
    row = memory_conn.execute("SELECT COUNT(*) FROM email_messages").fetchone()
    assert row[0] == 1


def test_maybe_conn_creates_connection(monkeypatch):
    created = []

    def fake_get_db():
        created.append(":memory:")
        return sqlite3.connect(":memory:")

    monkeypatch.setattr(db, "get_db", fake_get_db)
    with db.maybe_conn(None) as conn:
        conn.execute("CREATE TABLE test (id INTEGER)")
    assert len(created) == 1


def test_table_exists(memory_conn):
    memory_conn.execute("CREATE TABLE sample_table (id INTEGER)")
    assert db.table_exists("sample_table", conn=memory_conn) is True
    assert db.table_exists("missing_table", conn=memory_conn) is False


def test_fetch_counts_basic(memory_conn):
    memory_conn.execute("DELETE FROM email_messages")
    memory_conn.executemany(
        "INSERT INTO email_messages (account_id, status, interception_status, direction) VALUES (?,?,?,?)",
        [
            (1, "PENDING", "HELD", "inbound"),
            (1, "APPROVED", "RELEASED", "inbound"),
            (2, "SENT", "HELD", "outbound"),
        ],
    )
    counts = db.fetch_counts(conn=memory_conn)
    assert counts == {"total": 2, "pending": 1, "approved": 1, "rejected": 0, "sent": 0, "held": 1, "released": 1, "discarded": 0}


def test_fetch_counts_includes_outbound(memory_conn):
    memory_conn.execute("DELETE FROM email_messages")
    memory_conn.execute("INSERT INTO email_messages (account_id, status, interception_status, direction) VALUES (3, 'SENT', 'RELEASED', 'outbound')")
    counts = db.fetch_counts(conn=memory_conn, include_outbound=True)
    assert counts["sent"] == 1


def test_fetch_by_statuses(memory_conn):
    memory_conn.execute("DELETE FROM email_messages")
    memory_conn.executemany(
        "INSERT INTO email_messages (account_id, status) VALUES (?,?)",
        [(1, "PENDING"), (2, "DELIVERED"), (3, "PENDING")],
    )
    rows = db.fetch_by_statuses(["PENDING"], conn=memory_conn)
    assert len(rows) == 2


def test_fetch_by_interception(memory_conn):
    memory_conn.execute("DELETE FROM email_messages")
    memory_conn.executemany(
        "INSERT INTO email_messages (account_id, interception_status) VALUES (?,?)",
        [(1, "HELD"), (1, "RELEASED"), (2, "HELD")],
    )
    rows = db.fetch_by_interception(["HELD"], conn=memory_conn)
    assert len(rows) == 2
