"""Moderation Rules Blueprint - Phase 1B Route Modularization

Extracted from simple_app.py lines 859-875
Routes: /rules and lightweight JSON API for rule management
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import sqlite3
from app.utils.db import DB_PATH
from app.extensions import csrf

moderation_bp = Blueprint('moderation', __name__)


@moderation_bp.route('/rules')
@login_required
def rules():
    """Moderation rules page"""
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard.dashboard'))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM moderation_rules ORDER BY priority DESC").fetchall()
    # Normalize schema -> template expects: rule_name, rule_type, condition_value, action, priority, is_active
    cols = [r[1] for r in cursor.execute("PRAGMA table_info(moderation_rules)").fetchall()]
    normalized = []
    for r in rows:
        d = dict(r)
        if 'rule_type' in cols and 'condition_value' in cols:
            normalized.append({
                'id': d.get('id'),
                'rule_name': d.get('rule_name'),
                'rule_type': d.get('rule_type') or 'KEYWORD',
                'condition_value': d.get('condition_value') or d.get('keyword') or '',
                'action': d.get('action') or 'HOLD',
                'priority': d.get('priority') or 50,
                'is_active': d.get('is_active', 1),
            })
        else:
            # Legacy schema: keyword-only
            normalized.append({
                'id': d.get('id'),
                'rule_name': d.get('rule_name'),
                'rule_type': 'KEYWORD',
                'condition_value': d.get('keyword') or '',
                'action': d.get('action') or 'HOLD',
                'priority': d.get('priority') or 50,
                'is_active': d.get('is_active', 1),
            })
    conn.close()
    return render_template('rules.html', rules=normalized)


@moderation_bp.route('/api/rules', methods=['POST'])
@csrf.exempt  # JSON posts from JS; CSRF token wiring varies across pages
@login_required
def api_create_rule():
    """Create a moderation rule (supports legacy and extended schemas)."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    payload = request.get_json(silent=True) or {}
    name = str(payload.get('rule_name') or '').strip()
    rule_type = str(payload.get('rule_type') or 'KEYWORD').strip().upper()
    pattern = str(payload.get('pattern') or '').strip()
    action = str(payload.get('action') or 'HOLD').strip().upper()
    try:
        priority = int(payload.get('priority') or 50)
    except Exception:
        priority = 50
    if not (name and pattern):
        return jsonify({'success': False, 'error': 'rule_name and pattern required'}), 400

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(moderation_rules)").fetchall()]
    field_map = {
        'KEYWORD': 'BODY',
        'SENDER': 'SENDER',
        'RECIPIENT': 'RECIPIENT',
        'DOMAIN': 'SENDER_DOMAIN',
        'ATTACHMENT': 'ATTACHMENT',
        'SUBJECT': 'SUBJECT',
        'REGEX': 'BODY',
    }
    operator = 'REGEX' if rule_type == 'REGEX' else 'CONTAINS'
    condition_field = field_map.get(rule_type, 'BODY')
    try:
        if 'rule_type' in cols and 'condition_value' in cols:
            cur.execute(
                """
                INSERT INTO moderation_rules
                (rule_name, rule_type, condition_field, condition_operator, condition_value, action, priority, is_active)
                VALUES(?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (name, rule_type, condition_field, operator, pattern, action, priority),
            )
        else:
            # Legacy keyword-based schema
            cur.execute(
                """
                INSERT INTO moderation_rules
                (rule_name, keyword, action, priority, is_active)
                VALUES(?, ?, ?, ?, 1)
                """,
                (name, pattern, action, priority),
            )
        conn.commit()
        rid = cur.lastrowid
        return jsonify({'success': True, 'id': rid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@moderation_bp.route('/api/rules/<int:rule_id>', methods=['PUT'])
@csrf.exempt
@login_required
def api_update_rule(rule_id: int):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    payload = request.get_json(silent=True) or {}
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(moderation_rules)").fetchall()]
    fields=[]; values=[]
    if 'rule_name' in payload: fields.append('rule_name=?'); values.append(payload['rule_name'])
    if 'priority' in payload: fields.append('priority=?'); values.append(int(payload['priority']))
    if 'is_active' in payload: fields.append('is_active=?'); values.append(1 if payload['is_active'] else 0)
    if 'action' in payload: fields.append('action=?'); values.append(str(payload['action']).upper())
    # Pattern/type may be stored in extended or legacy schema
    if 'rule_type' in cols and 'condition_value' in cols:
        if 'rule_type' in payload:
            field_map = {
                'KEYWORD': 'BODY',
                'SENDER': 'SENDER',
                'RECIPIENT': 'RECIPIENT',
                'DOMAIN': 'SENDER_DOMAIN',
                'ATTACHMENT': 'ATTACHMENT',
                'SUBJECT': 'SUBJECT',
                'REGEX': 'BODY',
            }
            rtype = str(payload['rule_type']).upper()
            operator = 'REGEX' if rtype == 'REGEX' else 'CONTAINS'
            fields.extend(['rule_type=?', 'condition_field=?', 'condition_operator=?'])
            values.extend([rtype, field_map.get(rtype, 'BODY'), operator])
        if 'condition_value' in payload:
            fields.append('condition_value=?'); values.append(payload['condition_value'])
    if 'pattern' in payload and 'keyword' in cols:
        fields.append('keyword=?'); values.append(payload['pattern'])
    if not fields:
        conn.close(); return jsonify({'success': False, 'error': 'No fields to update'}), 400
    values.append(rule_id)
    cur.execute(f"UPDATE moderation_rules SET {', '.join(fields)} WHERE id=?", values); conn.commit(); conn.close()
    return jsonify({'success': True})


@moderation_bp.route('/api/rules/<int:rule_id>', methods=['DELETE'])
@csrf.exempt
@login_required
def api_delete_rule(rule_id: int):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute('DELETE FROM moderation_rules WHERE id=?', (rule_id,)); conn.commit(); conn.close()
    return jsonify({'success': True})
