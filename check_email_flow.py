import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check recent emails in last 24 hours
cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
recent = cur.execute("""
    SELECT id, subject, sender, recipients, interception_status, 
           risk_score, created_at
    FROM email_messages 
    WHERE created_at > ?
    ORDER BY created_at DESC 
    LIMIT 10
""", (cutoff,)).fetchall()

print(f"📧 Recent emails (last 24h): {len(recent)}\n")
for email in recent:
    print(f"ID: {email['id']}")
    print(f"  Subject: {email['subject']}")
    print(f"  From: {email['sender']}")
    print(f"  To: {email['recipients']}")
    print(f"  Status: {email['interception_status']}")
    print(f"  Risk: {email['risk_score']}")
    print(f"  Created: {email['created_at']}")
    print()

# Check if any emails have been HELD/INTERCEPTED
held = cur.execute("""
    SELECT COUNT(*) as count
    FROM email_messages 
    WHERE interception_status IN ('HELD', 'INTERCEPTED')
""").fetchone()

print(f"📊 Total HELD/INTERCEPTED emails: {held['count']}")

# Check accounts
accounts = cur.execute("""
    SELECT id, email, imap_host, smtp_host, circuit_open
    FROM email_accounts
""").fetchall()

print(f"\n👤 Email accounts: {len(accounts)}\n")
for acc in accounts:
    print(f"ID: {acc['id']} | {acc['email']}")
    print(f"  IMAP: {acc['imap_host']}")
    print(f"  SMTP: {acc['smtp_host']}")
    print(f"  Circuit Open: {acc['circuit_open']}")
    print()

conn.close()
