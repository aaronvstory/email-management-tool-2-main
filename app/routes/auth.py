"""Authentication Blueprint - Phase 1B Route Modularization

Extracted from simple_app.py lines 567-607
Routes: /, /login, /logout
Phase 2: Added rate limiting for security hardening
"""
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import sqlite3
from app.utils.db import DB_PATH
from app.models.simple_user import SimpleUser
from app.services.audit import log_action

# Import limiter from extensions
from app import extensions

auth_bp = Blueprint('auth', __name__)
log = logging.getLogger(__name__)


@auth_bp.route('/')
def index():
    """Redirect to dashboard or login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
@extensions.limiter.limit("5 per minute; 20 per hour", methods=["POST"])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        user = cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username = ?",
                              (username,)).fetchone()
        conn.close()

        if not password:
            log.warning("[auth::login] missing password input", extra={'username': username})
        if user and password and check_password_hash(user[2], password):
            user_obj = SimpleUser(user[0], user[1], user[3])
            login_user(user_obj)

            # Log the action
            log_action('LOGIN', user[0], None, f"User {username} logged in")
            log.info("[auth::login] login successful", extra={'user_id': user[0], 'username': username})

            return redirect(url_for('dashboard.dashboard'))

        log.warning("[auth::login] login failed", extra={'username': username})
        flash('Invalid username or password', 'error')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout"""
    log_action('LOGOUT', current_user.id, None, f"User {current_user.username} logged out")
    logout_user()
    return redirect(url_for('auth.login'))
