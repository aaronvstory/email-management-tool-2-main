"""
Resilient email API endpoints with defensive schema handling
Prevents 500 errors from schema drift or missing columns
"""
import sqlite3
from flask import Blueprint, jsonify, request, current_app as app
from app.utils.db import get_db

emails_api = Blueprint('emails_api', __name__)

def _table_and_columns(cur):
    """
    Try to find an emails-like table and map columns flexibly.
    Returns (table_name, available_columns_set, column_aliases_dict).
    """
    candidates = ['emails', 'email_messages', 'inbox_emails', 'email_queue']
    for t in candidates:
        try:
            cols = cur.execute(f"PRAGMA table_info({t})").fetchall()
        except sqlite3.OperationalError:
            continue
        if not cols:
            continue
        names = {c[1] for c in cols}  # column names
        # map common aliases -> normalized keys used by UI
        aliases = {
            'id': 'id',
            'subject': 'subject',
            'from_addr': 'sender',
            'sender': 'sender',
            'to_addr': 'recipient',
            'recipient': 'recipient',
            'status': 'status',
            'created_at': 'ts',
            'received_at': 'ts',
            'ts': 'ts',
        }
        return t, names, aliases
    return None, set(), {}

def _serialize(row, names, aliases):
    """Serialize a database row to a consistent JSON structure"""
    out = {
        'id': row['id'] if 'id' in names else 0,
        'subject': row['subject'] if 'subject' in names else '(no subject)',
        'sender': row['sender'] if 'sender' in names else (row['from_addr'] if 'from_addr' in names else '(unknown)'),
        'recipient': row['recipient'] if 'recipient' in names else (row['to_addr'] if 'to_addr' in names else '(unknown)'),
        'status': row['status'] if 'status' in names else 'HELD',
        'ts': row['created_at'] if 'created_at' in names else (row['received_at'] if 'received_at' in names else (row['ts'] if 'ts' in names else '')),
    }
    return out

@emails_api.get("/api/emails/recent")
def emails_recent():
    """Get recent emails with defensive error handling"""
    limit = max(1, min(int(request.args.get('limit', 50)), 200))
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        table, names, aliases = _table_and_columns(cur)
        if not table:
            return jsonify(success=True, items=[], counts={'ALL': 0, 'HELD': 0, 'RELEASED': 0, 'REJECTED': 0})

        order_col = 'created_at' if 'created_at' in names else ('received_at' if 'received_at' in names else ('ts' if 'ts' in names else 'id'))
        rows = cur.execute(f"SELECT * FROM {table} ORDER BY {order_col} DESC LIMIT ?", (limit,)).fetchall()
        items = [_serialize(r, names, aliases) for r in rows]

        # cheap counts
        counts = {'ALL': len(items), 'HELD': 0, 'RELEASED': 0, 'REJECTED': 0}
        for it in items:
            s = (it.get('status') or '').upper()
            if s in counts:
                counts[s] += 1

        return jsonify(success=True, items=items, counts=counts)
    except Exception as e:
        app.logger.exception("emails_recent failed")
        return jsonify(success=False, error=str(e)), 500

@emails_api.get("/api/emails")
def emails_list():
    """List emails with filtering and pagination"""
    # same as /recent but accepts filter params: status, q, page, page_size
    try:
        status = (request.args.get('status') or 'ALL').upper()
        q = (request.args.get('q') or '').strip()
        page = max(1, int(request.args.get('page', 1)))
        page_size = max(1, min(int(request.args.get('page_size', 50)), 200))
        offset = (page - 1) * page_size

        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        table, names, aliases = _table_and_columns(cur)
        if not table:
            return jsonify(success=True, items=[], total=0, page=page, pages=1, counts={'ALL': 0, 'HELD': 0, 'RELEASED': 0, 'REJECTED': 0})

        order_col = 'created_at' if 'created_at' in names else ('received_at' if 'received_at' in names else ('ts' if 'ts' in names else 'id'))

        where = []
        args = []

        # status filter
        if status in ('HELD', 'RELEASED', 'REJECTED'):
            if 'status' in names:
                where.append('UPPER(status) = ?')
                args.append(status)

        # simple text search
        if q:
            parts = []
            if 'subject' in names: parts.append('subject LIKE ?')
            if 'from_addr' in names: parts.append('from_addr LIKE ?')
            if 'sender' in names: parts.append('sender LIKE ?')
            if 'to_addr' in names: parts.append('to_addr LIKE ?')
            if 'recipient' in names: parts.append('recipient LIKE ?')
            like = f"%{q}%"
            for _ in range(len(parts)):
                args.append(like)
            if parts:
                where.append('(' + ' OR '.join(parts) + ')')

        where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
        total = cur.execute(f"SELECT COUNT(*) AS c FROM {table}{where_sql}", tuple(args)).fetchone()['c']

        rows = cur.execute(
            f"SELECT * FROM {table}{where_sql} ORDER BY {order_col} DESC LIMIT ? OFFSET ?",
            (*args, page_size, offset)
        ).fetchall()

        items = [_serialize(r, names, aliases) for r in rows]
        pages = max(1, (total + page_size - 1) // page_size)

        # fast counts (within current page only, good enough for badges)
        counts = {'ALL': len(items), 'HELD': 0, 'RELEASED': 0, 'REJECTED': 0}
        for it in items:
            s = (it.get('status') or '').upper()
            if s in counts: counts[s] += 1

        return jsonify(success=True, items=items, total=total, page=page, pages=pages, counts=counts)
    except Exception as e:
        app.logger.exception("emails_list failed")
        return jsonify(success=False, error=str(e)), 500

@emails_api.post("/api/dev/seed_emails")
def dev_seed_emails():
    """Seed demo emails (dev only)"""
    if not app.debug:
        return jsonify(success=False, error="disabled"), 404
    try:
        conn = get_db()
        cur = conn.cursor()
        # Pick/ensure a table
        table, names, _ = _table_and_columns(conn.cursor())
        if not table:
            # create simplest table for demos
            cur.execute("""
              CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY,
                subject TEXT, from_addr TEXT, to_addr TEXT,
                status TEXT, created_at TEXT
              )
            """)
            table, names, _ = 'emails', {'id','subject','from_addr','to_addr','status','created_at'}, {}

        import datetime as dt
        now = dt.datetime.utcnow().isoformat(timespec='seconds')

        rows = [
            ('Welcome to Mail Ops', 'hello@example.com', 'you@example.com', 'HELD', now),
            ('Your invoice', 'billing@example.com', 'you@example.com', 'RELEASED', now),
            ('Suspicious login', 'security@example.com', 'you@example.com', 'REJECTED', now),
        ]
        cur.executemany(f"INSERT INTO {table} (subject, from_addr, to_addr, status, created_at) VALUES (?,?,?,?,?)", rows)
        conn.commit()
        return jsonify(success=True, inserted=len(rows))
    except Exception as e:
        app.logger.exception("seed failed")
        return jsonify(success=False, error=str(e)), 500
