"""
Compose Blueprint - Email composition and sending

Extracted from simple_app.py (Phase 1C - Blueprint Migration)
Routes: /compose (GET, POST)
"""

import sqlite3
import smtplib
import ssl
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import make_msgid

from app.utils.db import DB_PATH
from app.utils.crypto import decrypt_credential
from app.utils.email_helpers import negotiate_smtp as _negotiate_smtp


# Create blueprint
compose_bp = Blueprint('compose', __name__)


@compose_bp.route('/compose', methods=['GET', 'POST'])
@login_required
def compose_email():
    """Compose and send a new email"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all active email accounts for FROM dropdown
    accounts = cursor.execute("""
        SELECT id, account_name, email_address
        FROM email_accounts
        WHERE is_active = 1
        ORDER BY account_name
    """).fetchall()

    if request.method == 'POST':
        if request.is_json:
            data = request.get_json(silent=True) or {}
            from_account_id = data.get('from_account')
            to_address = (data.get('to') or '').strip()
            cc_address = (data.get('cc') or '').strip()
            subject = (data.get('subject') or '').strip()
            body = (data.get('body') or '').strip()
        else:
            from_account_id = request.form.get('from_account', type=int)
            to_address = request.form.get('to', '').strip()
            cc_address = request.form.get('cc', '').strip()
            subject = request.form.get('subject', '').strip()
            body = request.form.get('body', '').strip()

        if not from_account_id or not to_address or not subject or not body:
            if request.is_json:
                conn.close(); return jsonify({'ok': False, 'error': 'missing-fields'}), 400
            flash('Please fill in all required fields', 'error')
            conn.close(); return render_template('compose.html', accounts=accounts)

        account = cursor.execute("SELECT * FROM email_accounts WHERE id = ?", (from_account_id,)).fetchone()
        if not account:
            if request.is_json:
                conn.close(); return jsonify({'ok': False, 'error': 'invalid-account'}), 400
            flash('Invalid sending account', 'error')
            conn.close(); return render_template('compose.html', accounts=accounts)

        smtp_password = decrypt_credential(account['smtp_password'])
        if not smtp_password:
            if request.is_json:
                conn.close(); return jsonify({'ok': False, 'error': 'decrypt-failed'}), 500
            flash('Failed to decrypt SMTP password. Re-configure the account.', 'error')
            conn.close(); return render_template('compose.html', accounts=accounts)

        msg = MIMEMultipart()
        msg['From'] = account['email_address']
        msg['To'] = to_address
        if cc_address:
            msg['Cc'] = cc_address
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        try:
            smtp_host = account['smtp_host']
            smtp_port = int(account['smtp_port']) if account['smtp_port'] else 587
            smtp_username = account['smtp_username']
            if not msg.get('Message-ID'):
                msg['Message-ID'] = make_msgid()

            # Use stored settings first (normalized by port), fallback to negotiate only on failure.
            context = ssl.create_default_context()
            def _connect(host: str, port: int, use_ssl_flag: bool):
                if use_ssl_flag:
                    return smtplib.SMTP_SSL(host, port, context=context)
                s = smtplib.SMTP(host, port)
                s.ehlo(); s.starttls(context=context); s.ehlo()
                return s

            # Normalize by common ports
            pref_use_ssl = True if smtp_port == 465 else False if smtp_port == 587 else bool(account['smtp_use_ssl'])
            try:
                server = _connect(smtp_host, smtp_port, pref_use_ssl)
            except Exception:
                # Fallback: probe and persist corrected values
                chosen = _negotiate_smtp(smtp_host, smtp_username, smtp_password, smtp_port, bool(account['smtp_use_ssl']))
                smtp_host = str(chosen['smtp_host']); smtp_port = int(chosen['smtp_port']); pref_use_ssl = bool(chosen['smtp_use_ssl'])
                server = _connect(smtp_host, smtp_port, pref_use_ssl)
                try:
                    # Persist corrected choice for future sends
                    cur2 = conn.cursor()
                    cur2.execute(
                        "UPDATE email_accounts SET smtp_host=?, smtp_port=?, smtp_use_ssl=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (smtp_host, smtp_port, 1 if pref_use_ssl else 0, int(from_account_id)),
                    ); conn.commit()
                except Exception:
                    pass
            server.login(smtp_username, smtp_password)
            recipients_all = [to_address] + ([cc_address] if cc_address else [])
            server.sendmail(account['email_address'], recipients_all, msg.as_string())
            server.quit()
            # Record outbound message in DB for dashboard visibility
            try:
                cur = conn.cursor()
                import json as _json
                cur.execute(
                    """
                    INSERT INTO email_messages
                    (message_id, sender, recipients, subject, body_text, body_html, raw_content,
                     account_id, direction, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'outbound', 'SENT', datetime('now'))
                    """,
                    (
                        msg['Message-ID'],
                        account['email_address'],
                        _json.dumps(recipients_all),
                        subject,
                        body,
                        '',
                        msg.as_string(),
                        int(from_account_id),
                    ),
                )
                conn.commit()
            except Exception:
                pass
        except Exception as e:
            if request.is_json:
                conn.close(); return jsonify({'ok': False, 'error': str(e)}), 500
            flash(f'Error sending email: {e}', 'error')
            conn.close(); return render_template('compose.html', accounts=accounts)

        if request.is_json:
            conn.close(); return jsonify({'ok': True})
        flash('Email sent successfully!', 'success')
        conn.close(); return redirect(url_for('inbox.inbox'))

    conn.close()
    return render_template('compose.html', accounts=accounts)
