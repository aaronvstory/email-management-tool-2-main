import sqlite3
import json

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get email #121
email = cur.execute('SELECT * FROM email_messages WHERE id=121').fetchone()

print("📧 Email #121 Full Details:\n")
print(f"ID: {email['id']}")
print(f"Subject: {email['subject']}")
print(f"Sender: {email['sender']}")
print(f"Recipients: {email['recipients']}")
print(f"Interception Status: {email['interception_status']}")
print(f"Risk Score: {email['risk_score']}")
print(f"Keywords: {email['keywords_matched']}")
print(f"Direction: {email['direction']}")
print(f"Account ID: {email['account_id']}")
print(f"Created At: {email['created_at']}")

# Parse body to check for 'invoice'
body = email['body_text'] or ''
subject = email['subject'] or ''
print(f"\nBody preview (first 200 chars):")
print(f"  {body[:200]}")

# Check if 'invoice' is in subject or body
invoice_in_subject = 'invoice' in subject.lower()
invoice_in_body = 'invoice' in body.lower()

print(f"\n🔍 Invoice Detection:")
print(f"  In subject: {invoice_in_subject}")
print(f"  In body: {invoice_in_body}")

# Manually test evaluate_rules on this exact email
from app.utils.rule_engine import evaluate_rules

recipients_list = json.loads(email['recipients']) if email['recipients'] else []

result = evaluate_rules(
    subject=subject,
    body_text=body,
    sender=email['sender'],
    recipients=recipients_list
)

print(f"\n🧪 Manual Rule Evaluation Result:")
print(f"  should_hold: {result['should_hold']}")
print(f"  risk_score: {result['risk_score']}")
print(f"  keywords: {result['keywords']}")
print(f"  matched_rules: {result['matched_rules']}")

# Compare with DB values
print(f"\n⚖️  DB vs Rule Engine Comparison:")
print(f"  DB risk_score: {email['risk_score']} | Rule engine: {result['risk_score']}")
print(f"  DB keywords: {email['keywords_matched']} | Rule engine: {result['keywords']}")
print(f"  DB status: {email['interception_status']} | Expected: {'INTERCEPTED' if result['should_hold'] else 'FETCHED'}")

if email['interception_status'] != ('INTERCEPTED' if result['should_hold'] else 'FETCHED'):
    print(f"\n❌ MISMATCH! Email was stored with wrong status!")
    print(f"   This suggests the rule was NOT active when email was processed.")

conn.close()
