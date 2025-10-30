"""Email Management Blueprint - Phase 1B Route Modularization

Extracted from simple_app.py lines 721-2197
Routes: /emails, /email/<id>, /email/<id>/action, /inbox, /compose, /api/held, /api/emails/pending
Plus API routes for reply/forward, download, intercept
"""
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, Response
from flask_login import login_required, current_user
import sqlite3
import os
import json
import email
import imaplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email import policy
from email import message_from_bytes
from email.utils import parsedate_to_datetime, getaddresses
from app.utils.db import DB_PATH, get_db, fetch_counts
from app.utils.imap_helpers import _ensure_quarantine, _move_uid_to_quarantine
from app.extensions import csrf, limiter
from app.utils.crypto import decrypt_credential
from app.utils.rule_engine import evaluate_rules
from app.services.audit import log_action
from app.utils.rate_limit import get_rate_limit_config, simple_rate_limit

emails_bp = Blueprint('emails', __name__)
log = logging.getLogger(__name__)


_FETCH_RATE_LIMIT = get_rate_limit_config('fetch', default_requests=30)
_FETCH_LIMIT_STRING = str(_FETCH_RATE_LIMIT['limit_string'])

@emails_bp.route('/emails-unified')
@login_required
def emails_unified():
    """Unified email management interface"""
    status_filter = request.args.get('status', 'ALL')
    account_id = request.args.get('account_id', type=int)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get email accounts
    accounts = cursor.execute(
        """
        SELECT id, account_name, email_address
        FROM email_accounts
        WHERE is_active = 1
        ORDER BY account_name
        """
    ).fetchall()

    # Get counts for all statuses (exclude outbound by default)
    counts = fetch_counts(account_id=account_id if account_id else None, include_outbound=False)

    conn.close()

    return render_template(
        'emails_unified.html',
        accounts=accounts,
        selected_account=account_id,
        current_filter=status_filter,
        total_count=counts.get('total', 0),
        held_count=counts.get('held', 0),
        pending_count=counts.get('pending', 0),
        approved_count=counts.get('approved', 0),
        rejected_count=counts.get('rejected', 0),
        released_count=counts.get('released', 0),
        discarded_count=counts.get('discarded', 0),
    )


@emails_bp.route('/api/emails/unified')
@login_required
def api_emails_unified():
    """API endpoint for unified email list"""
    status_filter = request.args.get('status', 'ALL')
    account_id = request.args.get('account_id', type=int)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build query based on filters (exclude outbound by default)
    query = """
        SELECT id, account_id, sender, recipients, subject, body_text,
               interception_status, status, created_at,
               latency_ms, risk_score, keywords_matched
        FROM email_messages
        WHERE (direction IS NULL OR direction!='outbound')
    """
    params = []

    if account_id:
        query += " AND account_id = ?"
        params.append(account_id)

    if status_filter and status_filter != 'ALL':
        if status_filter == 'RELEASED':
            # Treat released as interception_status=RELEASED or legacy delivered/approved (exclude SENT/outbound)
            query += " AND (interception_status='RELEASED' OR status IN ('APPROVED','DELIVERED'))"
        elif status_filter == 'HELD':
            # HELD now includes both PENDING and HELD statuses
            query += " AND (interception_status IN ('HELD', 'PENDING') OR status IN ('HELD', 'PENDING'))"
        else:
            query += " AND (interception_status = ? OR status = ?)"
            params.extend([status_filter, status_filter])
    else:
        # Default ALL view hides DISCARDED items
        query += " AND (interception_status IS NULL OR interception_status != 'DISCARDED')"

    query += " ORDER BY created_at DESC LIMIT 200"

    emails = cursor.execute(query, params).fetchall()

    # Get counts (exclude outbound by default)
    counts = fetch_counts(account_id=account_id if account_id else None, include_outbound=False)

    # Process emails for response (Phase 5 Quick Wins: optimized with helper function)
    def _process_email(email):
        """Process a single email record for API response"""
        email_dict = dict(email)

        # Fix timezone for created_at: SQLite datetime('now') returns UTC without 'Z' suffix
        # JavaScript interprets timestamps without timezone as local time, causing display errors
        # Append 'Z' to indicate UTC so browsers display correct local time
        if email_dict.get('created_at') and isinstance(email_dict['created_at'], str):
            if not email_dict['created_at'].endswith('Z') and 'T' not in email_dict['created_at']:
                # SQLite format: "YYYY-MM-DD HH:MM:SS" → "YYYY-MM-DDTHH:MM:SSZ"
                email_dict['created_at'] = email_dict['created_at'].replace(' ', 'T') + 'Z'

        # Add preview snippet
        body_text = email_dict.get('body_text') or ''
        email_dict['preview_snippet'] = ' '.join(body_text.split())[:160]

        # Parse recipients if JSON (pre-computed to avoid repeated parsing)
        try:
            if email_dict.get('recipients'):
                email_dict['recipients'] = json.loads(email_dict['recipients'])
        except (json.JSONDecodeError, TypeError):
            pass

        return email_dict

    # Process all emails in one comprehension (faster than loop)
    email_list = [_process_email(email) for email in emails]

    conn.close()

    # Return accurate counts from database, not len(email_list) which is limited by LIMIT clause
    # The "total" count should ALWAYS be >= individual status counts (held, released, rejected)
    return jsonify({
        'emails': email_list,
        'counts': {
            'total': counts.get('total', 0),
            'held': counts.get('held', 0),
            'pending': counts.get('pending', 0),
            'approved': counts.get('approved', 0),
            'rejected': counts.get('rejected', 0),
            'released': counts.get('released', 0),
            'discarded': counts.get('discarded', 0),
        }
    })


@emails_bp.route('/api/emails/search')
@login_required
def search_emails():
    """Search emails by subject, sender, recipient, or body text"""
    q = request.args.get('q', '').strip()
    account_id = request.args.get('account_id', type=int)

    if not q:
        return jsonify({'emails': [], 'count': 0, 'query': q})

    with get_db() as conn:
        cursor = conn.cursor()

        # Search in subject, sender, recipients (JSON array), and body_text
        query = """
            SELECT id, account_id, sender, recipients, subject, body_text,
                   interception_status, status, created_at,
                   latency_ms, risk_score, keywords_matched
            FROM email_messages
            WHERE (direction IS NULL OR direction!='outbound')
              AND (
                subject LIKE ? OR
                sender LIKE ? OR
                recipients LIKE ? OR
                body_text LIKE ?
              )
        """
        search_pattern = f'%{q}%'
        params = [search_pattern, search_pattern, search_pattern, search_pattern]

        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)

        query += " ORDER BY created_at DESC LIMIT 100"

        emails = cursor.execute(query, params).fetchall()

        # Process emails
        def _process_email(email):
            email_dict = dict(email)
            if email_dict.get('created_at') and isinstance(email_dict['created_at'], str):
                if not email_dict['created_at'].endswith('Z') and 'T' not in email_dict['created_at']:
                    email_dict['created_at'] = email_dict['created_at'].replace(' ', 'T') + 'Z'
            body_text = email_dict.get('body_text') or ''
            email_dict['preview_snippet'] = ' '.join(body_text.split())[:160]
            try:
                if email_dict.get('recipients'):
                    email_dict['recipients'] = json.loads(email_dict['recipients'])
            except (json.JSONDecodeError, TypeError):
                pass
            return email_dict

        email_list = [_process_email(email) for email in emails]

    return jsonify({'emails': email_list, 'count': len(email_list), 'query': q})


@emails_bp.route('/emails')
@login_required
def email_queue():
    """Legacy email queue - redirect to unified"""
    status_filter = request.args.get('status', 'PENDING')
    account_id = request.args.get('account_id', type=int)

    # Redirect to unified view
    params = []
    if status_filter:
        params.append(f'status={status_filter}')
    if account_id:
        params.append(f'account_id={account_id}')

    redirect_url = '/emails-unified'
    if params:
        redirect_url += '?' + '&'.join(params)

    return redirect(redirect_url)






# Keep original email_queue for backward compatibility (without redirect)
@emails_bp.route('/emails-legacy')
@login_required
def email_queue_legacy():
    status_filter = request.args.get('status', 'PENDING')
    account_id = request.args.get('account_id', type=int)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    accounts = cursor.execute(
        """
        SELECT id, account_name, email_address
        FROM email_accounts
        WHERE is_active = 1
        ORDER BY account_name
        """
    ).fetchall()

    counts = fetch_counts(account_id=int(account_id) if account_id else None)
    pending_count = int(counts.get('pending') or 0)
    approved_count = int(counts.get('approved') or 0)
    rejected_count = int(counts.get('rejected') or 0)
    total_count = int(counts.get('total') or 0)

    if account_id:
        if status_filter.upper() == 'ALL':
            emails = cursor.execute(
                """
                SELECT * FROM email_messages
                WHERE account_id = ?
                ORDER BY created_at DESC
                """,
                (account_id,),
            ).fetchall()
        else:
            emails = cursor.execute(
                """
                SELECT * FROM email_messages
                WHERE status = ? AND account_id = ?
                ORDER BY created_at DESC
                """,
                (status_filter, account_id),
            ).fetchall()
    else:
        if status_filter.upper() == 'ALL':
            emails = cursor.execute(
                """
                SELECT * FROM email_messages
                ORDER BY created_at DESC
                """
            ).fetchall()
        else:
            emails = cursor.execute(
                """
                SELECT * FROM email_messages
                WHERE status = ?
                ORDER BY created_at DESC
                """,
                (status_filter,),
            ).fetchall()

    conn.close()

    return render_template(
        'email_queue.html',
        emails=emails,
        current_filter=status_filter,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        total_count=total_count,
        accounts=accounts,
        selected_account_id=str(account_id) if account_id else None,
    )


@emails_bp.route('/email/<int:email_id>')
@login_required
def view_email(email_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Join with accounts to show meaningful account info in the viewer
    email_row = cursor.execute(
        """
        SELECT em.*, ea.account_name, ea.email_address
        FROM email_messages em
        LEFT JOIN email_accounts ea ON em.account_id = ea.id
        WHERE em.id = ?
        """,
        (email_id,)
    ).fetchone()

    if not email_row:
        conn.close()
        flash('Email not found', 'error')
        return redirect(url_for('emails.email_queue'))

    conn.close()

    email_data = dict(email_row)
    try:
        email_data['recipients'] = json.loads(email_data['recipients']) if email_data['recipients'] else []
    except (json.JSONDecodeError, TypeError):
        if isinstance(email_data['recipients'], str):
            email_data['recipients'] = [r.strip() for r in email_data['recipients'].split(',') if r.strip()]
        else:
            email_data['recipients'] = []

    try:
        email_data['keywords_matched'] = json.loads(email_data['keywords_matched']) if email_data['keywords_matched'] else []
    except (json.JSONDecodeError, TypeError):
        if isinstance(email_data['keywords_matched'], str):
            email_data['keywords_matched'] = [k.strip() for k in email_data['keywords_matched'].split(',') if k.strip()]
        else:
            email_data['keywords_matched'] = []

    return render_template('email_viewer.html', email=email_data, attachments_flags={'ui': True, 'edit': email_data.get('interception_status') == 'HELD'})


@emails_bp.route('/email/<int:email_id>/action', methods=['POST'])
@login_required
def email_action(email_id):
    action = request.form.get('action', '').upper()
    notes = request.form.get('notes', '')

    if action not in ['APPROVE', 'REJECT']:
        return jsonify({'error': 'Invalid action'}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    new_status = 'APPROVED' if action == 'APPROVE' else 'REJECTED'
    # Detect optional reviewed_at column for backward compatibility
    cols = [r[1] for r in cursor.execute("PRAGMA table_info(email_messages)").fetchall()]
    if 'reviewed_at' in cols:
        cursor.execute(
            """
            UPDATE email_messages
            SET status = ?, reviewer_id = ?, review_notes = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_status, current_user.id, notes, email_id),
        )
    else:
        cursor.execute(
            """
            UPDATE email_messages
            SET status = ?, reviewer_id = ?, review_notes = ?
            WHERE id = ?
            """,
            (new_status, current_user.id, notes, email_id),
        )

    log_action(action, current_user.id, email_id, f"Email {action.lower()}d with notes: {notes}")

    conn.commit()
    conn.close()

    flash(f'Email {action.lower()}d successfully', 'success')
    return redirect(url_for('emails.email_queue'))


@emails_bp.route('/api/fetch-emails', methods=['POST'])
@csrf.exempt
@limiter.limit(_FETCH_LIMIT_STRING)
@simple_rate_limit('fetch', config=_FETCH_RATE_LIMIT)
@login_required
def api_fetch_emails():
    """Fetch emails from IMAP server using UID-based fetching (migrated)."""
    data = request.get_json(silent=True) or {}
    account_id = data.get('account_id'); fetch_count = int(data.get('count', 20)); offset = int(data.get('offset', 0))
    if not account_id:
        return jsonify({'success': False, 'error': 'Account ID required'}), 400
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    acct = cur.execute("SELECT * FROM email_accounts WHERE id=? AND is_active=1", (account_id,)).fetchone()
    if not acct:
        conn.close(); return jsonify({'success': False, 'error': 'Account not found'}), 404
    mail = None
    auto_move_enabled = str(os.environ.get('AUTO_MOVE_ON_FETCH', '0')).lower() in ('1', 'true', 'yes')
    log.debug("[emails::fetch] start", extra={'account_id': account_id, 'count': fetch_count, 'offset': offset, 'auto_move': auto_move_enabled})
    try:
        password = decrypt_credential(acct['imap_password'])
        if not password:
            conn.close(); return jsonify({'success': False, 'error': 'Password decrypt failed'}), 500
        if int(acct['imap_port'] or 993) == 993:
            mail = imaplib.IMAP4_SSL(acct['imap_host'], int(acct['imap_port']))
        else:
            mail = imaplib.IMAP4(acct['imap_host'], int(acct['imap_port']))
            try: mail.starttls()
            except Exception as e:
                log.warning("[emails::fetch] STARTTLS failed (non-SSL port, continuing)", extra={'account_id': account_id, 'error': str(e)})
        mail.login(acct['imap_username'], password); mail.select('INBOX')
        typ, data_uids = mail.uid('SEARCH', 'ALL')
        if typ != 'OK':
            return jsonify({'success': False, 'error': 'UID SEARCH failed'}), 500
        uid_bytes = data_uids[0].split() if data_uids and data_uids[0] else []
        total = len(uid_bytes); start = max(0, total - offset - fetch_count); end = total - offset
        window = uid_bytes[start:end][-fetch_count:]
        results = []
        for raw_uid in reversed(window):
            uid = raw_uid.decode(); typ, msg_payload = mail.uid('fetch', uid, '(RFC822 INTERNALDATE)')
            if typ != 'OK' or not msg_payload or msg_payload[0] is None: continue
            raw_email = msg_payload[0][1]; msg = message_from_bytes(raw_email, policy=policy.default)
            internaldate = None
            try:
                fetch_data = msg_payload[0][0]
                if isinstance(fetch_data, bytes):
                    fetch_str = fetch_data.decode('utf-8', errors='ignore')
                    import re
                    m = re.search(r'INTERNALDATE "([^"]+)"', fetch_str)
                    if m:
                        date_str = m.group(1)
                        date_tuple = imaplib.Internaldate2tuple(f'INTERNALDATE "{date_str}"'.encode())
                        if date_tuple:
                            from datetime import datetime as dt
                            internaldate = dt(*date_tuple[:6]).isoformat()
            except Exception:
                pass
            if not internaldate:
                try:
                    date_hdr = msg.get('Date')
                    if date_hdr: internaldate = parsedate_to_datetime(date_hdr).isoformat()
                except Exception:
                    pass
            message_id = msg.get('Message-ID') or f"fetch_{account_id}_{uid}"
            sender = msg.get('From', '')
            subject = msg.get('Subject', 'No Subject')
            addr_fields = msg.get_all('To', []) + msg.get_all('Cc', [])
            addr_list = [addr for _, addr in getaddresses(addr_fields)]
            recipients_list = [a for a in addr_list if a] or ([msg.get('To', '')] if msg.get('To') else [])
            recipients = json.dumps(recipients_list)

            body_text = ''
            body_html = ''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.is_multipart():
                        continue
                    ctype = part.get_content_type()
                    payload = part.get_payload(decode=True)
                    if payload is None:
                        continue
                    if ctype == 'text/plain':
                        if isinstance(payload, (bytes, bytearray)):
                            body_text = payload.decode('utf-8', errors='ignore')
                        elif isinstance(payload, str):
                            body_text = payload
                    elif ctype == 'text/html':
                        if isinstance(payload, (bytes, bytearray)):
                            body_html = payload.decode('utf-8', errors='ignore')
                        elif isinstance(payload, str):
                            body_html = payload
            else:
                payload = msg.get_payload(decode=True)
                if isinstance(payload, (bytes, bytearray)):
                    body_text = payload.decode('utf-8', errors='ignore')
                elif isinstance(payload, str):
                    body_text = payload

            rule_eval = evaluate_rules(subject, body_text, sender, recipients_list)
            should_hold = bool(rule_eval['should_hold'])
            risk_score = rule_eval['risk_score']
            keywords_json = json.dumps(rule_eval['keywords'])
            log.debug("[emails::fetch] evaluated", extra={'account_id': account_id, 'uid': uid, 'should_hold': should_hold, 'risk': risk_score})
            cur.execute(
                """
                INSERT OR IGNORE INTO email_messages
                (message_id, sender, recipients, subject, body_text, body_html,
                 raw_content, account_id, direction, interception_status,
                 original_uid, original_internaldate, risk_score, keywords_matched, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (message_id, sender, recipients, subject, body_text, body_html, raw_email, account_id, 'inbound', 'FETCHED', uid, internaldate, risk_score, keywords_json),
            )
            row = cur.execute("SELECT id FROM email_messages WHERE message_id=? ORDER BY id DESC LIMIT 1", (message_id,)).fetchone()
            email_row_id = row['id'] if row else None

            moved_to_quarantine = False
            quarantine_folder = None
            if should_hold and auto_move_enabled and email_row_id:
                try:
                    quarantine_folder = _ensure_quarantine(mail, 'Quarantine')
                    moved_to_quarantine = _move_uid_to_quarantine(mail, uid, quarantine_folder)
                except Exception:
                    moved_to_quarantine = False
                if moved_to_quarantine:
                    cur.execute(
                        """
                        UPDATE email_messages
                        SET interception_status='HELD',
                            status='PENDING',
                            quarantine_folder=?,
                            action_taken_at=datetime('now')
                        WHERE id=?
                        """,
                        (quarantine_folder, email_row_id),
                    )
                    log.info("[emails::fetch] auto-held message", extra={'account_id': account_id, 'email_id': email_row_id, 'uid': uid, 'quarantine_folder': quarantine_folder})
                else:
                    quarantine_folder = None
                    log.debug("[emails::fetch] auto-move skipped", extra={'account_id': account_id, 'email_id': email_row_id, 'uid': uid})

            results.append({
                'id': email_row_id,
                'message_id': message_id,
                'uid': uid,
                'subject': subject,
                'should_hold': should_hold,
                'held': moved_to_quarantine,
                'quarantine_folder': quarantine_folder,
            })
        conn.commit();
        log.debug("[emails::fetch] completed", extra={'account_id': account_id, 'fetched': len(results), 'total': total})
        return jsonify({'success': True, 'total_available': total, 'fetched': len(results), 'emails': results})
    except Exception as exc:
        log.exception("[emails::fetch] failed", extra={'account_id': account_id})
        return jsonify({'success': False, 'error': str(exc)}), 500
    finally:
        if mail:
            try: mail.logout()
            except Exception as e:
                log.debug("[emails::fetch] IMAP logout failed (non-critical)", extra={'account_id': account_id, 'error': str(e)})
        conn.close()


@emails_bp.route('/api/email/<email_id>/reply-forward', methods=['GET'])
@login_required
def api_email_reply_forward(email_id):
    """Get email data formatted for reply or forward (migrated)."""
    action = request.args.get('action', 'reply')
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    row = cur.execute("SELECT * FROM email_messages WHERE id=?", (email_id,)).fetchone()
    if not row:
        conn.close(); return jsonify({'success': False, 'error': 'Email not found'}), 404
    if action == 'reply':
        data = {'to': row['sender'], 'subject': f"Re: {row['subject']}" if not (row['subject'] or '').startswith('Re:') else row['subject'], 'body': f"\n\n--- Original Message ---\nFrom: {row['sender']}\nDate: {row['created_at']}\nSubject: {row['subject']}\n\n{row['body_text']}"}
    else:
        data = {'to': '', 'subject': f"Fwd: {row['subject']}" if not (row['subject'] or '').startswith('Fwd:') else row['subject'], 'body': f"\n\n--- Forwarded Message ---\nFrom: {row['sender']}\nDate: {row['created_at']}\nSubject: {row['subject']}\n\n{row['body_text']}"}
    conn.close(); return jsonify({'success': True, 'data': data})


@emails_bp.route('/api/email/<email_id>/download', methods=['GET'])
@login_required
def api_email_download(email_id):
    """Download email as .eml file (migrated)."""
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    row = cur.execute("SELECT raw_content, subject FROM email_messages WHERE id=?", (email_id,)).fetchone(); conn.close()
    if not row or not row['raw_content']:
        return jsonify({'success': False, 'error': 'Email not found or no raw content'}), 404
    import re
    safe_subject = re.sub(r'[^\w\s-]', '', row['subject'] or 'email')[:50]; filename = f"{safe_subject}_{email_id}.eml"
    return Response(row['raw_content'], mimetype='message/rfc822', headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@emails_bp.route('/email/<int:email_id>/full')
@login_required
def get_full_email(email_id):
    """Get complete email details for editor (migrated)."""
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    row = cur.execute(
        """
        SELECT id, message_id, sender, recipients, subject,
               body_text, body_html, status,
               risk_score, keywords_matched, review_notes,
               created_at, processed_at
        FROM email_messages
        WHERE id = ?
        """,
        (email_id,),
    ).fetchone(); conn.close()
    if not row:
        return jsonify({'error': 'Email not found'}), 404
    data = {k: row[k] for k in row.keys()}
    # Indicate presence of raw content without serializing it (prevents JSON 500)
    data['has_raw'] = True
    return jsonify(data)


@emails_bp.route('/email/<int:email_id>/edit', methods=['GET'])
@login_required
def get_email_for_edit(email_id: int):
    """Thin alias to /email/<id>/full for edit modal compatibility."""
    return get_full_email(email_id)
