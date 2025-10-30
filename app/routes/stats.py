"""Statistics Blueprint - Phase 1B Route Modularization

Extracted from simple_app.py lines 1011, 2207, 2274, 2297
Routes: /api/stats, /api/unified-stats, /api/latency-stats, /stream/stats
"""
from flask import Blueprint, jsonify, Response, stream_with_context, current_app
from flask_login import login_required
import time
import json
from datetime import datetime, timezone
from app.utils.db import get_db, fetch_counts
from app.extensions import csrf
from app.services.stats import get_stats
import statistics

stats_bp = Blueprint('stats', __name__)

# TODO Phase 2: Unify stat sources (fetch_counts vs get_stats)

# Helper to access cache (Phase 5: replaced manual cache dicts with Flask-Caching)
def _get_cache():
    """Get cache instance from app context"""
    return current_app.cache


@stats_bp.route('/api/stats')
@login_required
def api_stats():
    """Get dashboard statistics"""
    data = get_stats()
    return jsonify(data)


@stats_bp.route('/api/unified-stats')
@login_required
def api_unified_stats():
    """Get unified statistics with released count, optionally filtered by account
    
    Phase 5 Quick Wins: Now uses Flask-Caching with automatic memoization by account_id
    """
    from flask import request
    account_id = request.args.get('account_id')
    
    # Use cache with memoization (automatically handles different account_id values)
    cache = _get_cache()
    cache_key = f'unified_stats_{account_id or "all"}'
    cached = cache.get(cache_key)
    if cached is not None:
        return jsonify(cached)
    
    # Get counts with optional account filtering
    if account_id:
        from app.utils.db import fetch_counts
        counts = fetch_counts(account_id=int(account_id), include_outbound=False)
    else:
        counts = get_stats()

    # Get released count with optional account filtering
    with get_db() as conn:
        cur = conn.cursor()
        if account_id:
            released = cur.execute("""
                SELECT COUNT(*) FROM email_messages
                WHERE (interception_status='RELEASED' OR status IN ('APPROVED','DELIVERED'))
                  AND (direction IS NULL OR direction!='outbound')
                  AND account_id = ?
            """, (account_id,)).fetchone()[0]
        else:
            released = cur.execute("""
                SELECT COUNT(*) FROM email_messages
                WHERE (interception_status='RELEASED' OR status IN ('APPROVED','DELIVERED'))
                  AND (direction IS NULL OR direction!='outbound')
            """).fetchone()[0]

    val = {
        'total': counts['total'],
        'pending': counts['pending'],
        'held': counts['held'],
        'released': released,
        'rejected': counts.get('rejected', 0),
        'discarded': counts.get('discarded', 0)
    }
    
    # Cache result (5 second TTL set in app config)
    cache.set(cache_key, val, timeout=5)
    return jsonify(val)


def _percentile(sorted_vals, pct: float) -> float:
    """Calculate percentile from sorted values"""
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])
    pos = (n - 1) * pct
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return float(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac)


@stats_bp.route('/api/latency-stats')
def api_latency_stats():
    """Get latency statistics with 10s cache
    
    Phase 5 Quick Wins: Now uses Flask-Caching instead of manual dict
    """
    cache = _get_cache()
    cache_key = 'latency_stats'
    cached = cache.get(cache_key)
    if cached is not None:
        return jsonify(cached)

    with get_db() as conn:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT latency_ms FROM email_messages
            WHERE latency_ms IS NOT NULL
            ORDER BY id DESC LIMIT 1000
            """
        ).fetchall()

    vals = [float(r[0]) for r in rows if r[0] is not None]
    vals.sort()
    count = len(vals)
    if count == 0:
        payload = {
            'count': 0,
            'min': 0, 'p50': 0, 'p90': 0, 'p95': 0, 'p99': 0, 'max': 0,
            'mean': 0, 'median': 0
        }
    else:
        payload = {
            'count': count,
            'min': float(vals[0]),
            'p50': _percentile(vals, 0.50),
            'p90': _percentile(vals, 0.90),
            'p95': _percentile(vals, 0.95),
            'p99': _percentile(vals, 0.99),
            'max': float(vals[-1]),
            'mean': float(statistics.fmean(vals) if hasattr(statistics, 'fmean') else sum(vals)/count),
            'median': float(statistics.median(vals)),
        }

    # Cache for 10 seconds (longer than default 5s due to expensive percentile calculations)
    cache.set(cache_key, payload, timeout=10)
    return jsonify(payload)


@stats_bp.route('/stream/stats')
@csrf.exempt
@login_required
def stream_stats():
    """Server-sent events stream for real-time statistics"""
    def generate():
        while True:
            counts = get_stats()
            data = json.dumps({
                'pending': counts.get('pending', 0),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            yield f"data: {data}\n\n"
            time.sleep(2)
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@stats_bp.route('/api/events')
@csrf.exempt
@login_required
def api_events():
    """Legacy SSE endpoint for real-time updates (migrated from monolith)."""
    def generate():
        while True:
            counts = get_stats()
            pending = counts.get('pending', 0)
            payload = json.dumps({'pending': pending, 'timestamp': datetime.now(timezone.utc).isoformat()})
            yield f"data: {payload}\n\n"
            time.sleep(5)
    return Response(stream_with_context(generate()), mimetype='text/event-stream')
