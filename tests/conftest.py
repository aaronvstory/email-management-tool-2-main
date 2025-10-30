"""
Pytest configuration and fixtures for Email Management Tool tests.

This conftest.py provides shared fixtures for:
- Flask app instances
- Authenticated test clients
- Database sessions with isolation
- Mock IMAP/SMTP connections
"""
import os
import sys
import tempfile
import sqlite3
from pathlib import Path
from typing import Generator
import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.utils.db import get_db

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope='session')
def test_db_path() -> Generator[str, None, None]:
    """Create a temporary database for testing session."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture(scope='function')
def db_session(test_db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """
    Provide an isolated database connection for each test.

    Uses WAL mode and row factory for dict-like access.
    Automatically rolls back after each test.
    """
    conn = sqlite3.connect(test_db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=30000')

    # Create schema
    _create_test_schema(conn)

    yield conn

    # Rollback and close
    conn.rollback()
    conn.close()


def _create_test_schema(conn: sqlite3.Connection) -> None:
    """Create minimal test schema for email management."""
    cursor = conn.cursor()

    # Users table - mirrors init_database()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'admin',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Email accounts table (keeps superset of production columns)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT,
            email_address TEXT UNIQUE NOT NULL,
            imap_host TEXT NOT NULL,
            imap_port INTEGER DEFAULT 993,
            imap_username TEXT,
            imap_password TEXT,
            imap_use_ssl INTEGER DEFAULT 1,
            smtp_host TEXT,
            smtp_port INTEGER DEFAULT 587,
            smtp_username TEXT,
            smtp_password TEXT,
            smtp_use_ssl INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            provider_type TEXT DEFAULT 'custom',
            last_checked TEXT,
            last_error TEXT,
            quarantine_folder TEXT DEFAULT 'Quarantine',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Email messages table (align with production schema)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT,
            account_id INTEGER,
            direction TEXT,
            status TEXT DEFAULT 'PENDING',
            interception_status TEXT,
            sender TEXT,
            recipients TEXT,
            subject TEXT,
            body_text TEXT,
            body_html TEXT,
            headers TEXT,
            attachments TEXT,
            original_uid INTEGER,
            original_internaldate TEXT,
            original_message_id TEXT,
            edited_message_id TEXT,
            quarantine_folder TEXT,
            raw_content TEXT,
            raw_path TEXT,
            risk_score REAL DEFAULT 0.0,
            keywords_matched TEXT,
            moderation_reason TEXT,
            moderator_id INTEGER,
            reviewer_id INTEGER,
            review_notes TEXT,
            approved_by TEXT,
            latency_ms INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            processed_at TEXT,
            action_taken_at TEXT,
            reviewed_at TEXT,
            sent_at TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            attachments_manifest TEXT,
            version INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (account_id) REFERENCES email_accounts (id)
        )
    ''')

    # Attachment storage metadata (Phase 2-4)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_attachments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            mime_type TEXT,
            size INTEGER,
            sha256 TEXT,
            disposition TEXT,
            content_id TEXT,
            is_original INTEGER NOT NULL DEFAULT 0,
            is_staged INTEGER NOT NULL DEFAULT 0,
            storage_path TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(email_id, filename, is_original, is_staged)
        )
    ''')

    # Release coordination tables (Phase 4)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_release_locks(
            email_id INTEGER PRIMARY KEY,
            acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS idempotency_keys(
            key TEXT PRIMARY KEY,
            email_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            response_json TEXT
        )
    ''')

    # Moderation rules table (include legacy + modern columns)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS moderation_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            rule_name TEXT,
            keyword TEXT,
            keywords TEXT,
            action TEXT DEFAULT 'HOLD',
            priority INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            rule_type TEXT,
            condition_field TEXT,
            condition_operator TEXT,
            condition_value TEXT
        )
    ''')

    # Audit log table (match app.services.audit)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT NOT NULL,
            user_id INTEGER,
            email_id INTEGER,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Worker heartbeats table (includes test-only should_stop flag)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS worker_heartbeats (
            worker_id TEXT PRIMARY KEY,
            should_stop INTEGER DEFAULT 0,
            last_heartbeat TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT,
            error_count INTEGER DEFAULT 0
        )
    ''')

    # Helpful index for release logic (mirrors init_database)
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_email_messages_msgid_unique
        ON email_messages(message_id)
        WHERE message_id IS NOT NULL
    ''')

    # Create test user (admin/admin123)
    from werkzeug.security import generate_password_hash
    cursor.execute(
        'INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)',
        ('admin', generate_password_hash('admin123'), 'admin')
    )

    conn.commit()


@pytest.fixture(scope='function')
def app(test_db_path: str, monkeypatch) -> Flask:
    """
    Create Flask app instance for testing.

    Uses test database and disables CSRF for easier testing.
    """
    # Initialize database schema BEFORE setting up the app
    conn = sqlite3.connect(test_db_path)
    _create_test_schema(conn)
    conn.close()
    
    # Set test environment
    monkeypatch.setenv('DB_PATH', test_db_path)
    monkeypatch.setenv('TEST_DB_PATH', test_db_path)
    monkeypatch.setenv('TESTING', '1')
    monkeypatch.setenv('ENABLE_WATCHERS', '0')  # Disable IMAP watchers in tests
    monkeypatch.setenv('FLASK_SECRET_KEY', 'test-secret-key-for-testing-only')
    monkeypatch.setenv('REQUIRE_LIVE_CREDENTIALS', '0')  # Don't require live creds in tests

    # Import app directly (simple_app.py creates the app module-level)
    import simple_app

    app = simple_app.app
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for easier testing

    return app


@pytest.fixture(scope='function')
def client(app: Flask) -> FlaskClient:
    """Provide a test client for making requests."""
    return app.test_client()


@pytest.fixture(scope='function')
def authenticated_client(client: FlaskClient) -> FlaskClient:
    """
    Provide an authenticated test client.

    Automatically logs in as admin user.
    """
    # Seed dashboard data to avoid template failures during login redirect
    conn = get_db()
    conn.execute(
        """
        INSERT OR IGNORE INTO email_messages
        (id, interception_status, status, subject, body_text, recipients, direction, created_at)
        VALUES (123456, 'HELD', 'PENDING', 'Seed Subject', 'Seed Body', 'seed@example.com', 'inbound', datetime('now'))
        """
    )
    conn.commit()
    conn.close()

    # Login
    client.post('/login', data={
        'username': 'admin',
        'password': 'admin123'
    }, follow_redirects=False)

    return client


@pytest.fixture(scope='function')
def mock_imap_connection():
    """
    Provide a mock IMAP connection for testing.

    Use this to avoid hitting real email servers in tests.
    """
    from unittest.mock import MagicMock

    mock_imap = MagicMock()
    mock_imap.select.return_value = ('OK', [b'1'])
    mock_imap.search.return_value = ('OK', [b'1 2 3'])
    mock_imap.fetch.return_value = ('OK', [(b'1', b'mock email data')])
    mock_imap.uid.return_value = ('OK', [b'1'])
    mock_imap.logout.return_value = ('OK', [])

    return mock_imap


@pytest.fixture(scope='function')
def mock_smtp_connection():
    """
    Provide a mock SMTP connection for testing.

    Use this to avoid sending real emails in tests.
    """
    from unittest.mock import MagicMock

    mock_smtp = MagicMock()
    mock_smtp.login.return_value = (235, b'Authentication successful')
    mock_smtp.sendmail.return_value = {}
    mock_smtp.quit.return_value = (221, b'Bye')

    return mock_smtp


@pytest.fixture(scope='function')
def sample_email_message():
    """Provide a sample email message for testing."""
    return {
        'id': 1,
        'account_id': 1,
        'message_id': '<test@example.com>',
        'sender': 'sender@example.com',
        'recipients': 'recipient@example.com',
        'subject': 'Test Email',
        'body_text': 'This is a test email body.',
        'body_html': '<p>This is a test email body.</p>',
        'raw_content': b'From: sender@example.com\r\nTo: recipient@example.com\r\nSubject: Test Email\r\n\r\nThis is a test email body.',
        'status': 'PENDING',
        'interception_status': None,
        'risk_score': 0.0,
        'direction': 'inbound'
    }


@pytest.fixture(scope='function')
def sample_account():
    """Provide a sample email account for testing."""
    return {
        'id': 1,
        'email_address': 'test@example.com',
        'imap_host': 'imap.example.com',
        'imap_port': 993,
        'imap_username': 'test@example.com',
        'imap_password': 'encrypted_password',
        'imap_use_ssl': 1,
        'smtp_host': 'smtp.example.com',
        'smtp_port': 587,
        'smtp_username': 'test@example.com',
        'smtp_password': 'encrypted_password',
        'smtp_use_ssl': 0,
        'is_active': 1,
        'quarantine_folder': 'Quarantine'
    }


# Pytest configuration hooks
def pytest_configure(config):
    """Configure pytest with custom settings."""
    config.addinivalue_line(
        "markers", "live: mark test as requiring live email accounts"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as security-related"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Auto-mark tests in certain directories
        if "live" in str(item.fspath):
            item.add_marker(pytest.mark.live)
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
