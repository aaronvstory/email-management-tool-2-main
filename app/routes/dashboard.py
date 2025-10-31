"""Dashboard Blueprint - Phase 1B Route Modularization

Extracted from simple_app.py lines 608-676
Routes: /dashboard, /dashboard/<tab>, /test-dashboard
"""
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
import sqlite3
import json
from app.utils.db import DB_PATH, get_db, fetch_counts

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@dashboard_bp.route('/dashboard/<tab>')
@login_required
def dashboard(tab='overview'):
    """Main dashboard with tab navigation"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get email accounts for account selector
    accounts = cursor.execute("""
        SELECT id, account_name, email_address, imap_host, imap_port, smtp_host, smtp_port,
               is_active, last_checked, last_error
        FROM email_accounts
        ORDER BY account_name
    """).fetchall()

    # Get selected account from query params
    selected_account_id = request.args.get('account_id', None)

    # Get statistics (filtered by account if selected)
    if selected_account_id:
        stats = fetch_counts(account_id=int(selected_account_id), include_outbound=False)

        # Get recent emails for selected account
        recent_emails = cursor.execute("""
            SELECT id, sender, recipients, subject, status, interception_status, created_at, body_text
            FROM email_messages
            WHERE account_id = ? AND (direction IS NULL OR direction!='outbound')
            ORDER BY created_at DESC
            LIMIT 20
        """, (selected_account_id,)).fetchall()
    else:
        # Get overall statistics
        stats = fetch_counts(include_outbound=False)

        # Get recent emails from all accounts
        recent_emails = cursor.execute("""
            SELECT id, sender, recipients, subject, status, interception_status, created_at, body_text
            FROM email_messages
            WHERE (direction IS NULL OR direction!='outbound')
            ORDER BY created_at DESC
            LIMIT 20
        """).fetchall()

    # Get active rules count
    active_rules = cursor.execute("SELECT COUNT(*) FROM moderation_rules WHERE is_active = 1").fetchone()[0]

    # Get all moderation rules for Rules tab (schema-aware: support legacy table without new columns)
    rule_table_info = cursor.execute("PRAGMA table_info(moderation_rules)").fetchall()
    rule_columns = {col[1] for col in rule_table_info}

    # Full set we'd like, ordered for presentation
    desired_cols = [
        "id",
        "rule_name",
        "rule_type",
        "condition_field",
        "condition_operator",
        "condition_value",
        "action",
        "priority",
        "is_active",
        "created_at",
    ]
    # Only select what exists in this DB
    select_cols = [c for c in desired_cols if c in rule_columns]
    if not select_cols:
        # Extremely defensive fallback: at least select id + rule_name if present
        minimal = [c for c in ["id", "rule_name"] if c in rule_columns]
        select_cols = minimal or ["id"]

    rules_query = f"SELECT {', '.join(select_cols)} FROM moderation_rules ORDER BY " \
                  f"{'priority DESC, ' if 'priority' in rule_columns else ''}{'rule_name' if 'rule_name' in rule_columns else 'id'}"
    raw_rules = cursor.execute(rules_query).fetchall()

    # Normalize rows to include missing keys so templates never 500
    def _norm_rule(row):
        d = dict(row)
        # Provide safe defaults for columns that might not exist in legacy DBs
        if "rule_type" not in d:
            d["rule_type"] = "keyword"
        if "condition_field" not in d:
            d["condition_field"] = None
        if "condition_operator" not in d:
            d["condition_operator"] = None
        if "condition_value" not in d:
            d["condition_value"] = None
        if "action" not in d:
            d["action"] = d.get("action") or "hold"
        if "priority" not in d:
            d["priority"] = d.get("priority") or 100
        if "is_active" not in d:
            d["is_active"] = d.get("is_active") if d.get("is_active") is not None else 1
        if "created_at" not in d:
            d["created_at"] = d.get("created_at") or ""
        if "rule_name" not in d:
            # absolute minimum for template stability
            d["rule_name"] = f"Rule #{d.get('id', '?')}"
        return d

    rules = [_norm_rule(r) for r in raw_rules]

    # Normalize data for template
    email_payload = []
    for row in recent_emails:
        record = dict(row)
        recipients = record.get('recipients')
        if recipients:
            try:
                if isinstance(recipients, str):
                    # Attempt JSON parse, fallback to CSV
                    parsed = json.loads(recipients)
                    if isinstance(parsed, list):
                        record['recipients'] = parsed
                    else:
                        record['recipients'] = [recipients]
                else:
                    record['recipients'] = list(recipients)
            except json.JSONDecodeError:
                record['recipients'] = [addr.strip() for addr in recipients.split(',') if addr.strip()]
        else:
            record['recipients'] = []

        body = record.get('body_text') or ''
        preview = ' '.join(body.split())[:160]
        record['preview_snippet'] = preview

        email_payload.append(record)

    conn.close()

    return render_template('dashboard_unified.html',
                         stats=stats,
                         recent_emails=email_payload,
                         active_rules=active_rules,
                         rules=rules,
                         accounts=accounts,
                         selected_account_id=selected_account_id,
                         active_tab=tab,
                         pending_count=stats['pending'],
                         user=current_user)


@dashboard_bp.route('/test-dashboard')
@login_required
def test_dashboard():
    """Test dashboard redirect"""
    return redirect(url_for('dashboard.dashboard'))
