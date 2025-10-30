import sqlite3

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check if email 120 exists
row = cur.execute('SELECT * FROM email_messages WHERE id=120').fetchone()

if row is None:
    print("Email ID 120 does NOT exist in database")
else:
    print(f"Email ID 120 EXISTS")
    print(f"Subject: {row['subject']}")
    print(f"Status: {row['interception_status']}")
    print(f"Direction: {row['direction']}")
    print(f"Account ID: {row['account_id']}")
    print(f"Raw path: {row['raw_path']}")
    print(f"Raw content: {len(row['raw_content']) if row['raw_content'] else 0} bytes")
    
    # Check account
    if row['account_id']:
        acc = cur.execute('SELECT * FROM email_accounts WHERE id=?', (row['account_id'],)).fetchone()
        if acc:
            print(f"Account email: {acc['email']}")
            print(f"IMAP host: {acc['imap_host']}")
        else:
            print(f"ERROR: Account {row['account_id']} does NOT exist!")

conn.close()
