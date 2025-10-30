import sqlite3

from app.routes import dashboard as dash
from app.utils.db import get_db
from tests.routes.test_interception_additional import _prepare_email, _login


def test_dashboard_overview_renders(client):
    _login(client)
    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    conn.execute("DELETE FROM email_accounts")
    _prepare_email(conn, email_id=201, account_id=301, status="HELD")
    conn.execute("INSERT OR IGNORE INTO moderation_rules (id, rule_name, is_active) VALUES (1, 'RuleOne', 1)")
    conn.commit()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"Dashboard" in resp.data


def test_dashboard_filters_by_account(client):
    _login(client)
    conn = get_db()
    conn.execute("DELETE FROM email_messages")
    conn.execute("DELETE FROM email_accounts")
    _prepare_email(conn, email_id=210, account_id=401, status="HELD")
    _prepare_email(conn, email_id=211, account_id=402, status="HELD")
    conn.commit()

    resp = client.get("/dashboard?account_id=401")
    assert resp.status_code == 200
    assert b"dashboard" in resp.data.lower()
