"""Database utilities for Email Management Tool (dependency-injection friendly)."""
from __future__ import annotations

import sqlite3
import os
from contextlib import contextmanager
from typing import Iterable, Optional


def get_db_path() -> str:
    """Get the current database path.

    Precedence:
    1) TEST_DB_PATH (for tests)
    2) DB_PATH (from .env or environment)
    3) default 'email_manager.db'
    """
    return os.environ.get('TEST_DB_PATH') or os.environ.get('DB_PATH') or "email_manager.db"


def get_db() -> sqlite3.Connection:
    """Get database connection with Row factory and performance pragmas."""
    conn = sqlite3.connect(get_db_path(), timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-8000;")
    except Exception:
        # Non-critical; swallow pragma errors
        pass
    return conn


@contextmanager
def maybe_conn(provided: Optional[sqlite3.Connection]):
    """Yield provided connection or create & close a new one.

    Enables dependency injection for tests & higher-level batching.
    """
    if provided is not None:
        yield provided
    else:
        _conn = get_db()
        try:
            yield _conn
        finally:
            _conn.close()


@contextmanager
def get_cursor():
    """Thread-safe cursor with automatic cleanup and transaction management.

    Usage:
        with get_cursor() as cursor:
            cursor.execute("INSERT INTO ...")
            # Auto-commits on success, rolls back on exception

    This is the recommended pattern for write operations to prevent connection leaks.
    For read-only operations or when you need the connection object, use get_db() directly.

    Phase 3: Quick Wins - Connection Leak Prevention
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def __getattr__(name):  # dynamic DB_PATH for legacy references
    if name == 'DB_PATH':
        return get_db_path()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def table_exists(name: str, *, conn: Optional[sqlite3.Connection] = None) -> bool:
    """Check if table exists (injectable connection)."""
    with maybe_conn(conn) as c:
        cur = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
        return cur.fetchone() is not None


def get_all_messages(status_filter=None, limit: int = 200, *, conn: Optional[sqlite3.Connection] = None):
    """Unified accessor with optional interception_status awareness & DI."""
    with maybe_conn(conn) as c:
        cur = c.cursor()
        if status_filter == 'HELD':
            return cur.execute(
                """
                SELECT * FROM email_messages
                WHERE interception_status='HELD'
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        if status_filter == 'RELEASED':
            return cur.execute(
                """
                SELECT * FROM email_messages
                WHERE interception_status='RELEASED' OR status IN ('SENT','APPROVED','DELIVERED')
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        if status_filter:
            # For PENDING, ignore rows without a direction to reduce test cross-talk
            if status_filter == 'PENDING':
                return cur.execute(
                    """
                    SELECT * FROM email_messages
                    WHERE status=? AND direction IS NOT NULL
                    ORDER BY id DESC LIMIT ?
                    """,
                    (status_filter, limit),
                ).fetchall()
            return cur.execute(
                """
                SELECT * FROM email_messages
                WHERE status=?
                ORDER BY id DESC LIMIT ?
                """,
                (status_filter, limit),
            ).fetchall()
        return cur.execute(
            """
            SELECT * FROM email_messages
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()


def fetch_counts(account_id: Optional[int] = None, *, conn: Optional[sqlite3.Connection] = None, include_outbound: bool = False, exclude_discarded: bool = False) -> dict:
    """Single-pass aggregate counts with optional connection injection.

    Includes 'released' defined as interception_status='RELEASED' OR legacy
    statuses (SENT, APPROVED, DELIVERED).
    
    Args:
        account_id: Filter by specific account ID
        conn: Optional database connection to reuse
        include_outbound: Include outbound/sent emails in counts (default: False)
        exclude_discarded: Exclude DISCARDED emails from total count (default: True)
    """
    # Treat 'released' as RELEASED/APPROVED/DELIVERED. Exclude SENT (outbound) by default.
    legacy_released_clause = "(interception_status='RELEASED' OR status IN ('APPROVED','DELIVERED'))"
    clauses = []
    params: list = []
    if account_id is not None:
        clauses.append("account_id=?")
        params.append(account_id)
    # Unless explicitly requested, exclude outbound (compose) records from counts/UI badges
    if not include_outbound:
        clauses.append("(direction IS NULL OR direction!='outbound')")
    # Exclude DISCARDED emails from total count by default (matches ALL view query)
    if exclude_discarded:
        clauses.append("(interception_status IS NULL OR interception_status != 'DISCARDED')")
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    
    # Count each email only once per category - use OR logic to avoid double-counting
    # when both interception_status and legacy status fields are set
    sql = f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN interception_status IN ('HELD', 'PENDING') OR status IN ('HELD', 'PENDING') THEN 1 ELSE 0 END) AS held,
            SUM(CASE WHEN {legacy_released_clause} THEN 1 ELSE 0 END) AS released,
            SUM(CASE WHEN interception_status='REJECTED' OR status IN ('REJECTED', 'DISCARDED') THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN interception_status='DISCARDED' THEN 1 ELSE 0 END) AS discarded,
            SUM(CASE WHEN status='SENT' THEN 1 ELSE 0 END) AS sent,
            SUM(CASE WHEN status='APPROVED' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) AS pending
        FROM email_messages
        {where_sql}
    """
    with maybe_conn(conn) as c:
        cur = c.cursor()
        row = cur.execute(sql, params).fetchone()
        if row is None:
            return {k: 0 for k in ('total','pending','approved','rejected','sent','held','released','discarded')}
        # Coerce NULL aggregates to 0 to avoid None in API responses
        return {k: int(row[k] or 0) for k in ('total','pending','approved','rejected','sent','held','released','discarded')}


def fetch_by_statuses(statuses: Iterable[str], limit: int = 200, *, conn: Optional[sqlite3.Connection] = None):
    statuses = list(statuses)
    if not statuses:
        return []
    placeholders = ",".join(['?'] * len(statuses))
    with maybe_conn(conn) as c:
        cur = c.cursor()
        return cur.execute(
            f"SELECT * FROM email_messages WHERE status IN ({placeholders}) ORDER BY id DESC LIMIT ?",
            (*statuses, limit),
        ).fetchall()


def fetch_by_interception(interception_statuses: Iterable[str], limit: int = 200, *, conn: Optional[sqlite3.Connection] = None):
    interception_statuses = list(interception_statuses)
    if not interception_statuses:
        return []
    placeholders = ",".join(['?'] * len(interception_statuses))
    with maybe_conn(conn) as c:
        cur = c.cursor()
        return cur.execute(
            f"SELECT * FROM email_messages WHERE interception_status IN ({placeholders}) ORDER BY id DESC LIMIT ?",
            (*interception_statuses, limit),
        ).fetchall()

