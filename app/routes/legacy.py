"""
Legacy compatibility endpoints blueprint.
Keeps old URLs functioning while the app is fully modularized.
"""
from flask import Blueprint, jsonify, redirect, url_for
from flask_login import login_required


legacy_bp = Blueprint('legacy', __name__)


@legacy_bp.route('/api/held', methods=['GET'])
@login_required
def legacy_api_held():
    """Deprecated legacy alias -> /api/interception/held"""
    return redirect(url_for('interception_bp.api_interception_held'), code=307)


@legacy_bp.route('/api/emails/pending', methods=['GET'])
def legacy_api_pending():
    """Deprecated legacy pending messages endpoint guidance"""
    return jsonify({
        'deprecated': True,
        'use': '/api/inbox?status=PENDING',
        'note': 'Interception (HELD) now separate via /api/interception/held'
    })
