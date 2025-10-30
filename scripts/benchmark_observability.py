"""Simple benchmarking script for logging and rate-limited endpoints.

Runs a handful of scenarios against the Flask test client to provide
latency percentiles both with default logging verbosity and with logging
muted. This offers a quick before/after comparison when tuning logging
overhead.
"""

from __future__ import annotations

import os
import statistics
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, List

from flask.testing import FlaskClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _percentiles(samples: List[float]) -> Dict[str, float]:
    ordered = sorted(samples)
    if not ordered:
        return {'p50': 0.0, 'p95': 0.0, 'p99': 0.0}

    def pct(p: float) -> float:
        k = max(0, min(len(ordered) - 1, int(round(p * (len(ordered) - 1)))))
        return ordered[k]

    return {
        'p50': pct(0.50),
        'p95': pct(0.95),
        'p99': pct(0.99),
    }


@contextmanager
def _log_level(level: str):
    old_level = os.environ.get('LOG_LEVEL')
    os.environ['LOG_LEVEL'] = level
    try:
        yield
    finally:
        if old_level is None:
            os.environ.pop('LOG_LEVEL', None)
        else:
            os.environ['LOG_LEVEL'] = old_level


def _measure(client: FlaskClient, label: str, func: Callable[[], None], iterations: int = 100) -> Dict[str, float]:
    durations: List[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        durations.append((time.perf_counter() - start) * 1000.0)  # ms

    stats = _percentiles(durations)
    stats['avg'] = statistics.fmean(durations)
    stats['min'] = min(durations)
    stats['max'] = max(durations)
    stats['label'] = label
    return stats


def run(client: FlaskClient, account_id: int, held_email_id: int) -> Dict[str, Dict[str, float]]:
    """Execute benchmark cases and return scenario → stats mapping."""

    scenarios = {}

    def call_edit():
        client.post(
            f'/api/email/{held_email_id}/edit',
            json={'subject': 'benchmark subject'},
        )

    def call_release():
        client.post(
            f'/api/interception/release/{held_email_id}',
            json={'target_folder': 'INBOX'},
        )

    def call_fetch():
        client.post('/api/fetch-emails', json={'account_id': account_id, 'count': 5})

    with _log_level('INFO'):
        scenarios['info_edit'] = _measure(client, 'edit:INFO', call_edit)
        scenarios['info_release'] = _measure(client, 'release:INFO', call_release)
        scenarios['info_fetch'] = _measure(client, 'fetch:INFO', call_fetch)

    with _log_level('WARNING'):
        scenarios['warn_edit'] = _measure(client, 'edit:WARN', call_edit)
        scenarios['warn_release'] = _measure(client, 'release:WARN', call_release)
        scenarios['warn_fetch'] = _measure(client, 'fetch:WARN', call_fetch)

    return scenarios


def main():
    from simple_app import app
    import sqlite3
    from app.utils.crypto import encrypt_credential

    with app.test_client() as client:
        conn = sqlite3.connect(os.environ.get('DB_PATH', 'email_manager.db'))
        conn.row_factory = sqlite3.Row

        conn.execute(
            """
            INSERT OR IGNORE INTO email_accounts (
                id, email_address, imap_host, imap_port, imap_username, imap_password,
                imap_use_ssl, smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_ssl, is_active
            )
            VALUES (1001, 'bench@example.com', 'imap.example.com', 993, 'bench@example.com', ?, 1,
                    'smtp.example.com', 587, 'bench@example.com', ?, 0, 1)
            """,
            (
                encrypt_credential('password123'),
                encrypt_credential('password123'),
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO email_messages (
                id, account_id, direction, interception_status, status, subject, body_text, raw_content
            )
            VALUES (2001, 1001, 'inbound', 'HELD', 'PENDING', 'Benchmail', 'Body', 'Raw email content')
            """
        )
        conn.commit()
        conn.close()

        client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)

        results = run(client, account_id=1001, held_email_id=2001)

        print("Latency results (ms):")
        for key, stats in results.items():
            print(f"- {key} → avg={stats['avg']:.2f}, p95={stats['p95']:.2f}, p99={stats['p99']:.2f}, min={stats['min']:.2f}, max={stats['max']:.2f}")


if __name__ == '__main__':
    main()
