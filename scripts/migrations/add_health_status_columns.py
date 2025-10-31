"""Add health status columns to email_accounts table

This migration adds the health monitoring columns that the API routes expect.
Required columns:
- smtp_health_status (TEXT) - 'connected', 'error', or 'unknown'
- imap_health_status (TEXT) - 'connected', 'error', or 'unknown'
- connection_status (TEXT) - 'connected', 'error', or 'unknown'
- last_health_check (TEXT) - ISO8601 timestamp
- last_successful_connection (TEXT) - ISO8601 timestamp
"""

import sqlite3
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

DB_PATH = os.environ.get('DB_PATH', 'email_manager.db')

def migrate():
    """Add health status columns to email_accounts table"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check existing columns
    cur.execute('PRAGMA table_info(email_accounts)')
    existing_columns = {row[1] for row in cur.fetchall()}

    columns_to_add = [
        ('smtp_health_status', 'TEXT'),
        ('imap_health_status', 'TEXT'),
        ('connection_status', 'TEXT'),
        ('last_health_check', 'TEXT'),
        ('last_successful_connection', 'TEXT'),
    ]

    added_count = 0
    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            print(f"Adding column: {col_name} {col_type}")
            cur.execute(f'ALTER TABLE email_accounts ADD COLUMN {col_name} {col_type}')
            added_count += 1
        else:
            print(f"Column {col_name} already exists, skipping")

    conn.commit()
    conn.close()

    print(f"\nMigration complete: {added_count} columns added")
    return added_count

if __name__ == '__main__':
    try:
        migrate()
        print("✓ Health status columns migration successful")
        sys.exit(0)
    except Exception as e:
        print(f"✗ Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
