"""Audit Logging Service - Phase 1B Core Modularization

Extracted from simple_app.py lines 71-90
Provides lightweight audit logging for user actions

Best-effort logging - failures are silently caught to preserve
application functionality (matches original monolith behavior).
"""
import sqlite3
from datetime import datetime, timezone
from app.utils.db import DB_PATH


def log_action(action_type, user_id, email_id, message):
    """Log user action to audit_log table

    Args:
        action_type: Type of action (LOGIN, LOGOUT, APPROVE, REJECT, etc.)
        user_id: ID of user performing action
        email_id: ID of email being acted upon (None for auth actions)
        message: Human-readable description of action

    Returns:
        None (failures silently caught)

    Example:
        >>> log_action('LOGIN', 1, None, "User admin logged in")
        >>> log_action('APPROVE', 1, 42, "Email approved by admin")
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # Ensure audit_log table exists (idempotent)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                user_id INTEGER,
                email_id INTEGER,
                message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert audit record
        cur.execute(
            """
            INSERT INTO audit_log (action_type, user_id, email_id, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (action_type, user_id, email_id, message, datetime.now(timezone.utc).isoformat()),
        )

        conn.commit()
        conn.close()
    except Exception:
        # Silent failure preserves behavior from monolith
        # Audit logging is best-effort and should never break application flow
        pass


def get_recent_logs(limit=100):
    """Retrieve recent audit log entries

    Args:
        limit: Maximum number of logs to return (default 100)

    Returns:
        list: List of audit log records as dicts

    Example:
        >>> logs = get_recent_logs(limit=50)
        >>> for log in logs:
        ...     print(f"{log['action_type']}: {log['message']}")
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        logs = cur.execute("""
            SELECT id, action_type, user_id, email_id, message, created_at
            FROM audit_log
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        conn.close()
        return [dict(log) for log in logs]
    except Exception:
        return []
