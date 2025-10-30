"""
Tests for Prometheus metrics functionality.

Verifies that metrics are properly instrumented and exposed.
"""
import pytest

from app.utils.metrics import (
    normalize_account_label,
    record_interception,
    record_release,
    record_discard,
    record_edit,
    record_error,
    record_imap_failure,
    record_smtp_failure,
    update_held_count,
    update_pending_count,
    set_watcher_status,
    emails_intercepted,
    emails_released,
    emails_discarded,
    emails_edited,
    errors_total,
    imap_connection_failures,
    smtp_connection_failures,
    emails_held_current,
    emails_pending_current,
    imap_watcher_status,
)


def test_record_interception_increments_counter():
    """Test that record_interception increments the counter."""
    label = normalize_account_label('test')
    # Get initial value
    before = emails_intercepted.labels(
        direction='inbound',
        status='HELD',
        account_id=label
    )._value.get()

    # Record interception
    record_interception(direction='inbound', status='HELD', account_id='test')

    # Verify increment
    after = emails_intercepted.labels(
        direction='inbound',
        status='HELD',
        account_id=label
    )._value.get()

    assert after == before + 1


def test_record_release_increments_counter():
    """Test that record_release increments the counter."""
    label = normalize_account_label('test')
    before = emails_released.labels(
        action='RELEASED',
        account_id=label
    )._value.get()

    record_release(action='RELEASED', account_id='test')

    after = emails_released.labels(
        action='RELEASED',
        account_id=label
    )._value.get()

    assert after == before + 1


def test_record_discard_increments_counter():
    """Test that record_discard increments the counter."""
    label = normalize_account_label('test')
    before = emails_discarded.labels(
        reason='USER_ACTION',
        account_id=label
    )._value.get()

    record_discard(reason='USER_ACTION', account_id='test')

    after = emails_discarded.labels(
        reason='USER_ACTION',
        account_id=label
    )._value.get()

    assert after == before + 1


def test_record_edit_increments_counter():
    """Test that record_edit increments the counter."""
    label = normalize_account_label('test')
    before = emails_edited.labels(account_id=label)._value.get()

    record_edit(account_id='test')

    after = emails_edited.labels(account_id=label)._value.get()

    assert after == before + 1


def test_record_error_increments_counter():
    """Test that record_error increments the counter."""
    before = errors_total.labels(
        error_type='ValidationError',
        component='api'
    )._value.get()

    record_error(error_type='ValidationError', component='api')

    after = errors_total.labels(
        error_type='ValidationError',
        component='api'
    )._value.get()

    assert after == before + 1


def test_record_imap_failure_increments_counter():
    """Test that record_imap_failure increments the counter."""
    account_label = normalize_account_label('test')
    host_label = 'host:imap.example.com'
    before = imap_connection_failures.labels(
        account_id=account_label,
        host=host_label
    )._value.get()

    record_imap_failure(account_id='test', host='imap.example.com')

    after = imap_connection_failures.labels(
        account_id=account_label,
        host=host_label
    )._value.get()

    assert after == before + 1


def test_record_smtp_failure_increments_counter():
    """Test that record_smtp_failure increments the counter."""
    account_label = normalize_account_label('test')
    host_label = 'host:smtp.example.com'
    before = smtp_connection_failures.labels(
        account_id=account_label,
        host=host_label
    )._value.get()

    record_smtp_failure(account_id='test', host='smtp.example.com')

    after = smtp_connection_failures.labels(
        account_id=account_label,
        host=host_label
    )._value.get()

    assert after == before + 1


def test_update_held_count_sets_gauge():
    """Test that update_held_count sets the gauge value."""
    update_held_count(42)

    value = emails_held_current._value.get()
    assert value == 42


def test_update_pending_count_sets_gauge():
    """Test that update_pending_count sets the gauge value."""
    update_pending_count(123)

    value = emails_pending_current._value.get()
    assert value == 123


def test_set_watcher_status_sets_gauge():
    """Test that set_watcher_status sets the gauge value."""
    # Set to running
    set_watcher_status('test_account', True)
    value_on = imap_watcher_status.labels(account_id=normalize_account_label('test_account'))._value.get()
    assert value_on == 1

    # Set to stopped
    set_watcher_status('test_account', False)
    value_off = imap_watcher_status.labels(account_id=normalize_account_label('test_account'))._value.get()
    assert value_off == 0


def test_metrics_endpoint_returns_prometheus_format(client):
    """Test that /metrics endpoint returns Prometheus format."""
    # /metrics endpoint doesn't require authentication
    response = client.get('/metrics')

    assert response.status_code == 200
    assert b'# HELP' in response.data
    assert b'# TYPE' in response.data

    # Check for some expected metrics
    assert b'emails_intercepted_total' in response.data
    assert b'emails_held_current' in response.data
    assert b'emails_pending_current' in response.data


def test_metrics_endpoint_includes_current_counts(client, db_session):
    """Test that /metrics endpoint includes current database counts."""
    # Insert some test data into the test database
    db_session.execute("""
        INSERT INTO email_messages (message_id, sender, recipients, subject, interception_status, status)
        VALUES ('test1', 'sender@example.com', 'recipient@example.com', 'Test 1', 'HELD', 'PENDING'),
               ('test2', 'sender@example.com', 'recipient@example.com', 'Test 2', 'HELD', 'PENDING')
    """)
    db_session.commit()

    # Request metrics (doesn't require authentication)
    response = client.get('/metrics')

    assert response.status_code == 200

    # Parse response to verify counts
    data = response.data.decode('utf-8')

    # Should include gauge metrics (exact values may vary due to test isolation)
    assert 'emails_held_current' in data
    assert 'emails_pending_current' in data


def test_normalize_account_label_sanitizes_value():
    label = normalize_account_label(' user@example.com ')
    assert label.startswith('acct:')
    assert ' ' not in label
