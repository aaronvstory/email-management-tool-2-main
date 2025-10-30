"""IMAP Watcher Startup Module

Handles initialization of IMAP monitoring threads for active email accounts.
Supports graceful startup with environment flag control.

Phase 1 Transitional Layout:
- Extracted from simple_app.py __main__ block
- ENABLE_WATCHERS environment variable controls startup
- Thread registry managed externally by caller
"""
import os
import threading
import sqlite3
from app.utils.db import DB_PATH
from app.utils.crypto import decrypt_credential


def start_imap_watchers(monitor_func, thread_registry, app_logger=None):
    """Start IMAP monitoring threads for all active accounts

    Args:
        monitor_func: The monitor_imap_account function to run in threads
        thread_registry: Dict to track running threads (account_id -> thread)
        app_logger: Optional logger for startup messages

    Returns:
        int: Number of watchers started

    Environment:
        ENABLE_WATCHERS: Set to '0' or 'false' to skip IMAP startup
    """
    # Check environment flag
    enable_watchers = os.environ.get('ENABLE_WATCHERS', '1').lower()
    if enable_watchers in ('0', 'false', 'no'):
        if app_logger:
            app_logger.info("IMAP watchers disabled via ENABLE_WATCHERS=0")
        print("⚠️  IMAP watchers disabled (ENABLE_WATCHERS=0)")
        return 0

    # Fetch active accounts
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    active_accounts = cursor.execute("""
        SELECT id, account_name, email_address, imap_username, imap_password
        FROM email_accounts WHERE is_active = 1
    """).fetchall()
    conn.close()

    # Start monitoring threads
    started_count = 0
    for account in active_accounts:
        account_id = account['id']
        # Skip accounts with missing credentials
        dec_pwd = decrypt_credential(account['imap_password']) if account['imap_password'] else None
        if not account['imap_username'] or not dec_pwd:
            if app_logger:
                app_logger.info(
                    "Skipping IMAP monitor for %s (ID: %s): credentials missing",
                    account['account_name'], account_id
                )
            print(f"   ⚠️  Skipping monitoring for {account['account_name']} (ID: {account_id}) - missing credentials")
            continue

        thread = threading.Thread(
            target=monitor_func,
            args=(account_id,),
            daemon=True
        )
        thread_registry[account_id] = thread
        thread.start()
        started_count += 1

        if app_logger:
            app_logger.info(f"Started IMAP monitor for {account['account_name']} (ID: {account_id})")
        print(f"   📬 Started monitoring for {account['account_name']} (ID: {account_id})")

    return started_count
