"""Shared helpers for request rate limiting configuration and fallbacks."""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict
from functools import wraps
from typing import Dict, Tuple, Optional

from flask import jsonify, request


_RATE_LIMIT_CACHE: Dict[str, Dict[str, int | str]] = {}
_RATE_LIMIT_CACHE_LOCK = threading.Lock()

_LOCAL_BUCKET_LOCK = threading.Lock()
_LOCAL_BUCKETS: Dict[Tuple[str, str], Dict[str, float | int]] = defaultdict(lambda: {'count': 0, 'reset_time': 0.0})


def _parse_int(text: Optional[str], default: int) -> int:
    if not text:
        return default
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return default


def _extract_first_int_from_string(text: str, default: int) -> int:
    for token in text.replace('/', ' ').split():
        try:
            return int(token)
        except ValueError:
            continue
    return default


def _infer_window_from_string(text: str, fallback: int) -> int:
    lower = text.lower()
    if 'second' in lower:
        return 1
    if 'hour' in lower:
        return 3600
    if 'minute' in lower:
        return 60
    return fallback


def _format_limit_string(requests_per_window: int, window_seconds: int) -> str:
    if window_seconds <= 0:
        return f"{requests_per_window} per minute"
    if window_seconds == 1:
        return f"{requests_per_window} per second"
    if window_seconds == 60:
        return f"{requests_per_window} per minute"
    if window_seconds == 3600:
        return f"{requests_per_window} per hour"
    return f"{requests_per_window} per {window_seconds} seconds"


def get_rate_limit_config(name: str, default_requests: int = 30, default_window: int = 60) -> Dict[str, int | str]:
    """Resolve configured limit string, request count, and window from environment."""
    key = name.lower()
    with _RATE_LIMIT_CACHE_LOCK:
        if key in _RATE_LIMIT_CACHE:
            return _RATE_LIMIT_CACHE[key]

        prefix = f"RATE_LIMIT_{name.upper()}"
        limit_str_env = os.environ.get(prefix)
        requests_env = os.environ.get(f"{prefix}_REQUESTS")
        window_env = os.environ.get(f"{prefix}_WINDOW_SECONDS")

        requests_per_window = default_requests
        window_seconds = default_window
        limit_string = _format_limit_string(default_requests, default_window)

        if limit_str_env:
            limit_string = limit_str_env.strip()
            requests_per_window = _extract_first_int_from_string(limit_string, default_requests)
            window_seconds = _infer_window_from_string(limit_string, default_window)
        else:
            requests_per_window = _parse_int(requests_env, default_requests)
            window_seconds = max(1, _parse_int(window_env, default_window)) if window_env else default_window
            limit_string = _format_limit_string(requests_per_window, window_seconds)

        config = {
            'limit_string': limit_string,
            'max_requests': max(0, requests_per_window),
            'window': max(1, window_seconds),
        }
        _RATE_LIMIT_CACHE[key] = config
        return config


def get_limit_string(name: str, default_requests: int = 30, default_window: int = 60) -> str:
    return str(get_rate_limit_config(name, default_requests, default_window)['limit_string'])


def get_client_identifier(req) -> str:
    forwarded_for = req.headers.get('X-Forwarded-For')
    if forwarded_for:
        primary = forwarded_for.split(',')[0].strip()
        if primary:
            return primary
    real_ip = req.headers.get('X-Real-IP')
    if real_ip:
        real_ip = real_ip.strip()
        if real_ip:
            return real_ip
    return req.remote_addr or 'unknown'


def simple_rate_limit(name: str, config: Optional[Dict[str, int | str]] = None, *, default_requests: int = 30, default_window: int = 60):
    """Thread-safe rate limiting decorator for local fallback when Flask-Limiter is disabled."""

    def decorator(func):
        cfg = config or get_rate_limit_config(name, default_requests, default_window)
        max_requests = int(cfg['max_requests'])
        window_seconds = int(cfg['window'])

        if max_requests <= 0:
            return func

        @wraps(func)
        def wrapped(*args, **kwargs):
            client_id = get_client_identifier(request)
            bucket_key = (name.lower(), client_id)
            now = time.monotonic()

            with _LOCAL_BUCKET_LOCK:
                bucket = _LOCAL_BUCKETS[bucket_key]
                if now >= bucket['reset_time']:
                    bucket['count'] = 0
                    bucket['reset_time'] = now + window_seconds

                if bucket['count'] >= max_requests:
                    wait_seconds = max(0, int(bucket['reset_time'] - now))
                    response = jsonify({
                        'error': 'Rate limit exceeded',
                        'retry_after': wait_seconds,
                        'limit': max_requests,
                    })
                    response.status_code = 429
                    response.headers['Retry-After'] = str(wait_seconds)
                    response.headers['X-RateLimit-Limit'] = str(max_requests)
                    response.headers['X-RateLimit-Remaining'] = '0'
                    response.headers['X-RateLimit-Reset'] = str(wait_seconds)
                    return response

                bucket['count'] = int(bucket['count']) + 1

            return func(*args, **kwargs)

        return wrapped

    return decorator


__all__ = ['get_rate_limit_config', 'get_limit_string', 'get_client_identifier', 'simple_rate_limit']
