"""Account Management Blueprint - Phase 1B Route Modularization

Extracted from simple_app.py lines 877-1760
Routes: /accounts, /accounts/add, /api/accounts/*, /api/detect-email-settings, /api/test-connection
Phase 3: Consolidated email helpers - using app.utils.email_helpers
"""
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.exceptions import BadRequest
import sqlite3
import json
from app.utils.db import DB_PATH, get_db
from datetime import datetime
from app.utils.crypto import encrypt_credential, decrypt_credential
from app.extensions import limiter, csrf
import csv
from io import StringIO

# Phase 3: Import consolidated email helpers
from app.utils.email_helpers import (
    detect_email_settings as _detect_email_settings,
    test_email_connection as _test_email_connection,
    normalize_modes as _normalize_modes,
    negotiate_smtp as _negotiate_smtp,
    negotiate_imap as _negotiate_imap,
)
from email.message import EmailMessage
import time
import os
import imaplib
from typing import Optional

log = logging.getLogger(__name__)

accounts_bp = Blueprint('accounts', __name__)

# Safe int conversion helper
_def = object()

def _to_int(val, default=None):
    try:
        return int(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _compute_watcher_state(account_id: int, *, conn: Optional[sqlite3.Connection] = None) -> dict:
    """Inspect thread + DB state for a watcher and return diagnostic fields."""
    thread_alive = False
    try:
        from simple_app import imap_threads  # lazy import to avoid circular import on module load

        thread = imap_threads.get(account_id)
        thread_alive = bool(thread and thread.is_alive())
    except Exception as exc:  # pragma: no cover - defensive logging
        log.warning(
            "[accounts] Failed to inspect watcher thread",
            extra={'account_id': account_id, 'error': str(exc)},
        )

    should_close = conn is None
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
    else:
        conn.row_factory = sqlite3.Row

    try:
        row = conn.execute(
            "SELECT is_active, last_checked, last_error FROM email_accounts WHERE id=?",
            (account_id,),
        ).fetchone()
        heartbeat = conn.execute(
            "SELECT last_heartbeat, status FROM worker_heartbeats "
            "WHERE worker_id=? ORDER BY last_heartbeat DESC LIMIT 1",
            (f'imap_{account_id}',),
        ).fetchone()
    finally:
        if should_close:
            conn.close()

    if not row:
        detail = None
        if heartbeat and heartbeat['last_heartbeat']:
            detail = f"Last heartbeat {heartbeat['last_heartbeat']} (status={heartbeat.get('status') or 'unknown'})"
        return {
            'state': 'unknown',
            'is_active': False,
            'thread_alive': thread_alive,
            'last_heartbeat': heartbeat['last_heartbeat'] if heartbeat else None,
            'status': heartbeat['status'] if heartbeat else None,
            'last_error': None,
            'detail': detail or 'Account not found when computing watcher state',
        }

    is_active = bool(row['is_active'])
    if thread_alive and is_active:
        state = 'running'
    elif thread_alive and not is_active:
        state = 'stopping'
    elif not thread_alive and is_active:
        state = 'starting'
    else:
        state = 'stopped'

    detail: Optional[str]
    if row['last_error']:
        detail = f"Last error: {row['last_error']}"
    elif heartbeat and heartbeat['last_heartbeat']:
        detail = f"Last heartbeat {heartbeat['last_heartbeat']} (status={heartbeat.get('status') or 'unknown'})"
    else:
        detail = 'No recent heartbeat recorded'

    return {
        'state': state,
        'is_active': is_active,
        'thread_alive': thread_alive,
        'last_heartbeat': heartbeat['last_heartbeat'] if heartbeat else None,
        'status': heartbeat['status'] if heartbeat else None,
        'last_error': row['last_error'],
        'detail': detail,
    }


def _watcher_response(account_id: int, *, ok: bool, detail: Optional[str] = None, status_code: int = 200):
    """Compose standardized watcher API payload."""
    info = _compute_watcher_state(account_id)
    payload = {
        'success': bool(ok),
        'ok': bool(ok),
        'account_id': account_id,
        'state': info['state'],
        'watcher': info,
        'detail': detail or info.get('detail'),
    }
    return payload, status_code


@accounts_bp.route('/api/accounts')
@login_required
def api_get_accounts():
    """Get all email accounts (admin and diagnostics)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT id, account_name, email_address, is_active,
               smtp_host, smtp_port, imap_host, imap_port
        FROM email_accounts
        ORDER BY account_name
        """
    ).fetchall()
    conn.close()
    return jsonify({'success': True, 'accounts': [dict(r) for r in rows]})


@accounts_bp.route('/api/accounts/bulk-delete', methods=['POST'])
@csrf.exempt
@login_required
def api_accounts_bulk_delete():
    """Bulk delete email accounts by ids.
    Body: {"ids": [1,2,3]}
    """
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'error': 'No ids provided'}), 400
    # Normalize to ints and filter invalid
    try:
        id_list = [int(i) for i in ids if str(i).isdigit()]
    except (ValueError, TypeError) as e:
        log.warning(f"[accounts] Failed to parse account IDs: {e}")
        id_list = []
    if not id_list:
        return jsonify({'success': False, 'error': 'No valid ids provided'}), 400
    # Best-effort: stop watchers and clear heartbeats first
    try:
        from simple_app import stop_imap_watcher_for_account
        for aid in id_list:
            try:
                stop_imap_watcher_for_account(aid)
            except (RuntimeError, KeyError) as e:
                log.warning(f"[accounts] Failed to stop watcher for account {aid}: {e}")
    except Exception:
        pass
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        # Remove heartbeats for these accounts
        try:
            cur.executemany("DELETE FROM worker_heartbeats WHERE worker_id=?", [(f"imap_{aid}",) for aid in id_list])
        except sqlite3.Error as e:
            log.warning(f"[accounts] Failed to remove heartbeats for accounts {id_list}: {e}")
        # Delete accounts
        qmarks = ",".join(["?"] * len(id_list))
        cur.execute(f"DELETE FROM email_accounts WHERE id IN ({qmarks})", id_list)
        conn.commit()
        deleted = cur.rowcount if cur.rowcount is not None else len(id_list)
    finally:
        conn.close()
    return jsonify({'success': True, 'deleted': deleted, 'ids': id_list})


@accounts_bp.route('/api/accounts/<account_id>/health')
@login_required
def api_account_health(account_id):
    """Get real-time health status for an account (from DB fields)."""
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    account = cur.execute(
        """
        SELECT smtp_health_status, imap_health_status,
               last_health_check, last_error, connection_status
        FROM email_accounts WHERE id = ?
        """,
        (account_id,),
    ).fetchone()
    if not account:
        conn.close(); return jsonify({'error': 'Account not found'}), 404
    smtp_status = account['smtp_health_status'] or 'unknown'
    imap_status = account['imap_health_status'] or 'unknown'
    if smtp_status == 'connected' and imap_status == 'connected':
        overall = 'connected'
    elif smtp_status == 'error' or imap_status == 'error':
        overall = 'error'
    elif smtp_status == 'unknown' and imap_status == 'unknown':
        overall = 'unknown'
    else:
        overall = 'warning'
    conn.close()
    return jsonify({
        'overall': overall,
        'smtp': smtp_status,
        'imap': imap_status,
        'last_check': account['last_health_check'],
        'last_error': account['last_error']
    })


@accounts_bp.route('/api/accounts/<account_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_account_crud(account_id):
    """Account CRUD operations (sanitized; no decrypted secrets returned)."""
    if request.method == 'GET':
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        cur = conn.cursor(); acc = cur.execute("SELECT * FROM email_accounts WHERE id=?", (account_id,)).fetchone()
        if not acc:
            conn.close(); return jsonify({'error': 'Account not found'}), 404
        data = dict(acc); data.pop('imap_password', None); data.pop('smtp_password', None)
        conn.close(); return jsonify(data)

    if request.method == 'PUT':
        if current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        payload = request.get_json(silent=True) or {}
        conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
        fields, values = [], []
        for field in ['account_name','email_address','provider_type','smtp_host','smtp_port','smtp_username','imap_host','imap_port','imap_username']:
            if field in payload:
                fields.append(f"{field} = ?"); values.append(payload[field])
        if payload.get('smtp_password'):
            fields.append('smtp_password = ?'); values.append(encrypt_credential(payload['smtp_password']))
        if payload.get('imap_password'):
            fields.append('imap_password = ?'); values.append(encrypt_credential(payload['imap_password']))
        if 'smtp_use_ssl' in payload:
            fields.append('smtp_use_ssl = ?'); values.append(1 if payload['smtp_use_ssl'] else 0)
        if 'imap_use_ssl' in payload:
            fields.append('imap_use_ssl = ?'); values.append(1 if payload['imap_use_ssl'] else 0)
        if 'is_active' in payload:
            # Guard: cannot activate without valid (decrypted, non-empty) credentials
            desired_active = 1 if (payload['is_active'] in (1, True, '1')) else 0
            if desired_active:
                existing = cur.execute(
                    "SELECT imap_username, smtp_username, imap_password, smtp_password FROM email_accounts WHERE id=?",
                    (account_id,)
                ).fetchone()
                if not existing or not existing[0] or not existing[1]:
                    conn.close(); return jsonify({'error': 'Cannot activate account without credentials'}), 400
                from app.utils.crypto import decrypt_credential as _dec
                imap_pwd = _dec(existing[2]) if existing[2] else None
                smtp_pwd = _dec(existing[3]) if existing[3] else None
                if not imap_pwd or not smtp_pwd:
                    conn.close(); return jsonify({'error': 'Cannot activate: credentials invalid or missing'}), 400
            fields.append('is_active = ?'); values.append(desired_active)
        if fields:
            fields.append('updated_at = CURRENT_TIMESTAMP'); values.append(account_id)
            cur.execute(f"UPDATE email_accounts SET {', '.join(fields)} WHERE id = ?", values); conn.commit()
        conn.close(); return jsonify({'success': True})

    # DELETE
    if current_user.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("DELETE FROM email_accounts WHERE id=?", (account_id,)); conn.commit(); conn.close()
    return jsonify({'success': True})


@accounts_bp.route('/api/accounts/<int:account_id>/credentials', methods=['POST'])
@csrf.exempt
@login_required
def api_update_credentials(account_id: int):
    """Update account credentials (IMAP/SMTP passwords and usernames)."""
    if current_user.role != 'admin':
        return jsonify({'ok': False, 'success': False, 'error': 'Admin access required'}), 403

    # explicit JSON failure instead of silent ignore
    try:
        payload = request.get_json(force=False, silent=False) or {}
    except BadRequest:
        return jsonify({'ok': False, 'success': False, 'error': 'Invalid JSON payload'}), 400

    allowed = (
        ('imap_username', False),
        ('imap_password', True),
        ('smtp_username', False),
        ('smtp_password', True),
    )

    set_parts, values = [], []
    for key, encrypt in allowed:
        if key in payload and payload[key] is not None:
            set_parts.append(f'{key} = ?')
            values.append(encrypt_credential(payload[key]) if encrypt else payload[key])

    if not set_parts:
        return jsonify({'ok': False, 'success': False, 'error': 'No credentials provided'}), 400

    set_parts.append('updated_at = CURRENT_TIMESTAMP')
    values.append(account_id)
    sql = f"UPDATE email_accounts SET {', '.join(set_parts)} WHERE id = ?"

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(sql, values)
            conn.commit()
        return jsonify({'ok': True, 'success': True})
    except Exception as e:
        return jsonify({'ok': False, 'success': False, 'error': str(e)}), 500


@accounts_bp.route('/api/accounts/<int:account_id>/circuit/reset', methods=['POST'])
@csrf.exempt
@login_required
def api_reset_circuit(account_id: int):
    """Reset circuit breaker flags for an account (clear error states)."""
    if current_user.role != 'admin':
        return jsonify({'ok': False, 'success': False, 'error': 'Admin access required'}), 403

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE email_accounts
            SET last_error = NULL,
                connection_status = 'unknown',
                smtp_health_status = 'unknown',
                imap_health_status = 'unknown'
            WHERE id = ?
        """, (account_id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'success': True})
    except Exception as e:
        conn.close()
        return jsonify({'ok': False, 'success': False, 'error': str(e)}), 500


@accounts_bp.route('/api/accounts/<account_id>/test', methods=['POST'])
@limiter.limit("10 per minute")
@login_required
def api_test_account(account_id):
    """Test account IMAP/SMTP connectivity and update health fields."""
    if current_user.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    cur = conn.cursor(); acc = cur.execute("SELECT * FROM email_accounts WHERE id=?", (account_id,)).fetchone()
    if not acc:
        conn.close(); return jsonify({'error': 'Account not found'}), 404
    imap_pwd = decrypt_credential(acc['imap_password'])
    smtp_pwd = decrypt_credential(acc['smtp_password'])
    if not acc['imap_username'] or not imap_pwd:
        conn.close(); return jsonify({'success': False, 'imap': {'success': False, 'message': 'IMAP username/password required'}, 'smtp': {'success': False, 'message': 'SMTP test skipped'}}), 400
    if not acc['smtp_username'] or not smtp_pwd:
        conn.close(); return jsonify({'success': False, 'imap': {'success': False, 'message': 'IMAP test skipped'}, 'smtp': {'success': False, 'message': 'SMTP username/password required'}}), 400
    imap_ok, imap_msg = _test_email_connection('imap', str(acc['imap_host'] or ''), _to_int(acc['imap_port'], 993), str(acc['imap_username'] or ''), imap_pwd or '', bool(acc['imap_use_ssl']))
    smtp_ok, smtp_msg = _test_email_connection('smtp', str(acc['smtp_host'] or ''), _to_int(acc['smtp_port'], 465), str(acc['smtp_username'] or ''), smtp_pwd or '', bool(acc['smtp_use_ssl']))
    cur.execute(
        """
        UPDATE email_accounts
        SET smtp_health_status = ?, imap_health_status = ?,
            last_health_check = CURRENT_TIMESTAMP,
            connection_status = ?
        WHERE id = ?
        """,
        (
            'connected' if smtp_ok else 'error',
            'connected' if imap_ok else 'error',
            'connected' if (smtp_ok and imap_ok) else 'error',
            account_id,
        ),
    )
    if smtp_ok and imap_ok:
        cur.execute("UPDATE email_accounts SET last_successful_connection = CURRENT_TIMESTAMP WHERE id=?", (account_id,))
    conn.commit(); conn.close()
    return jsonify({'success': smtp_ok and imap_ok, 'imap': {'success': imap_ok, 'message': imap_msg}, 'smtp': {'success': smtp_ok, 'message': smtp_msg}})


@accounts_bp.route('/api/accounts/export')
@login_required
def api_export_accounts():
    """Export non-secret account configuration as JSON file."""
    if current_user.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT account_name, email_address, provider_type,
               imap_host, imap_port, imap_username, imap_use_ssl,
               smtp_host, smtp_port, smtp_username, smtp_use_ssl
        FROM email_accounts
        ORDER BY account_name
        """
    ).fetchall(); conn.close()
    export = {'version': '1.0', 'exported_at': datetime.now().isoformat(), 'accounts': [dict(r) for r in rows]}
    resp = jsonify(export); resp.headers['Content-Disposition'] = 'attachment; filename=email_accounts_export.json'
    return resp


@accounts_bp.route('/api/test-connection/<connection_type>', methods=['POST'])
@limiter.limit("10 per minute")
@login_required
def api_test_connection(connection_type):
    """Test IMAP/SMTP connectivity to an arbitrary host using provided params."""
    data = request.get_json(silent=True) or {}
    host = str(data.get('host') or '').strip(); port = _to_int(data.get('port'), None)
    username = str(data.get('username') or '').strip(); password = str(data.get('password') or '')
    use_ssl = bool(data.get('use_ssl', True))
    if not (host and port and username and password):
        return jsonify({'success': False, 'message': 'Missing parameters (host, port, username, password required)', 'error': 'Missing parameters'}), 400
    ok, msg = _test_email_connection(connection_type, host, int(port), username, password, use_ssl)
    return jsonify({'success': ok, 'message': msg, 'error': None if ok else msg})






@accounts_bp.route('/api/accounts/<int:account_id>/imap-live-test', methods=['POST'])
@login_required
def api_imap_live_test(account_id: int):
    """Append a probe email to INBOX and verify watcher quarantines it and DB row appears as HELD."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    cur = conn.cursor(); acc = cur.execute("SELECT * FROM email_accounts WHERE id=?", (account_id,)).fetchone()
    if not acc:
        conn.close(); return jsonify({'success': False, 'error': 'Account not found'}), 404
    host, port, user = acc['imap_host'], _to_int(acc['imap_port'], 993), acc['imap_username'] or acc['email_address']
    pwd = decrypt_credential(acc['imap_password']) if acc['imap_password'] else None
    if not (host and user):
        conn.close(); return jsonify({'success': False, 'error': 'IMAP credentials missing'}), 400
    if pwd is None:
        conn.close(); return jsonify({'success': False, 'error': 'IMAP credentials missing'}), 400
    log.debug("[accounts::probe] starting probe", extra={'account_id': account_id, 'host': host, 'port': port})
    # Build unique probe
    probe_id = f"probe-{account_id}-{int(time.time())}"
    msg = EmailMessage(); msg['From']=user; msg['To']=user; msg['Subject']=f"[EMT-PROBE] {probe_id}"; msg.set_content('probe')
    try:
        import imaplib, imaplib as _imap
        if port == 993:
            imap = imaplib.IMAP4_SSL(host, port)
        else:
            imap = imaplib.IMAP4(host, port)
            try: imap.starttls()
            except (imaplib.IMAP4.error, OSError) as e:
                log.warning("[accounts::probe] STARTTLS failed (non-SSL port, continuing)", extra={'account_id': account_id, 'error': str(e)})
        imap.login(user, pwd); imap.select('INBOX')
        import time as _t
        date_param = imaplib.Time2Internaldate(_t.localtime())
        imap.append('INBOX', '', date_param, msg.as_bytes())
        imap.logout()
        log.debug("[accounts::probe] appended probe message", extra={'account_id': account_id, 'probe_id': probe_id})
    except (imaplib.IMAP4.error, OSError) as e:
        log.error(f"[accounts::probe] IMAP append failed for account {account_id}: {e}")
        conn.close(); return jsonify({'success': False, 'error': f'IMAP append failed: {e}'}), 500
    # Poll for HELD entry in DB and verify server state
    ok=False; attempts=10; last=None
    while attempts>0 and not ok:
        row = cur.execute("""
            SELECT id, subject, interception_status FROM email_messages
            WHERE account_id=? AND subject LIKE ? AND interception_status='HELD'
            ORDER BY id DESC LIMIT 1
        """, (account_id, f"%{probe_id}%")).fetchone()
        if row:
            last = dict(row)
            # Double check IMAP: present in Quarantine, absent in INBOX
            try:
                port = _to_int(acc['imap_port'], 993)
                imap = imaplib.IMAP4_SSL(acc['imap_host'], port) if port==993 else imaplib.IMAP4(acc['imap_host'], port)
                try:
                    if port!=993: imap.starttls()
                except (imaplib.IMAP4.error, OSError):
                    pass
                imap_pwd = decrypt_credential(acc['imap_password']) if acc['imap_password'] else None
                if imap_pwd is None:
                    log.warning("[accounts::probe] decrypted password missing during verification", extra={'account_id': account_id})
                    break
                imap.login(acc['imap_username'] or acc['email_address'], imap_pwd)
                mid_hdr = last.get('subject') or f"[EMT-PROBE] {probe_id}"
                # INBOX absent
                imap.select('INBOX')
                typ1, d1 = imap.search(None, 'SUBJECT', f'"{mid_hdr}"')
                in_inbox = bool(d1 and d1[0] and len(d1[0].split())>0)
                # Quarantine present
                qname = os.getenv('IMAP_QUARANTINE_NAME', 'Quarantine')
                try:
                    imap.select(qname)
                except Exception:
                    try:
                        imap.select(f'INBOX.{qname}')
                    except Exception:
                        imap.select(f'INBOX/{qname}')
                typ2, d2 = imap.search(None, 'SUBJECT', f'"{mid_hdr}"')
                in_quar = bool(d2 and d2[0] and len(d2[0].split())>0)
                imap.logout()
                ok = (in_quar and not in_inbox)
                if ok:
                    log.info("[accounts::probe] probe quarantined successfully", extra={'account_id': account_id, 'probe_id': probe_id})
                    break
            except Exception:
                ok = False
        time.sleep(2); attempts-=1
    conn.close()
    return jsonify({'success': ok, 'result': last, 'probe_id': probe_id})


@accounts_bp.route('/api/accounts/<int:account_id>/scan-inbox')
@login_required
def api_scan_inbox(account_id: int):
    """List recent emails in INBOX that are not yet in our DB (subject + uid)."""
    n = _to_int(request.args.get('last'), 30) or 30
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    cur = conn.cursor(); acc = cur.execute("SELECT * FROM email_accounts WHERE id=?", (account_id,)).fetchone()
    if not acc:
        conn.close(); return jsonify({'success': False, 'error': 'Account not found'}), 404
    host, port, user = acc['imap_host'], _to_int(acc['imap_port'], 993), acc['imap_username'] or acc['email_address']
    pwd = decrypt_credential(acc['imap_password']) if acc['imap_password'] else None
    if not (host and user):
        conn.close(); return jsonify({'success': False, 'error': 'IMAP credentials missing'}), 400
    if pwd is None:
        conn.close(); return jsonify({'success': False, 'error': 'IMAP credentials missing'}), 400
    log.debug("[accounts::scan_inbox] scanning INBOX", extra={'account_id': account_id, 'limit': n})
    try:
        imap = imaplib.IMAP4_SSL(host, port) if port==993 else imaplib.IMAP4(host, port)
        try:
            if port!=993: imap.starttls()
        except Exception:
            pass
        imap.login(user, pwd); imap.select('INBOX')
        typ, data = imap.search(None, 'ALL')
        uids = []
        if typ=='OK' and data and data[0]:
            all_uids = [int(x) for x in data[0].split()]
            uids = all_uids[-n:]
        # Filter out those already in DB by original_uid
        res=[]
        if uids:
            placeholders = ','.join(['?']*len(uids))
            seen = set(x[0] for x in cur.execute(f"SELECT DISTINCT original_uid FROM email_messages WHERE account_id=? AND original_uid IN ({placeholders})", [account_id,*uids]).fetchall())
            to_show = [u for u in uids if u not in seen]
            if to_show:
                # Fetch ENVELOPE for subject
                for uid in to_show:
                    try:
                        typ2, d2 = imap.uid('FETCH', str(uid), '(ENVELOPE)')
                        subj = f'UID {uid}'
                        if typ2=='OK' and d2 and d2[0]:
                            s = str(d2[0])
                            # crude subject extract
                            if 'ENVELOPE' in s:
                                start = s.find('ENVELOPE')
                        res.append({'uid': uid, 'subject': subj})
                    except Exception:
                        res.append({'uid': uid, 'subject': f'UID {uid}'})
        imap.logout(); conn.close();
        log.debug("[accounts::scan_inbox] completed", extra={'account_id': account_id, 'candidates': len(res)})
        return jsonify({'success': True, 'candidates': res})
    except Exception as e:
        conn.close(); return jsonify({'success': False, 'error': str(e)}), 500


@accounts_bp.route('/api/accounts/<int:account_id>/intercept-uid', methods=['POST'])
@login_required
def api_intercept_uid(account_id: int):
    """Move a specific UID from INBOX to Quarantine and store it as HELD if not already recorded."""
    payload = request.get_json(silent=True) or {}
    uid = str(payload.get('uid') or '').strip()
    if not uid:
        return jsonify({'success': False, 'error': 'uid required'}), 400
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    cur = conn.cursor(); acc = cur.execute("SELECT * FROM email_accounts WHERE id=?", (account_id,)).fetchone()
    if not acc:
        conn.close(); return jsonify({'success': False, 'error': 'Account not found'}), 404
    host, port, user = acc['imap_host'], _to_int(acc['imap_port'], 993), acc['imap_username'] or acc['email_address']
    pwd = decrypt_credential(acc['imap_password']) if acc['imap_password'] else None
    if not (host and user and pwd):
        conn.close(); return jsonify({'success': False, 'error': 'IMAP credentials missing'}), 400
    try:
        imap = imaplib.IMAP4_SSL(host, port) if port==993 else imaplib.IMAP4(host, port)
        try:
            if port!=993: imap.starttls()
        except Exception:
            pass
        imap.login(user, pwd); imap.select('INBOX')
        # Fetch RFC822 for DB storage
        typ0, d0 = imap.uid('FETCH', uid, '(RFC822 INTERNALDATE)')
        raw_bytes = None; internal = None
        if typ0=='OK' and d0 and isinstance(d0[0], tuple):
            raw_bytes = d0[0][1]
        # Move or copy+delete
        moved=False
        try:
            typ1, _ = imap.uid('MOVE', uid, 'Quarantine')
            moved = (typ1=='OK')
        except Exception:
            try:
                typ2,_ = imap.uid('COPY', uid, 'Quarantine')
                if typ2=='OK':
                    imap.uid('STORE', uid, '+FLAGS', r'(\Deleted)'); imap.expunge(); moved=True
            except Exception:
                moved=False
        # Insert into DB if not present
        if raw_bytes:
            from email import message_from_bytes, policy as _pol
            emsg = message_from_bytes(raw_bytes, policy=_pol.default)
            orig_mid = (emsg.get('Message-ID') or '').strip() or None
            exists = None
            if orig_mid:
                exists = cur.execute('SELECT id FROM email_messages WHERE message_id=?', (orig_mid,)).fetchone()
            if not exists:
                sender = str(emsg.get('From','')); recips = str(emsg.get('To','') or '')
                import json as _json
                cur.execute('''
                    INSERT INTO email_messages
                    (message_id, sender, recipients, subject, body_text, body_html, raw_content,
                     account_id, interception_status, direction, original_uid, original_message_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'HELD', 'inbound', ?, ?, datetime('now'))
                ''', (
                    orig_mid or f"imap_{uid}_{int(time.time())}",
                    sender,
                    _json.dumps([recips]) if recips else '[]',
                    str(emsg.get('Subject','')), 
                    '', '', raw_bytes,
                    account_id,
                    int(uid), orig_mid
                ))
                conn.commit()
        imap.logout(); conn.close()
        return jsonify({'success': True, 'moved': moved})
    except Exception as e:
        conn.close(); return jsonify({'success': False, 'error': str(e)}), 500


@accounts_bp.route('/api/accounts/<int:account_id>/resync', methods=['POST'])
@login_required
def api_resync_last(account_id: int):
    """Force a sweep of the last N messages in INBOX for this account and quarantine them if new (idempotent)."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    n = _to_int(request.args.get('last'), 50) or 50
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    cur = conn.cursor(); acc = cur.execute("SELECT * FROM email_accounts WHERE id=?", (account_id,)).fetchone()
    if not acc:
        conn.close(); return jsonify({'success': False, 'error': 'Account not found'}), 404
    host, port, user = acc['imap_host'], _to_int(acc['imap_port'], 993), acc['imap_username'] or acc['email_address']
    pwd = decrypt_credential(acc['imap_password']) if acc['imap_password'] else None
    if not (host and user and pwd):
        conn.close(); return jsonify({'success': False, 'error': 'IMAP credentials missing'}), 400
    try:
        import imaplib
        imap = imaplib.IMAP4_SSL(host, port) if port==993 else imaplib.IMAP4(host, port)
        try:
            if port!=993: imap.starttls()
        except Exception:
            pass
        imap.login(user, pwd); imap.select('INBOX')
        typ, data = imap.search(None, 'ALL')
        uids = []
        if typ=='OK' and data and data[0]:
            all_uids = [int(x) for x in data[0].split()]
            uids = all_uids[-n:]
        # Move to Quarantine; duplicates safely ignored by DB insert logic
        moved=0
        for uid in uids:
            try:
                typ2, _ = imap.uid('MOVE', str(uid), 'Quarantine')
                if typ2!='OK':
                    # fallback copy+delete
                    typ3,_ = imap.uid('COPY', str(uid), 'Quarantine')
                    if typ3=='OK':
                        imap.uid('STORE', str(uid), '+FLAGS', r'(\Deleted)')
                        imap.expunge()
                        moved += 1
                else:
                    moved += 1
            except Exception:
                continue
        imap.logout()
        conn.close(); return jsonify({'success': True, 'moved': moved, 'checked': len(uids)})
    except Exception as e:
        conn.close(); return jsonify({'success': False, 'error': str(e)}), 500


@accounts_bp.route('/accounts')
@login_required
def email_accounts():
    """Email accounts management page with enhanced status monitoring"""
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard.dashboard'))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    accounts = cursor.execute(
        """
        SELECT id, account_name, email_address,
               imap_host, imap_port, imap_username, imap_use_ssl,
               smtp_host, smtp_port, smtp_username, smtp_use_ssl,
               is_active, last_checked, last_error,
               created_at, updated_at
        FROM email_accounts
        ORDER BY account_name
        """
    ).fetchall()

    conn.close()

    return render_template('accounts.html', accounts=accounts)


@accounts_bp.route('/accounts/import', methods=['GET'])
@login_required
def accounts_import_page():
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard.dashboard'))
    return render_template('accounts_import.html')


@accounts_bp.route('/accounts/add', methods=['GET', 'POST'])
@login_required
def add_email_account():
    """Add new email account"""
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        account_name = request.form.get('account_name')
        email_address = request.form.get('email_address')
        start_watcher = request.form.get('start_watcher') == 'on'  # NEW: Control watcher startup

        use_auto_detect = request.form.get('use_auto_detect') == 'on'
        if use_auto_detect and email_address:
            auto = _detect_email_settings(email_address)
            imap_host = auto['imap_host']; imap_port = auto['imap_port']; imap_use_ssl = auto['imap_use_ssl']
            smtp_host = auto.get('smtp_host')  # Optional
            smtp_port = auto.get('smtp_port', 465)  # Optional
            smtp_use_ssl = auto.get('smtp_use_ssl', True)  # Optional
            imap_username = email_address
            smtp_username = email_address
            imap_password = request.form.get('imap_password')
            smtp_password = request.form.get('smtp_password')  # Optional
            # Probe to self-heal if credentials provided
            if imap_password:
                try:
                    imap_choice = _negotiate_imap(imap_host, imap_username, imap_password, imap_port, imap_use_ssl)
                    imap_host = imap_choice['imap_host']; imap_port = imap_choice['imap_port']; imap_use_ssl = imap_choice['imap_use_ssl']
                except Exception:
                    pass
            if smtp_password and smtp_host:  # Only negotiate if SMTP provided
                try:
                    smtp_choice = _negotiate_smtp(smtp_host, smtp_username, smtp_password, smtp_port, smtp_use_ssl)
                    smtp_host = smtp_choice['smtp_host']; smtp_port = smtp_choice['smtp_port']; smtp_use_ssl = smtp_choice['smtp_use_ssl']
                except Exception:
                    pass
        else:
            imap_host = request.form.get('imap_host')
            imap_port = _to_int(request.form.get('imap_port'), 993)
            imap_username = request.form.get('imap_username')
            imap_password = request.form.get('imap_password')
            imap_use_ssl = request.form.get('imap_use_ssl') == 'on'

            # SMTP fields are now OPTIONAL
            smtp_host = request.form.get('smtp_host') or None
            smtp_port = _to_int(request.form.get('smtp_port'), 465) if smtp_host else None
            smtp_username = request.form.get('smtp_username') or None
            smtp_password = request.form.get('smtp_password') or None
            smtp_use_ssl = request.form.get('smtp_use_ssl') == 'on' if smtp_host else False

            # Normalize modes by ports
            if smtp_host and smtp_port:
                smtp_use_ssl, imap_use_ssl = _normalize_modes(int(smtp_port), bool(smtp_use_ssl), int(imap_port or 0), bool(imap_use_ssl))
            # Optional negotiation if creds present
            if imap_password and imap_username and imap_host:
                try:
                    ch = _negotiate_imap(imap_host, imap_username, imap_password, imap_port, imap_use_ssl)
                    imap_host = ch['imap_host']; imap_port = ch['imap_port']; imap_use_ssl = ch['imap_use_ssl']
                except Exception:
                    pass
            if smtp_password and smtp_username and smtp_host:
                try:
                    ch = _negotiate_smtp(smtp_host, smtp_username, smtp_password, smtp_port, smtp_use_ssl)
                    smtp_host = ch['smtp_host']; smtp_port = ch['smtp_port']; smtp_use_ssl = ch['smtp_use_ssl']
                except Exception:
                    pass

        # IMAP is REQUIRED
        imap_ok, imap_msg = _test_email_connection('imap', str(imap_host or ''), _to_int(imap_port, 993), str(imap_username or ''), imap_password or '', bool(imap_use_ssl))
        if not imap_ok:
            flash(f'IMAP connection failed: {imap_msg}', 'error')
            return render_template('add_account.html')

        # SMTP is OPTIONAL - only test if provided
        if smtp_host and smtp_username and smtp_password:
            smtp_ok, smtp_msg = _test_email_connection('smtp', str(smtp_host), _to_int(smtp_port, 465), str(smtp_username), smtp_password, bool(smtp_use_ssl))
            if not smtp_ok:
                flash(f'SMTP connection failed: {smtp_msg}', 'error')
                return render_template('add_account.html')

        encrypted_imap_password = encrypt_credential(imap_password)
        encrypted_smtp_password = encrypt_credential(smtp_password) if smtp_password else None

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO email_accounts
            (account_name, email_address, imap_host, imap_port, imap_username, imap_password, imap_use_ssl,
             smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_ssl, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                account_name, email_address, imap_host, imap_port, imap_username, encrypted_imap_password, imap_use_ssl,
                smtp_host, smtp_port, smtp_username, encrypted_smtp_password, smtp_use_ssl,
            ),
        )
        account_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Validate account_id is not None (shouldn't happen for successful INSERT)
        if account_id is None:
            flash('Failed to create account: database error', 'error')
            return redirect(url_for('accounts.email_accounts'))

        # Start IMAP watcher ONLY if user requested it
        if start_watcher:
            try:
                from simple_app import monitor_imap_account, imap_threads  # lazy import to avoid circular at import time
                import threading
                thread = threading.Thread(target=monitor_imap_account, args=(account_id,), daemon=True)
                imap_threads[account_id] = thread  # account_id is now guaranteed to be int
                thread.start()
                flash('Account added and monitoring started successfully', 'success')
            except Exception as e:
                # Log warning but don't fail the account creation
                try:
                    current_app.logger.warning(f"Failed to start IMAP monitor thread for account {account_id}: {e}")
                except Exception:
                    pass
                flash('Account added successfully (monitoring not started - you can start it manually from the accounts page)', 'warning')
        else:
            flash('Account added successfully (monitoring not started)', 'success')

        return redirect(url_for('accounts.email_accounts'))

    return render_template('add_account.html')


@accounts_bp.route('/api/accounts/import', methods=['POST'])
@csrf.exempt
@login_required
def api_import_accounts():
    if current_user.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    file = request.files.get('file')
    auto_detect = (request.form.get('auto_detect') == 'on') or (request.args.get('auto_detect') == '1')
    if not file:
        return jsonify({'success': False, 'error': 'CSV file is required'}), 400
    try:
        content = file.read().decode('utf-8', errors='ignore')
        reader = csv.DictReader(StringIO(content))
        rows = list(reader)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Invalid CSV: {e}'}), 400

    inserted = updated = errors = 0
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        for row in rows:
            try:
                # Normalize
                r = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                email = r.get('email_address') or r.get('email')
                if not email:
                    raise ValueError('email_address missing')
                account_name = r.get('account_name') or email
                imap_user = r.get('imap_username') or email
                smtp_user = r.get('smtp_username') or email
                imap_pwd = r.get('imap_password')
                smtp_pwd = r.get('smtp_password')
                if not imap_pwd or not smtp_pwd:
                    raise ValueError('imap_password and smtp_password required')
                def _to_int(v, d=None):
                    try: return int(v)
                    except Exception: return d
                def _to_bool(v, d=None):
                    if v is None: return d
                    s = str(v).strip().lower()
                    if s in ('1','true','yes','y'): return True
                    if s in ('0','false','no','n'): return False
                    return d
                imap_host = r.get('imap_host'); smtp_host = r.get('smtp_host')
                imap_port = _to_int(r.get('imap_port'), 993); smtp_port = _to_int(r.get('smtp_port'), 465)
                imap_ssl = _to_bool(r.get('imap_use_ssl'), True); smtp_ssl = _to_bool(r.get('smtp_use_ssl'), True)
                if auto_detect and (not imap_host or not smtp_host):
                    auto = _detect_email_settings(email)
                    imap_host = imap_host or auto['imap_host']
                    imap_port = imap_port or auto['imap_port']
                    imap_ssl = auto['imap_use_ssl'] if imap_ssl is None else imap_ssl
                    smtp_host = smtp_host or auto['smtp_host']
                    smtp_port = smtp_port or auto['smtp_port']
                    smtp_ssl = auto['smtp_use_ssl'] if smtp_ssl is None else smtp_ssl
                is_active = 1 if _to_bool(r.get('is_active'), True) else 0

                enc_imap = encrypt_credential(imap_pwd)
                enc_smtp = encrypt_credential(smtp_pwd)
                existing = cur.execute("SELECT id FROM email_accounts WHERE email_address=?", (email,)).fetchone()
                if existing:
                    cur.execute(
                        """
                        UPDATE email_accounts
                        SET account_name=?,
                            imap_host=?, imap_port=?, imap_username=?, imap_password=?, imap_use_ssl=?,
                            smtp_host=?, smtp_port=?, smtp_username=?, smtp_password=?, smtp_use_ssl=?,
                            is_active=?, updated_at=CURRENT_TIMESTAMP
                        WHERE email_address=?
                        """,
                        (
                            account_name,
                            imap_host, imap_port, imap_user, enc_imap, 1 if (imap_ssl is not False) else 0,
                            smtp_host, smtp_port, smtp_user, enc_smtp, 1 if (smtp_ssl is not False) else 0,
                            is_active, email
                        )
                    ); updated += 1
                else:
                    cur.execute(
                        """
                        INSERT INTO email_accounts (
                            account_name, email_address,
                            imap_host, imap_port, imap_username, imap_password, imap_use_ssl,
                            smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_ssl,
                            is_active
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            account_name, email,
                            imap_host, imap_port, imap_user, enc_imap, 1 if (imap_ssl is not False) else 0,
                            smtp_host, smtp_port, smtp_user, enc_smtp, 1 if (smtp_ssl is not False) else 0,
                            is_active
                        )
                    ); inserted += 1
            except Exception as e:
                errors += 1
                current_app.logger.warning(f"Import row error for {row.get('email_address')}: {e}")
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'inserted': inserted, 'updated': updated, 'errors': errors})

@accounts_bp.route('/api/accounts/<int:account_id>/monitor/start', methods=['POST'])
@csrf.exempt
@login_required
def api_start_monitor(account_id: int):
    """Activate and start IMAP monitoring for a specific account."""
    if current_user.role != 'admin':
        payload, code = _watcher_response(account_id, ok=False, detail='Admin access required', status_code=403)
        return jsonify(payload), code
    # Validate credentials present
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    acc = cur.execute("SELECT * FROM email_accounts WHERE id=?", (account_id,)).fetchone()
    if not acc:
        conn.close()
        payload, code = _watcher_response(account_id, ok=False, detail='Account not found', status_code=404)
        return jsonify(payload), code
    imap_user = acc['imap_username'] or acc['email_address']
    imap_pwd = decrypt_credential(acc['imap_password']) if acc['imap_password'] else None
    if not imap_user or not imap_pwd:
        conn.close()
        payload, code = _watcher_response(account_id, ok=False, detail='IMAP credentials missing', status_code=400)
        return jsonify(payload), code
    # Set active and start watcher via simple_app helper
    cur.execute("UPDATE email_accounts SET is_active=1 WHERE id=?", (account_id,))
    conn.commit()
    conn.close()
    try:
        from simple_app import start_imap_watcher_for_account
        ok = start_imap_watcher_for_account(account_id)
    except Exception as e:
        log.warning(
            "[accounts] Failed to start IMAP watcher",
            extra={'account_id': account_id, 'error': str(e)},
        )
        payload, code = _watcher_response(
            account_id,
            ok=False,
            detail=f"Failed to start watcher: {e}",
            status_code=500,
        )
        return jsonify(payload), code
    detail_msg = "Watcher start requested" if ok else "Watcher thread did not report as running"
    status_code = 200 if ok else 500
    payload, code = _watcher_response(account_id, ok=bool(ok), detail=detail_msg, status_code=status_code)
    return jsonify(payload), code

@accounts_bp.route('/api/accounts/<int:account_id>/monitor/stop', methods=['POST'])
@csrf.exempt
@login_required
def api_stop_monitor(account_id: int):
    """Deactivate and stop IMAP monitoring for a specific account."""
    if current_user.role != 'admin':
        payload, code = _watcher_response(account_id, ok=False, detail='Admin access required', status_code=403)
        return jsonify(payload), code
    # Deactivate and signal stop
    stop_error = None
    try:
        from simple_app import stop_imap_watcher_for_account
        stop_imap_watcher_for_account(account_id)
    except Exception as e:
        stop_error = str(e)
        log.warning(
            "[accounts] Failed to signal watcher stop",
            extra={'account_id': account_id, 'error': stop_error},
        )
    # Confirm deactivation
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE email_accounts SET is_active=0 WHERE id=?", (account_id,))
    conn.commit()
    conn.close()
    detail_msg = "Watcher stop requested" if not stop_error else f"Watcher stop issued with warning: {stop_error}"
    status_code = 200 if not stop_error else 500
    payload, code = _watcher_response(account_id, ok=(stop_error is None), detail=detail_msg, status_code=status_code)
    return jsonify(payload), code

@accounts_bp.route('/api/accounts/<int:account_id>/monitor/restart', methods=['POST'])
@csrf.exempt
@login_required
def api_restart_monitor(account_id: int):
    """Quick restart for an IMAP watcher: stop then start (best-effort)."""
    if current_user.role != 'admin':
        payload, code = _watcher_response(account_id, ok=False, detail='Admin access required', status_code=403)
        return jsonify(payload), code
    try:
        from simple_app import stop_imap_watcher_for_account, start_imap_watcher_for_account
        stop_imap_watcher_for_account(account_id)
        ok = start_imap_watcher_for_account(account_id)
        detail_msg = "Watcher restart requested" if ok else "Watcher restart did not complete"
        status_code = 200 if ok else 500
        payload, code = _watcher_response(account_id, ok=bool(ok), detail=detail_msg, status_code=status_code)
        return jsonify(payload), code
    except Exception as e:
        log.warning(
            "[accounts] Failed to restart watcher",
            extra={'account_id': account_id, 'error': str(e)},
        )
        payload, code = _watcher_response(
            account_id,
            ok=False,
            detail=f"Failed to restart watcher: {e}",
            status_code=500,
        )
        return jsonify(payload), code

@accounts_bp.route('/api/watchers/status')
@login_required
def api_watchers_status():
    """Return recent IMAP watcher heartbeats for UI badges/diagnostics."""
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        # Ensure column existence detection for error_count
        cols = [r[1] for r in cur.execute("PRAGMA table_info(worker_heartbeats)").fetchall()]
        has_err = 'error_count' in cols
        query = (
            "SELECT worker_id, last_heartbeat, status" + (", error_count" if has_err else "") +
            " FROM worker_heartbeats WHERE datetime(last_heartbeat) > datetime('now','-2 minutes') ORDER BY last_heartbeat DESC"
        )
        rows = cur.execute(query).fetchall()
        payload = [dict(r) for r in rows]
    except Exception:
        payload = []
    finally:
        conn.close()
    return jsonify({'success': True, 'workers': payload})

@accounts_bp.route('/api/detect-email-settings', methods=['POST'])
@login_required
def api_detect_email_settings():
    """API endpoint for smart detection of email settings (moved from monolith)."""
    data = request.get_json(silent=True) or {}
    email = data.get('email', '')

    if not email or '@' not in email:
        return jsonify({'error': 'Invalid email address'}), 400

    settings = _detect_email_settings(email)
    return jsonify(settings)
