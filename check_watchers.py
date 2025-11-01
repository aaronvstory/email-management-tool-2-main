import sqlite3
import requests

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get all accounts
accounts = cur.execute("""
    SELECT id, account_name, email_address, imap_host, is_active, 
           imap_health_status, smtp_health_status, last_error
    FROM email_accounts
""").fetchall()

print(f"📊 Email Accounts Status:\n")
for acc in accounts:
    print(f"ID: {acc['id']} - {acc['account_name']}")
    print(f"  Email: {acc['email_address']}")
    print(f"  IMAP Host: {acc['imap_host']}")
    print(f"  Active: {acc['is_active']}")
    print(f"  IMAP Health: {acc['imap_health_status']}")
    print(f"  SMTP Health: {acc['smtp_health_status']}")
    if acc['last_error']:
        print(f"  Last Error: {acc['last_error'][:100]}")
    print()

conn.close()

# Check if watchers are running
print("\n🔍 Checking Active IMAP Watchers...\n")
try:
    resp = requests.get('http://127.0.0.1:5001/api/watchers', timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        watchers = data.get('watchers', [])
        print(f"Active Watchers: {len(watchers)}\n")
        for w in watchers:
            print(f"  Account {w.get('account_id')}: {w.get('status')}")
    else:
        print(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
