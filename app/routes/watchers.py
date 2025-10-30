"""Watchers & Settings management UI and APIs.

Provides:
- /watchers page with per-account IMAP watcher status and controls
- /api/watchers/overview for status JSON (IMAP + SMTP summary)
- /settings page for runtime-configurable flags with descriptions
- /api/settings GET/POST to view/update flag overrides (stored in DB)

Notes:
- IMAP controls reuse existing accounts API: /api/accounts/<id>/monitor/(start|stop|restart)
- SMTP is presented as a service with health checks (restart not yet implemented)
"""
from __future__ import annotations

import os
import socket
import sqlite3
from typing import Dict, Any

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user

from app.utils.db import DB_PATH


watchers_bp = Blueprint('watchers', __name__)


def _smtp_health() -> Dict[str, Any]:
    host = os.environ.get('SMTP_PROXY_HOST', '127.0.0.1')
    port = int(os.environ.get('SMTP_PROXY_PORT', '8587'))
    ok = False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        ok = (s.connect_ex((host, port)) == 0)
        s.close()
    except Exception:
        ok = False
    last_sc = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        row = cur.execute("SELECT value FROM system_status WHERE key='smtp_last_selfcheck' LIMIT 1").fetchone()
        if row and row['value']:
            last_sc = row['value']
        conn.close()
    except Exception:
        pass
    return {'listening': ok, 'host': host, 'port': port, 'last_selfcheck_ts': last_sc}


@watchers_bp.route('/watchers')
@login_required
def watchers_page():
    return render_template('watchers.html')


@watchers_bp.route('/api/watchers/overview')
@login_required
def api_watchers_overview():
    """Combine account list with recent heartbeats and SMTP health."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    accounts = [dict(r) for r in cur.execute(
        """
        SELECT id, account_name, email_address, is_active
        FROM email_accounts
        ORDER BY account_name
        """
    ).fetchall()]
    # Map heartbeats
    hb = {}
    try:
        rows = cur.execute(
            """
            SELECT worker_id, last_heartbeat, status, 
                   CASE WHEN instr(worker_id, 'imap_')=1 THEN substr(worker_id, 6) ELSE NULL END AS acct
            FROM worker_heartbeats
            WHERE datetime(last_heartbeat) > datetime('now','-3 minutes')
            ORDER BY last_heartbeat DESC
            """
        ).fetchall()
        for r in rows:
            try:
                acct_id = int(r['acct']) if r['acct'] else None
                if acct_id:
                    hb[acct_id] = {'status': r['status'], 'last_heartbeat': r['last_heartbeat']}
            except Exception:
                continue
    except Exception:
        pass
    conn.close()

    # Merge
    for a in accounts:
        w = hb.get(int(a['id']))
        a['watcher'] = {
            'state': (w['status'] if w else ('stopped' if not a['is_active'] else 'unknown')),
            'last_heartbeat': (w['last_heartbeat'] if w else None),
            'is_active': bool(a['is_active'])
        }

    return jsonify({'success': True, 'smtp': _smtp_health(), 'accounts': accounts})


@watchers_bp.route('/api/stats-quick-validate')
@login_required
def api_stats_quick_validate():
    """Quick E2E counts check against DB to compare with UI displayed stats."""
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        row = cur.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) AS pending,
              SUM(CASE WHEN interception_status='HELD' THEN 1 ELSE 0 END) AS held,
              SUM(CASE WHEN interception_status='RELEASED' OR status IN ('APPROVED','DELIVERED') THEN 1 ELSE 0 END) AS released,
              SUM(CASE WHEN status='REJECTED' THEN 1 ELSE 0 END) AS rejected
            FROM email_messages
            WHERE (direction IS NULL OR direction!='outbound')
            """
        ).fetchone()
        conn.close()
        return jsonify({'success': True, 'counts': {k: int(row[k] or 0) for k in row.keys()}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------- Settings -------------------

_KNOWN_FLAGS: Dict[str, Dict[str, Any]] = {
    'ENABLE_WATCHERS': {
        'type': 'bool', 'default': True,
        'desc': 'Enable/disable all IMAP watchers globally.'
    },
    'IMAP_IDLE_TIMEOUT': {
        'type': 'int', 'default': 1500,
        'desc': 'Seconds before breaking IMAP IDLE to keep session alive.'
    },
    'IMAP_IDLE_PING_INTERVAL': {
        'type': 'int', 'default': 840,
        'desc': 'Seconds between periodic IDLE breaks for opportunistic polling.'
    },
    'EMAIL_CONN_TIMEOUT': {
        'type': 'int', 'default': 15,
        'desc': 'TCP connection timeout for IMAP in seconds.'
    },
    'IMAP_FORCE_COPY_PURGE': {
        'type': 'bool', 'default': False,
        'desc': 'Force COPY+DELETE+EXPUNGE instead of MOVE (provider compatibility).'
    },
    'IMAP_SWEEP_LAST_N': {
        'type': 'int', 'default': 50,
        'desc': 'During scans, also inspect the last N UIDs for missed messages.'
    },
    'IMAP_MARK_SEEN_QUARANTINE': {
        'type': 'bool', 'default': True,
        'desc': 'Mark messages as Seen in Quarantine to reduce unread badges.'
    },
    'IMAP_QUARANTINE_PREFERENCE': {
        'type': 'str', 'default': 'auto',
        'desc': 'Prefer quarantine folder naming: auto | inbox | plain.'
    },
    'IMAP_LOG_VERBOSE': {
        'type': 'bool', 'default': False,
        'desc': 'Increase watcher logs for troubleshooting (more INFO logs).'
    },
    'IMAP_CIRCUIT_THRESHOLD': {
        'type': 'int', 'default': 5,
        'desc': 'Consecutive failures before auto-disabling an account watcher.'
    },
    'SMTP_PROXY_HOST': {
        'type': 'str', 'default': '127.0.0.1',
        'desc': 'SMTP proxy bind host.'
    },
    'SMTP_PROXY_PORT': {
        'type': 'int', 'default': 8587,
        'desc': 'SMTP proxy port.'
    },
}


def _read_settings() -> Dict[str, Any]:
    # Load DB overrides
    db_overrides: Dict[str, str] = {}
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value TEXT)")
        for r in cur.execute("SELECT key, value FROM system_settings").fetchall():
            db_overrides[r['key']] = r['value']
        conn.close()
    except Exception:
        pass
    # Merge defaults -> env -> db
    result: Dict[str, Any] = {}
    for k, meta in _KNOWN_FLAGS.items():
        val: Any = meta['default']
        if k in os.environ and os.environ.get(k) is not None:
            env_val = os.environ.get(k)
            try:
                if meta['type'] == 'bool':
                    val = str(env_val).lower() in ('1','true','yes','on')
                elif meta['type'] == 'int':
                    val = int(env_val)  # type: ignore[assignment]
                else:
                    val = env_val
            except Exception:
                val = env_val
        if k in db_overrides:
            dv = db_overrides[k]
            try:
                if meta['type'] == 'bool':
                    val = str(dv).lower() in ('1','true','yes','on')
                elif meta['type'] == 'int':
                    val = int(dv)
                else:
                    val = dv
            except Exception:
                val = dv
        result[k] = val
    return result


@watchers_bp.route('/settings')
@login_required
def settings_page():
    return render_template('settings.html', settings=_read_settings(), meta=_KNOWN_FLAGS)


@watchers_bp.route('/api/settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    if request.method == 'GET':
        s = _read_settings()
        payload = []
        for k, v in s.items():
            payload.append({'key': k, 'value': v, 'type': _KNOWN_FLAGS[k]['type'], 'desc': _KNOWN_FLAGS[k]['desc']})
        return jsonify({'success': True, 'settings': payload})

    # POST: save overrides and update process env; restarting watchers recommended
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    data = request.get_json(silent=True) or {}
    updates = data.get('settings') or {}
    if not isinstance(updates, dict):
        return jsonify({'success': False, 'error': 'Invalid payload'}), 400
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value TEXT)")
        for k, v in updates.items():
            if k not in _KNOWN_FLAGS:
                continue
            # Persist textual value
            text_v = str(v)
            cur.execute("INSERT OR REPLACE INTO system_settings(key, value) VALUES(?,?)", (k, text_v))
            # Also update runtime environment to affect new connections
            os.environ[k] = text_v
        conn.commit(); conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': True})
