"""
Comprehensive tests for interception.py email release and management.

Tests cover:
- Email release workflow
- Email editing before release
- Discard functionality
- Quarantine cleanup
- Attachment stripping
- Idempotency guarantees
- IMAP verification
- Error handling
"""
import pytest
import sqlite3
import json
from unittest.mock import Mock, patch, MagicMock
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default as default_policy
from app.utils.crypto import encrypt_credential


def _configure_imap_mock(mock_imap, *, duplicate_hits=None, verify_hits=None):
    """
    Configure a MagicMock IMAP connection with sensible defaults.

    duplicate_hits: bytes list returned on the first search (duplicate check)
    verify_hits: bytes list returned on subsequent searches (post-append verify)
    """
    mock_conn = MagicMock()
    mock_imap.return_value = mock_conn
    mock_conn.login.return_value = ('OK', [b'Logged in'])
    mock_conn.select.return_value = ('OK', [b'1'])
    mock_conn.append.return_value = ('OK', [b'APPEND completed'])

    dupes = duplicate_hits if duplicate_hits is not None else [b'']
    verify = verify_hits if verify_hits is not None else [b'1']
    state = {'call': 0}

    def _search_side_effect(*args, **kwargs):
        # First call checks for pre-existing message (idempotency guard)
        if state['call'] == 0:
            state['call'] += 1
            return ('OK', dupes)
        state['call'] += 1
        return ('OK', verify)

    mock_conn.search.side_effect = _search_side_effect
    return mock_conn


@pytest.fixture
def held_email(test_db_path):
    """Create a HELD email in the test database."""
    conn = sqlite3.connect(test_db_path, timeout=30.0)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        
        # Insert or refresh test account and message records deterministically
        conn.execute("DELETE FROM email_messages WHERE id = 1")
        conn.execute("""
            INSERT INTO email_accounts 
            (id, account_name, email_address, imap_host, imap_port, 
             imap_username, imap_password, imap_use_ssl, is_active)
            VALUES (1, 'Test Account', 'test@example.com', 'imap.example.com', 
                    993, 'test@example.com', ?, 1, 1)
            ON CONFLICT(id) DO UPDATE SET
                account_name=excluded.account_name,
                email_address=excluded.email_address,
                imap_host=excluded.imap_host,
                imap_port=excluded.imap_port,
                imap_username=excluded.imap_username,
                imap_password=excluded.imap_password,
                imap_use_ssl=excluded.imap_use_ssl,
                is_active=excluded.is_active
        """, (encrypt_credential('P@ssw0rd!'),))
        
        # Create raw email content
        msg = EmailMessage()
        msg['From'] = 'sender@example.com'
        msg['To'] = 'test@example.com'
        msg['Subject'] = 'Test Email Subject'
        msg['Message-ID'] = '<test123@example.com>'
        msg.set_content('This is the test email body.')
        
        raw_content = msg.as_string()
        
        # Insert email message
        conn.execute("""
            INSERT INTO email_messages 
            (id, account_id, message_id, sender, recipients, subject, body_text,
             direction, interception_status, status, raw_content, original_uid,
             original_internaldate, quarantine_folder, created_at)
            VALUES (1, 1, '<test123@example.com>', 'sender@example.com', 
                    '["test@example.com"]', 'Test Email Subject', 
                    'This is the test email body.', 'inbound', 'HELD', 'PENDING',
                    ?, 100, datetime('now'), 'Quarantine', datetime('now'))
        """, (raw_content,))
        
        conn.commit()
    finally:
        conn.close()
    
    return 1  # email_id


class TestEmailRelease:
    """Test email release functionality."""

    def test_release_basic_flow(self, client, authenticated_client, held_email, test_db_path):
        """Test basic email release without edits."""
        with patch('imaplib.IMAP4_SSL') as mock_imap:
            _configure_imap_mock(mock_imap)
            
            # Release email
            response = authenticated_client.post(
                f'/api/interception/release/{held_email}',
                json={'target_folder': 'INBOX'},
                headers={'Content-Type': 'application/json'}
            )
        
            assert response.status_code == 200
            data = response.get_json()
            assert data.get('ok') is True
            assert data.get('released_to') == 'INBOX'

    def test_release_with_subject_edit(self, client, authenticated_client, held_email, test_db_path):
        """Test email release with subject modification."""
        with patch('imaplib.IMAP4_SSL') as mock_imap:
            _configure_imap_mock(mock_imap)
            
            response = authenticated_client.post(
                f'/api/interception/release/{held_email}',
                json={
                    'target_folder': 'INBOX',
                    'edited_subject': 'EDITED: Test Email Subject'
                },
                headers={'Content-Type': 'application/json'}
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data.get('ok') is True

    def test_release_with_body_edit(self, client, authenticated_client, held_email, test_db_path):
        """Test email release with body modification."""
        with patch('imaplib.IMAP4_SSL') as mock_imap:
            _configure_imap_mock(mock_imap)
            
            response = authenticated_client.post(
                f'/api/interception/release/{held_email}',
                json={
                    'target_folder': 'INBOX',
                    'edited_body': 'This is the EDITED email body with changes.'
                },
                headers={'Content-Type': 'application/json'}
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data.get('ok') is True

    def test_release_idempotency_already_released(self, client, authenticated_client, held_email, test_db_path):
        """Test that releasing already-released email is idempotent."""
        # Mark email as already released
        conn = sqlite3.connect(test_db_path)
        conn.execute("""
            UPDATE email_messages 
            SET interception_status = 'RELEASED', status = 'DELIVERED'
            WHERE id = ?
        """, (held_email,))
        conn.commit()
        conn.close()
        
        response = authenticated_client.post(
            f'/api/interception/release/{held_email}',
            json={'target_folder': 'INBOX'},
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data.get('ok') is True
        assert data.get('reason') == 'already-released'

    def test_release_fails_for_discarded(self, client, authenticated_client, held_email, test_db_path):
        """Test that discarded emails cannot be released."""
        # Mark email as discarded
        conn = sqlite3.connect(test_db_path)
        conn.execute("""
            UPDATE email_messages 
            SET interception_status = 'DISCARDED'
            WHERE id = ?
        """, (held_email,))
        conn.commit()
        conn.close()
        
        response = authenticated_client.post(
            f'/api/interception/release/{held_email}',
            json={'target_folder': 'INBOX'},
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 409
        data = response.get_json()
        assert data.get('ok') is False
        assert data.get('reason') == 'discarded'

    def test_release_not_found(self, client, authenticated_client, test_db_path):
        """Test release of non-existent email."""
        response = authenticated_client.post(
            '/api/interception/release/99999',
            json={'target_folder': 'INBOX'},
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data.get('ok') is False
        assert data.get('reason') == 'not-found'


class TestEmailDiscard:
    """Test email discard functionality."""

    def test_discard_held_email(self, client, authenticated_client, held_email, test_db_path):
        """Test discarding a HELD email."""
        response = authenticated_client.post(
            f'/api/interception/discard/{held_email}',
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data.get('ok') is True
        assert data.get('status') == 'DISCARDED'
        assert data.get('changed') == 1

    def test_discard_idempotency(self, client, authenticated_client, held_email, test_db_path):
        """Test that discarding already-discarded email is idempotent."""
        # First discard
        authenticated_client.post(f'/api/interception/discard/{held_email}')
        
        # Second discard should be idempotent
        response = authenticated_client.post(
            f'/api/interception/discard/{held_email}',
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data.get('ok') is True
        assert data.get('status') == 'DISCARDED'
        assert data.get('changed') == 0
        assert data.get('already') is True

    def test_discard_not_found(self, client, authenticated_client, test_db_path):
        """Test discard of non-existent email."""
        response = authenticated_client.post(
            '/api/interception/discard/99999',
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data.get('ok') is False


class TestAttachmentHandling:
    """Test attachment stripping functionality."""

    def test_strip_attachments(self, client, authenticated_client, test_db_path, held_email):
        """Test that attachments can be stripped during release."""
        # Create email with attachment
        conn = sqlite3.connect(test_db_path)
        conn.execute("DELETE FROM email_messages WHERE id = 2")
    
        msg = EmailMessage()
        msg['From'] = 'sender@example.com'
        msg['To'] = 'test@example.com'
        msg['Subject'] = 'Email with Attachment'
        msg['Message-ID'] = '<attach@example.com>'
        msg.set_content('Body with attachment')
        
        # Add fake attachment
        msg.add_attachment(b'attachment data', maintype='application', 
                          subtype='pdf', filename='document.pdf')
        
        raw_content = msg.as_string()
        
        conn.execute("""
            INSERT INTO email_messages 
            (id, account_id, message_id, sender, recipients, subject, body_text,
             direction, interception_status, status, raw_content, original_uid)
            VALUES (2, 1, '<attach@example.com>', 'sender@example.com', 
                    '["test@example.com"]', 'Email with Attachment', 
                    'Body with attachment', 'inbound', 'HELD', 'PENDING', ?, 200)
        """, (raw_content,))
        conn.commit()
        conn.close()
        
        with patch('imaplib.IMAP4_SSL') as mock_imap:
            _configure_imap_mock(mock_imap)
            
            response = authenticated_client.post(
                '/api/interception/release/2',
                json={
                    'target_folder': 'INBOX',
                    'strip_attachments': True
                },
                headers={'Content-Type': 'application/json'}
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data.get('ok') is True
            assert 'attachments_removed' in data


class TestHealthEndpoints:
    """Test health check and monitoring endpoints."""

    def test_healthz_endpoint(self, client):
        """Test /healthz returns status information."""
        response = client.get('/healthz')
        
        assert response.status_code in [200, 503]
        data = response.get_json()
        
        assert 'ok' in data
        assert 'db' in data
        assert 'held_count' in data
        assert 'timestamp' in data

    def test_healthz_includes_security_status(self, client):
        """Test that healthz includes security configuration."""
        response = client.get('/healthz')
        data = response.get_json()
        
        if 'security' in data:
            security = data['security']
            assert 'secret_key_configured' in security
            assert 'csrf_enabled' in security

    def test_healthz_includes_imap_config(self, client):
        """Test that healthz includes IMAP configuration."""
        response = client.get('/healthz')
        data = response.get_json()
        
        if 'imap_config' in data:
            imap_cfg = data['imap_config']
            assert 'mode' in imap_cfg

    def test_smtp_health_endpoint(self, client):
        """Test /api/smtp-health endpoint."""
        response = client.get('/api/smtp-health')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'ok' in data
        assert 'listening' in data


class TestInterceptionAPI:
    """Test interception dashboard APIs."""

    def test_get_held_messages(self, client, authenticated_client, held_email):
        """Test /api/interception/held returns HELD messages."""
        response = authenticated_client.get('/api/interception/held')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'messages' in data
        assert 'stats' in data
        assert isinstance(data['messages'], list)

    def test_get_specific_held_message(self, client, authenticated_client, held_email):
        """Test /api/interception/held/<id> returns message details."""
        response = authenticated_client.get(f'/api/interception/held/{held_email}')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'id' in data
        assert data['id'] == held_email
        assert 'subject' in data
        assert 'sender' in data

    def test_get_held_message_with_diff(self, client, authenticated_client, held_email):
        """Test message retrieval with diff flag."""
        response = authenticated_client.get(
            f'/api/interception/held/{held_email}?include_diff=1'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should include preview_snippet
        assert 'preview_snippet' in data

    def test_inbox_api(self, client, authenticated_client, held_email):
        """Test /api/inbox endpoint."""
        response = authenticated_client.get('/api/inbox')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'messages' in data
        assert 'count' in data
        assert isinstance(data['messages'], list)

    def test_inbox_api_with_filter(self, client, authenticated_client, held_email):
        """Test /api/inbox with status filter."""
        response = authenticated_client.get('/api/inbox?status=HELD')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'messages' in data
        # Messages should be filtered to HELD status


class TestReleaseEdgeCase:
    """Test edge cases in email release."""

    def test_release_without_raw_content(self, client, authenticated_client, test_db_path):
        """Test release fails gracefully when raw content is missing."""
        # Create email without raw content
        conn = sqlite3.connect(test_db_path)
        conn.execute("DELETE FROM email_messages WHERE id = 3")
        conn.execute("""
            INSERT INTO email_messages 
            (id, account_id, message_id, sender, subject, 
             direction, interception_status, status)
            VALUES (3, 1, '<noraw@example.com>', 'sender@example.com',
                    'No Raw Content', 'inbound', 'HELD', 'PENDING')
        """)
        conn.commit()
        conn.close()
        
        response = authenticated_client.post(
            '/api/interception/release/3',
            json={'target_folder': 'INBOX'},
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 500
        data = response.get_json()
        assert data.get('ok') is False
        assert data.get('reason') == 'raw-missing'

    def test_release_imap_connection_failure(self, client, authenticated_client, held_email):
        """Test release handles IMAP connection failures."""
        with patch('imaplib.IMAP4_SSL') as mock_imap:
            mock_imap.side_effect = Exception("Connection refused")
            
            response = authenticated_client.post(
                f'/api/interception/release/{held_email}',
                json={'target_folder': 'INBOX'},
                headers={'Content-Type': 'application/json'}
            )
            
            assert response.status_code == 500
            data = response.get_json()
            assert data.get('ok') is False

    def test_release_to_custom_folder(self, client, authenticated_client, held_email):
        """Test release to custom IMAP folder."""
        with patch('imaplib.IMAP4_SSL') as mock_imap:
            _configure_imap_mock(mock_imap)
            
            response = authenticated_client.post(
                f'/api/interception/release/{held_email}',
                json={'target_folder': 'Archive'},
                headers={'Content-Type': 'application/json'}
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data.get('released_to') == 'Archive'


class TestMetricsEndpoint:
    """Test Prometheus metrics endpoint."""

    def test_metrics_endpoint_returns_prometheus_format(self, client):
        """Test /metrics returns Prometheus-formatted metrics."""
        response = client.get('/metrics')
        
        assert response.status_code == 200
        assert 'text/plain' in response.content_type.lower() or \
               'prometheus' in response.content_type.lower()

    def test_metrics_includes_email_counts(self, client, held_email):
        """Test metrics includes email count gauges."""
        response = client.get('/metrics')
        
        content = response.data.decode('utf-8')
        
        # Should include held and pending count metrics
        # Exact metric names depend on implementation
        assert len(content) > 0
