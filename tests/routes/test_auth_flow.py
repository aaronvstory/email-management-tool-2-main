import sqlite3

from werkzeug.security import generate_password_hash

from app.utils.db import get_db


def _seed_admin_user(password: str = "admin123") -> None:
    conn = get_db()
    conn.execute("DELETE FROM users WHERE username = ?", ("admin",))
    conn.execute(
        """
        INSERT INTO users (id, username, password_hash, role)
        VALUES (1, ?, ?, 'admin')
        ON CONFLICT(id) DO UPDATE SET username=excluded.username, password_hash=excluded.password_hash, role=excluded.role
        """,
        ("admin", generate_password_hash(password),),
    )
    conn.commit()
    conn.close()


def test_login_redirects_to_dashboard_on_success(client):
    _seed_admin_user()
    resp = client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/dashboard")


def test_login_redirects_authenticated_users(authenticated_client):
    resp = authenticated_client.get("/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/dashboard")
