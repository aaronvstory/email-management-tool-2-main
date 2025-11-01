import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get emails from last 30 minutes (your recent tests)
cutoff = (datetime.now() - timedelta(minutes=30)).isoformat()

recent = cur.execute("""
    SELECT id, subject, sender, recipients, interception_status, 
           risk_score, keywords_matched, created_at
    FROM email_messages 
    WHERE created_at > ?
    ORDER BY id DESC
    LIMIT 20
""", (cutoff,)).fetchall()

print("=" * 80)
print(f"RECENT TEST EMAILS (Last 30 minutes - {len(recent)} emails)")
print("=" * 80)

invoice_emails = []
for email in recent:
    subject_lower = (email['subject'] or '').lower()
    has_invoice = 'invoice' in subject_lower
    
    if has_invoice:
        invoice_emails.append(email)
    
    print(f"\nID: {email['id']} | Created: {email['created_at']}")
    print(f"  Subject: {email['subject']}")
    print(f"  Status: {email['interception_status']} {'❌ WRONG!' if has_invoice and email['interception_status'] != 'INTERCEPTED' else '✅' if has_invoice else ''}")
    print(f"  Risk: {email['risk_score']} {'❌ Should be 75!' if has_invoice and email['risk_score'] == 0 else ''}")
    print(f"  Keywords: {email['keywords_matched']}")
    print(f"  From: {email['sender'][:50]}")

print("\n" + "=" * 80)
print(f"INVOICE KEYWORD ANALYSIS")
print("=" * 80)

if invoice_emails:
    print(f"\n📧 Found {len(invoice_emails)} emails with 'invoice' in subject:\n")
    
    intercepted_count = sum(1 for e in invoice_emails if e['interception_status'] == 'INTERCEPTED')
    fetched_count = sum(1 for e in invoice_emails if e['interception_status'] == 'FETCHED')
    
    print(f"  INTERCEPTED: {intercepted_count}")
    print(f"  FETCHED: {fetched_count} ❌ THESE SHOULD HAVE BEEN INTERCEPTED!")
    
    if fetched_count > 0:
        print(f"\n❌ FAILURE CONFIRMED!")
        print(f"\nThe following emails with 'invoice' were NOT intercepted:\n")
        for email in invoice_emails:
            if email['interception_status'] != 'INTERCEPTED':
                print(f"  ID {email['id']}: '{email['subject']}'")
                print(f"    Status: {email['interception_status']}")
                print(f"    Risk: {email['risk_score']}")
                print(f"    Keywords: {email['keywords_matched']}")
else:
    print(f"\n⚠️  No emails with 'invoice' found in recent tests.")
    print(f"   Please send a test email with 'invoice' in the subject.")

# Check if any emails were intercepted at all
any_intercepted = cur.execute("""
    SELECT COUNT(*) as count FROM email_messages 
    WHERE interception_status = 'INTERCEPTED' AND created_at > ?
""", (cutoff,)).fetchone()['count']

print(f"\n📊 Total INTERCEPTED in last 30 min: {any_intercepted}")

conn.close()
