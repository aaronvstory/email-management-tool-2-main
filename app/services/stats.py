"""Statistics Service with In-Memory Caching

Provides unified statistics for dashboard with TTL-based caching.
Reduces database load by caching frequent stat queries.

Phase 1 Transitional Layout:
- Extracted from simple_app.py inline caching
- 2-second TTL for dashboard stats
- Global-only scope (account-specific deferred to Phase 2)

Cache Design:
- Simple dict-based with timestamps
- Thread-safe for read-heavy workloads
- No lock needed (stale reads acceptable for stats)
"""
import time
from app.utils.db import get_db, fetch_counts, table_exists


# In-memory cache: {'ts': float, 'stats': dict or None}
_STATS_CACHE = {'ts': 0, 'stats': None}
_CACHE_TTL = 2.0  # seconds


def get_stats(force_refresh=False):
    """Get unified dashboard statistics with caching

    Returns dict with keys:
    - total: Total message count
    - pending: Messages awaiting review
    - approved: Approved messages
    - rejected: Rejected messages
    - sent: Successfully sent messages
    - held: Messages held for interception

    Args:
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        dict: Statistics dictionary

    Cache TTL: 2 seconds (configurable via _CACHE_TTL)

    Example:
        >>> stats = get_stats()
        >>> print(f"Pending: {stats['pending']}, Held: {stats['held']}")
    """
    now = time.time()

    # Check cache validity
    if not force_refresh and (now - _STATS_CACHE['ts']) < _CACHE_TTL:
        cached = _STATS_CACHE['stats']
        if cached is not None:
            return cached

    # Cache miss or expired - fetch fresh data
    # Be resilient when tables are not yet initialized in test environment
    try:
        if not table_exists('email_messages'):
            stats = {k: 0 for k in ('total','pending','approved','rejected','sent','held','released')}
        else:
            stats = fetch_counts()  # Returns all 6 counts (total, pending, approved, rejected, sent, held)
    except Exception:
        stats = {k: 0 for k in ('total','pending','approved','rejected','sent','held','released')}

    # Update cache
    _STATS_CACHE['ts'] = now
    _STATS_CACHE['stats'] = stats

    return stats


def clear_cache():
    """Clear the statistics cache (useful for testing or immediate updates)

    Example:
        >>> clear_cache()  # Force next get_stats() to fetch fresh data
    """
    _STATS_CACHE['ts'] = 0
    _STATS_CACHE['stats'] = None


def get_cache_info():
    """Get cache metadata for monitoring/debugging

    Returns:
        dict: Cache info with keys 'age_seconds', 'is_valid', 'has_data'

    Example:
        >>> info = get_cache_info()
        >>> print(f"Cache age: {info['age_seconds']:.1f}s, Valid: {info['is_valid']}")
    """
    now = time.time()
    age = now - _STATS_CACHE['ts']
    return {
        'age_seconds': age,
        'is_valid': age < _CACHE_TTL,
        'has_data': _STATS_CACHE['stats'] is not None
    }
