"""
Prometheus metrics for Email Management Tool.

Provides instrumentation for:
- Email interception operations (SMTP + IMAP)
- Email release operations
- Error tracking
- System health metrics
- Latency measurements
"""
import re
import time
from contextlib import contextmanager
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram, Info


_MAX_LABEL_LENGTH = 48
_SAFE_LABEL_PATTERN = re.compile(r"[^a-zA-Z0-9_.:-]")


def _normalize_label(value: Optional[str], default: str = 'unknown', prefix: Optional[str] = None) -> str:
    """Normalize Prometheus label values to limit cardinality and ensure safe characters."""
    if value is None:
        return default

    text = str(value).strip()
    if not text:
        return default

    sanitized = _SAFE_LABEL_PATTERN.sub('_', text)
    if not sanitized:
        sanitized = default

    if len(sanitized) > _MAX_LABEL_LENGTH:
        sanitized = sanitized[:_MAX_LABEL_LENGTH]

    if prefix:
        sanitized = f"{prefix}:{sanitized}"

    return sanitized


def normalize_account_label(account_id: Optional[str]) -> str:
    """Public helper to normalize account labels consistently."""
    return _normalize_label(account_id, default='acct:unknown', prefix='acct')


def _normalize_host_label(host: Optional[str]) -> str:
    return _normalize_label(host, default='host:unknown', prefix='host')


# =============================================================================
# Email Operation Metrics
# =============================================================================

# Email interception counter (by direction and status)
emails_intercepted = Counter(
    'emails_intercepted_total',
    'Total number of emails intercepted',
    labelnames=['direction', 'status', 'account_id']
)

# Email release counter (by action)
emails_released = Counter(
    'emails_released_total',
    'Total number of emails released back to inbox',
    labelnames=['action', 'account_id']
)

# Email discard counter
emails_discarded = Counter(
    'emails_discarded_total',
    'Total number of emails discarded',
    labelnames=['reason', 'account_id']
)

# Email editing counter
emails_edited = Counter(
    'emails_edited_total',
    'Total number of emails edited before release',
    labelnames=['account_id']
)

# =============================================================================
# Error Tracking
# =============================================================================

# Error counter by type and component
errors_total = Counter(
    'errors_total',
    'Total number of errors by type and component',
    labelnames=['error_type', 'component']
)

# IMAP connection failures
imap_connection_failures = Counter(
    'imap_connection_failures_total',
    'Total number of IMAP connection failures',
    labelnames=['account_id', 'host']
)

# SMTP connection failures
smtp_connection_failures = Counter(
    'smtp_connection_failures_total',
    'Total number of SMTP connection failures',
    labelnames=['account_id', 'host']
)

# =============================================================================
# System Health & State
# =============================================================================

# Gauge for currently held emails
emails_held_current = Gauge(
    'emails_held_current',
    'Current number of emails in HELD status'
)

# Gauge for pending emails
emails_pending_current = Gauge(
    'emails_pending_current',
    'Current number of emails in PENDING status'
)

# IMAP watcher status (1 = running, 0 = stopped)
imap_watcher_status = Gauge(
    'imap_watcher_status',
    'Status of IMAP watcher threads (1 = running, 0 = stopped)',
    labelnames=['account_id']
)

# Database connection pool status
db_connections_active = Gauge(
    'db_connections_active',
    'Number of active database connections'
)

# =============================================================================
# Latency Metrics
# =============================================================================

# Email interception latency (time from SMTP receive to DB store)
interception_latency = Histogram(
    'email_interception_latency_seconds',
    'Email interception latency in seconds',
    labelnames=['direction'],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0)
)

# Email release latency
release_latency = Histogram(
    'email_release_latency_seconds',
    'Email release operation latency in seconds',
    labelnames=['action'],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# IMAP operation latency
imap_operation_latency = Histogram(
    'imap_operation_latency_seconds',
    'IMAP operation latency in seconds',
    labelnames=['operation', 'account_id'],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

# =============================================================================
# Application Info
# =============================================================================

# Application version and build info
app_info = Info(
    'email_manager_app',
    'Email Management Tool application information'
)

# Set initial app info (should be called at startup)
app_info.info({
    'version': '2.8',
    'component': 'email_manager',
    'environment': 'development'
})


# =============================================================================
# Helper Functions & Context Managers
# =============================================================================

@contextmanager
def track_latency(histogram: Histogram, **labels):
    """
    Context manager to track operation latency.

    Usage:
        with track_latency(interception_latency, direction='inbound'):
            # perform operation
            intercept_email()
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        histogram.labels(**labels).observe(duration)


def record_interception(direction: str = 'inbound',
                       status: str = 'HELD',
                       account_id: Optional[str] = None) -> None:
    """Record an email interception event."""
    account_label = normalize_account_label(account_id)
    emails_intercepted.labels(
        direction=direction,
        status=status,
        account_id=account_label
    ).inc()


def record_release(action: str = 'RELEASED',
                  account_id: Optional[str] = None) -> None:
    """Record an email release event."""
    account_label = normalize_account_label(account_id)
    emails_released.labels(
        action=action,
        account_id=account_label
    ).inc()


def record_discard(reason: str = 'USER_ACTION',
                  account_id: Optional[str] = None) -> None:
    """Record an email discard event."""
    account_label = normalize_account_label(account_id)
    emails_discarded.labels(
        reason=reason,
        account_id=account_label
    ).inc()


def record_edit(account_id: Optional[str] = None) -> None:
    """Record an email edit event."""
    account_label = normalize_account_label(account_id)
    emails_edited.labels(
        account_id=account_label
    ).inc()


def record_error(error_type: str, component: str) -> None:
    """Record an error event."""
    errors_total.labels(
        error_type=error_type,
        component=component
    ).inc()


def record_imap_failure(account_id: Optional[str] = None,
                       host: str = 'unknown') -> None:
    """Record an IMAP connection failure."""
    account_label = normalize_account_label(account_id)
    host_label = _normalize_host_label(host)
    imap_connection_failures.labels(
        account_id=account_label,
        host=host_label
    ).inc()


def record_smtp_failure(account_id: Optional[str] = None,
                       host: str = 'unknown') -> None:
    """Record an SMTP connection failure."""
    account_label = normalize_account_label(account_id)
    host_label = _normalize_host_label(host)
    smtp_connection_failures.labels(
        account_id=account_label,
        host=host_label
    ).inc()


def update_held_count(count: int) -> None:
    """Update the current held emails gauge."""
    emails_held_current.set(count)


def update_pending_count(count: int) -> None:
    """Update the current pending emails gauge."""
    emails_pending_current.set(count)


def set_watcher_status(account_id: str, status: bool) -> None:
    """Set IMAP watcher status (True = running, False = stopped)."""
    imap_watcher_status.labels(account_id=normalize_account_label(account_id)).set(1 if status else 0)


def update_db_connections(count: int) -> None:
    """Update the active database connections gauge."""
    db_connections_active.set(count)


__all__ = [
    # Metrics objects
    'emails_intercepted',
    'emails_released',
    'emails_discarded',
    'emails_edited',
    'errors_total',
    'imap_connection_failures',
    'smtp_connection_failures',
    'emails_held_current',
    'emails_pending_current',
    'imap_watcher_status',
    'db_connections_active',
    'interception_latency',
    'release_latency',
    'imap_operation_latency',
    'app_info',

    # Helper functions
    'normalize_account_label',
    'track_latency',
    'record_interception',
    'record_release',
    'record_discard',
    'record_edit',
    'record_error',
    'record_imap_failure',
    'record_smtp_failure',
    'update_held_count',
    'update_pending_count',
    'set_watcher_status',
    'update_db_connections',
]
