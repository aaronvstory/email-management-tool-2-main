"""Inbox Blueprint - Phase 1C Route Modularization

Extracted from simple_app.py
Route: /inbox - Now redirects to unified email management
"""
import sqlite3
from flask import Blueprint, render_template, request, redirect
from flask_login import login_required

from app.utils.db import DB_PATH


inbox_bp = Blueprint('inbox', __name__)


@inbox_bp.route('/inbox')
@login_required
def inbox():
    """Redirect to unified email management interface"""
    selected_account = request.args.get('account_id', type=int)
    
    redirect_url = '/emails-unified?status=ALL'
    if selected_account:
        redirect_url += f'&account_id={selected_account}'
    
    return redirect(redirect_url)


@inbox_bp.route('/inbox-legacy')
@login_required
def inbox_legacy():
    """Legacy inbox view - kept for reference"""
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

    selected_account = request.args.get('account_id', type=int)

    if selected_account:
        emails = cursor.execute(
            """
            SELECT em.*, ea.account_name, ea.email_address
            FROM email_messages em
            LEFT JOIN email_accounts ea ON em.account_id = ea.id
            WHERE em.account_id = ?
            ORDER BY em.created_at DESC
            LIMIT 100
            """,
            (selected_account,),
        ).fetchall()
    else:
        emails = cursor.execute(
            """
            SELECT em.*, ea.account_name, ea.email_address
            FROM email_messages em
            LEFT JOIN email_accounts ea ON em.account_id = ea.id
            ORDER BY em.created_at DESC
            LIMIT 100
            """
        ).fetchall()

    conn.close()

    return render_template(
        'inbox.html', emails=emails, accounts=accounts, selected_account=selected_account
    )
