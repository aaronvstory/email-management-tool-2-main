import sqlite3
conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Replace '2024-06-01 00:00:00' with your actual test start timestamp
test_start_time = '2024-06-01 00:00:00'

new_emails = cur.execute('''
    SELECT id, subject, interception_status, risk_score, keywords_matched, created_at
    FROM email_messages
    WHERE created_at > ?
    ORDER BY id DESC
    LIMIT 5
''', (test_start_time,)).fetchall()

print("\n🔍 New Emails Since Test Started:\n")
if not new_emails:
    print("   ❌ No new emails found. Wait longer or check IMAP watcher status.")
else:
    for email in new_emails:
        print(f"ID: {email['id']} - {email['subject']}")
        print(f"  Status: {email['interception_status']} {'✅' if email['interception_status'] == 'INTERCEPTED' else '❌'}")
        print(f"  Risk: {email['risk_score']}")
        print(f"  Keywords: {email['keywords_matched']}")
        print(f"  Created: {email['created_at']}")
        print()

conn.close()
