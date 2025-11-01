"""
Diagnostics & Test Utilities Blueprint
Routes moved from simple_app.py to keep the entrypoint thin.
"""
import os
import json
import sqlite3
import time
import smtplib
from datetime import datetime
from email.utils import formatdate, make_msgid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app.utils.db import DB_PATH
from app.utils.crypto import decrypt_credential
from app.utils.email_helpers import test_email_connection as _test_email_connection
import os

diagnostics_bp = Blueprint('diagnostics', __name__)


@diagnostics_bp.route('/test/cross-account', methods=['POST'])
@login_required
def run_cross_account_test():
    try:
        import subprocess
        result = subprocess.run(['python', 'cross_account_test.py'], capture_output=True, text=True, timeout=60)
        output = result.stdout
        success = "TEST PASSED" in output
        return jsonify({'success': success, 'output': output, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@diagnostics_bp.route('/api/test-status')
@login_required
def get_test_status():
    try:
        import glob
        test_files = glob.glob('test_results_*.json')
        if test_files:
            latest_file = max(test_files)
            with open(latest_file, 'r') as f:
                data = json.load(f)
                return jsonify(data)
        else:
            return jsonify({'status': 'No tests run yet'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@diagnostics_bp.route('/api/logs')
@login_required
def get_logs():
    """Fetch recent application logs with filtering."""
    import glob
    import logging
    
    # Get filter parameters
    severity = request.args.get('severity', '').upper()  # ERROR, WARNING, INFO, DEBUG
    component = request.args.get('component', '')  # imap_watcher, smtp_handler, accounts, etc.
    limit = int(request.args.get('limit', 100))
    
    logs = []
    log_dir = 'logs'
    
    try:
        # Read from app.log (JSON formatted logs)
        log_file = os.path.join(log_dir, 'app.log')
        if not os.path.exists(log_file):
            return jsonify({'logs': [], 'message': 'No log file found'}), 200
        
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Read last N lines for efficiency
            recent_lines = lines[-1000:] if len(lines) > 1000 else lines
            
            for line in reversed(recent_lines):  # Most recent first
                try:
                    log_entry = json.loads(line.strip())
                    
                    # Apply severity filter
                    if severity and log_entry.get('level', '').upper() != severity:
                        continue
                    
                    # Apply component filter (check message or logger name)
                    if component:
                        msg = log_entry.get('message', '').lower()
                        logger = log_entry.get('name', '').lower()
                        if component.lower() not in msg and component.lower() not in logger:
                            continue
                    
                    logs.append(log_entry)
                    
                    if len(logs) >= limit:
                        break
                except (json.JSONDecodeError, ValueError):
                    # Skip malformed log lines
                    continue
        
        return jsonify({
            'logs': logs,
            'count': len(logs),
            'filters': {
                'severity': severity or 'all',
                'component': component or 'all',
                'limit': limit
            }
        }), 200
        
    except Exception as e:
        logging.getLogger(__name__).error(f"[diagnostics] Failed to fetch logs: {e}")
        return jsonify({'error': 'Failed to read logs', 'details': str(e)}), 500


@diagnostics_bp.route('/diagnostics/test', methods=['POST'])
@login_required
def test_email_send():
    flash('Email diagnostics send test temporarily disabled (module deprecated).', 'warning')
    return redirect(url_for('accounts.diagnostics'))


@diagnostics_bp.route('/interception-test')
@login_required
def interception_test_dashboard():
    return render_template('interception_test_dashboard.html', timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@diagnostics_bp.route('/api/test/send-email', methods=['POST'])
@login_required
def api_test_send_email():
    data = request.get_json(silent=True) or {}
    from_account_id = data.get('from_account_id'); to_account_id = data.get('to_account_id')
    subject = data.get('subject') or 'Test'; body = data.get('body') or 'Test body'
    if not (from_account_id and to_account_id):
        return jsonify({'success': False, 'error': 'Missing account ids'}), 400
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    from_account = cur.execute("SELECT * FROM email_accounts WHERE id=?", (from_account_id,)).fetchone()
    to_account = cur.execute("SELECT * FROM email_accounts WHERE id=?", (to_account_id,)).fetchone(); conn.close()
    if not from_account or not to_account:
        return jsonify({'success': False, 'error': 'Invalid account ids'}), 400
    try:
        msg = MIMEMultipart(); msg['From'] = from_account['email_address']; msg['To'] = to_account['email_address']
        msg['Subject'] = subject; msg['Date'] = formatdate(); msg['Message-ID'] = make_msgid(); msg.attach(MIMEText(body, 'plain'))
        smtp_host = os.environ.get('SMTP_PROXY_HOST', '127.0.0.1')
        smtp_port = int(os.environ.get('SMTP_PROXY_PORT', '8587'))
        smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=5); smtp.send_message(msg); smtp.quit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@diagnostics_bp.route('/api/test/check-interception')
@login_required
def api_test_check_interception():
    try:
        subject = request.args.get('subject')
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        email = cursor.execute(
            """
            SELECT id, subject, interception_status, created_at
            FROM email_messages
            WHERE subject = ? AND interception_status = 'INTERCEPTED'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (subject,),
        ).fetchone(); conn.close()
        if email:
            return jsonify({'success': True, 'email_id': email['id'], 'subject': email['subject'], 'interception_status': email['interception_status']})
        return jsonify({'success': False, 'message': 'Email not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@diagnostics_bp.route('/api/test/verify-delivery', methods=['POST'])
@login_required
def api_test_verify_delivery():
    data = request.get_json(silent=True) or {}
    account_id = data.get('account_id'); subject = (data.get('subject') or '').strip()
    if not (account_id and subject):
        return jsonify({'success': False, 'error': 'Missing account_id or subject'}), 400
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    account = cur.execute("SELECT id FROM email_accounts WHERE id=?", (account_id,)).fetchone(); conn.close()
    if not account:
        return jsonify({'success': False, 'error': 'Invalid account ID'}), 400
    c2 = sqlite3.connect(DB_PATH).cursor(); hit = c2.execute("SELECT 1 FROM email_messages WHERE subject=? LIMIT 1", (subject,)).fetchone(); c2.connection.close()
    return jsonify({'success': bool(hit), 'source': 'local-db'})


@diagnostics_bp.route('/api/test/send-bi-directional', methods=['POST'])
@login_required
def api_test_send_bi_directional():
    """Send bi-directional test email (Hostinger↔Gmail) for automated interception testing"""
    data = request.get_json(silent=True) or {}
    direction = data.get('direction')  # 'hostinger-to-gmail' or 'gmail-to-hostinger'
    subject = data.get('subject') or f'Test Email {datetime.now().strftime("%H:%M:%S")}'

    if direction not in ['hostinger-to-gmail', 'gmail-to-hostinger']:
        return jsonify({'success': False, 'error': 'Invalid direction parameter'}), 400

    # Permanent account email addresses
    HOSTINGER_EMAIL = 'mcintyre@corrinbox.com'
    GMAIL_EMAIL = 'ndayijecika@gmail.com'

    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; cur = conn.cursor()

        # Determine sender and recipient based on direction
        if direction == 'hostinger-to-gmail':
            sender_email = HOSTINGER_EMAIL
            recipient_email = GMAIL_EMAIL
        else:  # gmail-to-hostinger
            sender_email = GMAIL_EMAIL
            recipient_email = HOSTINGER_EMAIL

        # Look up sender account
        sender_account = cur.execute(
            "SELECT * FROM email_accounts WHERE email_address=? AND is_active=1",
            (sender_email,)
        ).fetchone()

        if not sender_account:
            conn.close()
            return jsonify({'success': False, 'error': f'Sender account not found: {sender_email}'}), 404

        # Decrypt credentials
        smtp_password = decrypt_credential(sender_account['smtp_password']) if sender_account['smtp_password'] else None
        if not smtp_password:
            conn.close()
            return jsonify({'success': False, 'error': 'SMTP password not configured'}), 400

        conn.close()

        # Build email message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg['Date'] = formatdate()
        msg['Message-ID'] = make_msgid()

        body = f"""This is a bi-directional test email for automatic interception validation.

Direction: {direction}
Sent from: {sender_email}
Sent to: {recipient_email}
Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

This email should be automatically intercepted by the polling watcher at the recipient's INBOX.

Test flow:
1. {sender_email} sends → {recipient_email} receives
2. Email automatically intercepted (HELD status)
3. Verify in database and UI
"""
        msg.attach(MIMEText(body, 'plain'))

        # Send via provider SMTP (not proxy)
        smtp_host = sender_account['smtp_host']
        smtp_port = int(sender_account['smtp_port'])
        smtp_use_ssl = bool(sender_account['smtp_use_ssl'])
        smtp_username = sender_account['smtp_username'] or sender_email

        if smtp_use_ssl and smtp_port == 465:
            # Direct SSL connection
            smtp = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            # STARTTLS connection (port 587)
            smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()

        smtp.login(smtp_username, smtp_password)
        smtp.send_message(msg)
        smtp.quit()

        return jsonify({
            'success': True,
            'direction': direction,
            'sender': sender_email,
            'recipient': recipient_email,
            'subject': subject,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@diagnostics_bp.route('/api/diagnostics/<int:account_id>')
@login_required
def api_account_diagnostics(account_id: int):
    """Run SMTP/IMAP diagnostics for a single account and return JSON.
    Safe: does not return decrypted secrets, only status messages.
    """
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        acc = cur.execute("SELECT * FROM email_accounts WHERE id=?", (account_id,)).fetchone()
        conn.close()
        if not acc:
            return jsonify({'error': 'Account not found'}), 404

        # Prepare credentials
        imap_user = str(acc['imap_username'] or '')
        smtp_user = str(acc['smtp_username'] or '')
        imap_pwd = decrypt_credential(acc['imap_password']) if acc['imap_password'] else ''
        smtp_pwd = decrypt_credential(acc['smtp_password']) if acc['smtp_password'] else ''

        # Run tests (best-effort if creds missing)
        imap_ok = False; smtp_ok = False
        imap_msg = 'IMAP username/password required'
        smtp_msg = 'SMTP username/password required'

        if imap_user and imap_pwd:
            imap_ok, imap_msg = _test_email_connection(
                'imap', str(acc['imap_host'] or ''), int(acc['imap_port'] or 993), imap_user, imap_pwd, bool(acc['imap_use_ssl'])
            )
        if smtp_user and smtp_pwd:
            smtp_ok, smtp_msg = _test_email_connection(
                'smtp', str(acc['smtp_host'] or ''), int(acc['smtp_port'] or 465), smtp_user, smtp_pwd, bool(acc['smtp_use_ssl'])
            )

        payload = {
            'account_name': acc['account_name'],
            'email_address': acc['email_address'],
            'smtp_test': {'success': bool(smtp_ok), 'message': smtp_msg},
            'imap_test': {'success': bool(imap_ok), 'message': imap_msg},
            'timestamp': datetime.now().isoformat()
        }
        return jsonify(payload)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
