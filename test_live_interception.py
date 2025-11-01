"""
Test live email interception by sending a test email with 'invoice' keyword.
This will verify that the rule engine is working correctly NOW.
"""
import sqlite3
from datetime import datetime
import time

# First, verify the invoice rule is active
conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 70)
print("LIVE INTERCEPTION TEST - Invoice Keyword")
print("=" * 70)

# Check current rules
rules = cur.execute("""
    SELECT id, rule_name, condition_field, condition_value, is_active, priority
    FROM moderation_rules
    WHERE is_active = 1
    ORDER BY priority DESC
""").fetchall()

print(f"\n📋 Active Rules ({len(rules)}):\n")
for r in rules:
    print(f"  Rule {r['id']}: {r['rule_name']}")
    print(f"    Field: {r['condition_field']}, Value: {r['condition_value']}")
    print(f"    Priority: {r['priority']}")

# Get current email count
before_count = cur.execute("SELECT COUNT(*) as count FROM email_messages").fetchone()['count']
print(f"\n📊 Current emails in DB: {before_count}")

# Get count of INTERCEPTED emails
intercepted_count = cur.execute("""
    SELECT COUNT(*) as count FROM email_messages
    WHERE interception_status = 'INTERCEPTED'
""").fetchone()['count']
print(f"📊 Currently INTERCEPTED: {intercepted_count}")

conn.close()

print("\n" + "=" * 70)
print("✅ PRE-FLIGHT CHECK COMPLETE")
print("=" * 70)

print(f"\n📧 To test interception:")
print(f"   1. Go to: http://127.0.0.1:5001/compose")
print(f"   2. Log in with: admin / admin123")
print(f"   3. Send email:")
print(f"      From: ndayijecika@gmail.com")
print(f"      To: mcintyre@corrinbox.com")
print(f"      Subject: TEST INVOICE #{int(time.time())}")
print(f"      Body: This is a test email to verify invoice interception.")
print(f"\n   4. Wait 30 seconds for IMAP watcher to fetch it")
print(f"   5. Then run: python verify_interception.py")

import os

# Create verification script safely
verify_script_name = 'verify_interception.py'
if os.path.exists(verify_script_name):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    verify_script_name = f'verify_interception_{timestamp}.py'
    print(f"⚠️ File 'verify_interception.py' exists. Creating '{verify_script_name}' instead.")

with open(verify_script_name, 'w') as f:
    f.write(f"""import sqlite3
conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

new_emails = cur.execute('''
    SELECT id, subject, interception_status, risk_score, keywords_matched, created_at
    FROM email_messages
    WHERE id > {before_count}
    ORDER BY id DESC
    LIMIT 5
''').fetchall()

print("\\n🔍 New Emails Since Test Started:\\n")
if not new_emails:
    print("   ❌ No new emails found. Wait longer or check IMAP watcher status.")
else:
    for email in new_emails:
        print(f"ID: {{email['id']}} - {{email['subject']}}")
        print(f"  Status: {{email['interception_status']}} {{'✅' if email['interception_status'] == 'INTERCEPTED' else '❌'}}")
        print(f"  Risk: {{email['risk_score']}}")
        print(f"  Keywords: {{email['keywords_matched']}}")
        print(f"  Created: {{email['created_at']}}")
        print()

conn.close()
""")

print(f"\n✅ Created {verify_script_name} - run it after sending the email")
