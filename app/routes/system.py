"""System status and diagnostics API endpoints."""

import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.utils.db import DB_PATH


system_bp = Blueprint('system', __name__)
_PROCESS_START_TS = time.time()


LOG_DIRS: List[str] = [
    os.path.join(os.getcwd(), 'logs'),
    os.path.join(os.getcwd(), 'app', 'logs')
]


def _query_system_status(key: str) -> Optional[str]:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        row = cur.execute("SELECT value FROM system_status WHERE key=? LIMIT 1", (key,)).fetchone()
        conn.close()
        if row and row['value']:
            return row['value']
    except Exception:
        return None
    return None


@system_bp.route('/api/system/summary')
@login_required
def api_system_summary():
    response: Dict[str, Any] = {
        'database_size_bytes': None,
        'uptime_seconds': int(max(time.time() - _PROCESS_START_TS, 0)),
        'uptime_since': None
    }

    try:
        if os.path.exists(DB_PATH):
            response['database_size_bytes'] = os.path.getsize(DB_PATH)
    except Exception:
        response['database_size_bytes'] = None

    uptime_value = _query_system_status('app_start_time')
    if uptime_value:
        response['uptime_since'] = uptime_value
        try:
            start_ts = datetime.fromisoformat(uptime_value.replace('Z', '+00:00'))
            delta = datetime.now(timezone.utc) - start_ts
            response['uptime_seconds'] = max(int(delta.total_seconds()), response['uptime_seconds'])
        except Exception:
            pass

    return jsonify(response)


@system_bp.route('/api/system/smtp-health')
@login_required
def api_smtp_health():
    listening = False
    last_selfcheck = _query_system_status('smtp_last_selfcheck')
    try:
        host = os.environ.get('SMTP_PROXY_HOST', '127.0.0.1')
        port = int(os.environ.get('SMTP_PROXY_PORT', '8587'))
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        listening = (s.connect_ex((host, port)) == 0)
        s.close()
    except Exception:
        listening = False
    return jsonify({'listening': listening, 'last_selfcheck': last_selfcheck})


@system_bp.route('/api/system/watchers/status')
@login_required
def api_watchers_status():
    limit_minutes = int(request.args.get('minutes', 3))
    limit_minutes = max(1, min(limit_minutes, 30))
    payload = []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cols = [row[1] for row in cur.execute("PRAGMA table_info(worker_heartbeats)").fetchall()]
        has_error = 'error_count' in cols
        select_cols = "worker_id, last_heartbeat, status" + (", error_count" if has_error else "")
        query = (
            f"SELECT {select_cols} "
            "FROM worker_heartbeats "
            "WHERE datetime(last_heartbeat) > datetime('now', ?) "
            "ORDER BY last_heartbeat DESC"
        )
        rows = cur.execute(query, (f'-{limit_minutes} minutes',)).fetchall()
        payload = [dict(r) for r in rows]
        conn.close()
    except Exception:
        pass
    return jsonify({'success': True, 'workers': payload})


@system_bp.route('/api/system/logs')
@login_required
def api_system_logs():
    """Return recent logs from DB if available, otherwise tail log files.
    Supports both JSON logs (logs/app.json.log) and text logs (logs/app.log).
    Filtering:
    - Excludes noisy "Logging initialized" lines
    - Respects ?min_level= (DEBUG|INFO|WARNING|ERROR|CRITICAL), default INFO
    - De-duplicates by message (keeps newest occurrence)
    """
    from collections import deque
    import json as _json
    import re

    limit = int(max(1, min(500, int(request.args.get('limit', 200)))))
    min_level = (request.args.get('min_level') or 'INFO').upper()
    level_rank = {'DEBUG': 10, 'INFO': 20, 'WARNING': 30, 'ERROR': 40, 'CRITICAL': 50}
    cutoff = level_rank.get(min_level, 20)

    def _passes_filters(rec: Dict[str, Any]) -> bool:
        msg = str(rec.get('message', ''))
        if 'Logging initialized' in msg:
            return False
        lvl = str(rec.get('level', 'INFO')).upper()
        rank = level_rank.get(lvl, 20)
        return rank >= cutoff

    # Keep all entries; only filter by level and remove init spam
    def _dedupe_newest_first(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return rows[:limit]

    # 1) Try database-backed logs first (opt-out via ?source=file)
    if (request.args.get('source') or '').lower() != 'file':
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT timestamp, level, message, source
                FROM system_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,)
            )
            db_rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            if db_rows:
                filtered = [r for r in db_rows if _passes_filters(r)]
                if filtered:
                    return jsonify({'logs': filtered})
        except Exception:
            pass

    # 2) Fallback: tail JSON log file
    def _read_json_log(path: str, n: int):
        out = []
        try:
            dq = deque(maxlen=n)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    dq.append(line.strip())
            for line in dq:
                if not line:
                    continue
                try:
                    obj = _json.loads(line)
                    out.append({
                        'timestamp': obj.get('timestamp'),
                        'level': obj.get('level'),
                        'message': obj.get('message'),
                        'source': obj.get('logger') or obj.get('module')
                    })
                except Exception:
                    continue
        except Exception:
            return []
        return out

    # 3) Fallback: tail text log file
    _TEXT_RE = re.compile(r"^(?P<ts>[^ ]+\s+[^ ]+)\s+(?P<level>[A-Z]+)\s+\[(?P<src>[^\]]+)\]\s+(?P<msg>.*)$")

    def _read_text_log(path: str, n: int):
        out = []
        try:
            dq = deque(maxlen=n)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    dq.append(line.rstrip('\n'))
            for line in dq:
                m = _TEXT_RE.match(line)
                if not m:
                    continue
                out.append({
                    'timestamp': m.group('ts'),
                    'level': m.group('level'),
                    'message': m.group('msg'),
                    'source': m.group('src')
                })
        except Exception:
            return []
        return out

    files_to_check = []
    for d in LOG_DIRS:
        files_to_check.append(os.path.join(d, 'app.json.log'))
        files_to_check.append(os.path.join(d, 'app.log'))

    # Prefer JSON log if present
    for p in files_to_check:
        if p.endswith('app.json.log') and os.path.exists(p):
            json_rows = _read_json_log(p, limit)
            if json_rows:
                json_rows = [r for r in json_rows if _passes_filters(r)]
                json_rows = _dedupe_newest_first(list(reversed(json_rows)))
                return jsonify({'logs': json_rows})

    # Otherwise try text log
    for p in files_to_check:
        if p.endswith('app.log') and os.path.exists(p):
            text_rows = _read_text_log(p, limit)
            if text_rows:
                text_rows = [r for r in text_rows if _passes_filters(r)]
                text_rows = _dedupe_newest_first(list(reversed(text_rows)))
                return jsonify({'logs': text_rows})

    # Nothing found
    return jsonify({'logs': []})
