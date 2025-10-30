import sqlite3

# Connect to database
conn = sqlite3.connect('email_manager.db')
cur = conn.cursor()

# Check for missing tables
tables_to_check = ['email_release_locks', 'email_attachments', 'idempotency_keys']
for table in tables_to_check:
    exists = cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'").fetchone()
    print(f"Table {table}: {'EXISTS' if exists else 'MISSING'}")

print("\n=== Creating missing tables ===\n")

# Create email_release_locks table
cur.execute('''
    CREATE TABLE IF NOT EXISTS email_release_locks(
        email_id INTEGER PRIMARY KEY,
        acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
''')
print("✅ Created email_release_locks table")

# Create email_attachments table  
cur.execute('''
    CREATE TABLE IF NOT EXISTS email_attachments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email_id INTEGER NOT NULL,
        filename TEXT,
        content_type TEXT,
        size_bytes INTEGER,
        storage_path TEXT,
        is_original BOOLEAN DEFAULT 1,
        is_staged BOOLEAN DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(email_id) REFERENCES email_messages(id) ON DELETE CASCADE
    )
''')
print("✅ Created email_attachments table")

# Create idempotency_keys table
cur.execute('''
    CREATE TABLE IF NOT EXISTS idempotency_keys(
        key TEXT PRIMARY KEY,
        email_id INTEGER,
        status TEXT,
        response_json TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
''')
print("✅ Created idempotency_keys table")

# Check if email_messages has required columns
cur.execute("PRAGMA table_info(email_messages)")
columns = {row[1]: row[2] for row in cur.fetchall()}

if 'attachments_manifest' not in columns:
    cur.execute("ALTER TABLE email_messages ADD COLUMN attachments_manifest TEXT")
    print("✅ Added attachments_manifest column to email_messages")
else:
    print("ℹ️  attachments_manifest column already exists")

if 'version' not in columns:
    cur.execute("ALTER TABLE email_messages ADD COLUMN version INTEGER NOT NULL DEFAULT 0")
    print("✅ Added version column to email_messages")
else:
    print("ℹ️  version column already exists")

conn.commit()
conn.close()

print("\n=== Schema migration complete! ===")
