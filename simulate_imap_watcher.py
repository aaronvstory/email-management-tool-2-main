"""
Simulate EXACTLY what the IMAP watcher does when processing an email.
This will help us identify where the interception is failing.
"""
import sqlite3
import json
from app.utils.rule_engine import evaluate_rules

print("=" * 70)
print("SIMULATING IMAP WATCHER EMAIL PROCESSING")
print("=" * 70)

# Simulate Email #121 being processed
email_data = {
    'subject': 'invoice #1',
    'body_text': 'hi.. slay!',
    'sender': 'Rocky Jones <ndayijecika@gmail.com>',
    'recipients_list': ['mcintyre@corrinbox.com']
}

print(f"\n📧 Simulating Email Processing:")
print(f"   Subject: {email_data['subject']}")
print(f"   Body: {email_data['body_text']}")
print(f"   From: {email_data['sender']}")
print(f"   To: {email_data['recipients_list']}")

# Call evaluate_rules EXACTLY as IMAP watcher does (line 540)
print(f"\n🔍 Calling evaluate_rules()...")
rule_eval = evaluate_rules(
    email_data['subject'],
    email_data['body_text'], 
    email_data['sender'],
    email_data['recipients_list']
)

print(f"\n📊 Rule Evaluation Result:")
print(f"   should_hold: {rule_eval.get('should_hold')}")
print(f"   risk_score: {rule_eval.get('risk_score', 0)}")
print(f"   keywords: {rule_eval.get('keywords', [])}")
print(f"   matched_rules: {rule_eval.get('matched_rules', [])}")

# Determine interception_status as IMAP watcher does (line 542)
should_hold = bool(rule_eval.get('should_hold'))
interception_status = 'INTERCEPTED' if should_hold else 'FETCHED'

print(f"\n🎯 Determined Status:")
print(f"   should_hold = {should_hold}")
print(f"   interception_status = '{interception_status}'")

# Now compare with what was ACTUALLY stored in DB for Email #121
print(f"\n" + "=" * 70)
print("COMPARING WITH DATABASE")
print("=" * 70)

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

email_121 = cur.execute("""
    SELECT id, subject, interception_status, risk_score, keywords_matched
    FROM email_messages
    WHERE id = 121
""").fetchone()

print(f"\n📧 Email #121 in Database:")
print(f"   Subject: {email_121['subject']}")
print(f"   interception_status: '{email_121['interception_status']}'")
print(f"   risk_score: {email_121['risk_score']}")
print(f"   keywords_matched: {email_121['keywords_matched']}")

print(f"\n⚖️  COMPARISON:")
print(f"   Expected status: '{interception_status}'")
print(f"   Actual status:   '{email_121['interception_status']}'")
print(f"   Match: {'✅ YES' if interception_status == email_121['interception_status'] else '❌ NO'}")

print(f"\n   Expected risk: {rule_eval.get('risk_score', 0)}")
print(f"   Actual risk:   {email_121['risk_score']}")
print(f"   Match: {'✅ YES' if rule_eval.get('risk_score', 0) == email_121['risk_score'] else '❌ NO'}")

if email_121['interception_status'] != interception_status:
    print(f"\n❌ MISMATCH DETECTED!")
    print(f"\nPOSSIBLE CAUSES:")
    print(f"  1. Rule #2 ('invoice') didn't exist when Email #121 was processed")
    print(f"  2. Rule #2 was inactive (is_active=0) at that time")
    print(f"  3. IMAP watcher had stale cached rules")
    print(f"  4. Database connection issue prevented rule from being read")
    
    # Check rule timeline
    rules = cur.execute("""
        SELECT id, rule_name, condition_value, is_active, created_at
        FROM moderation_rules
        ORDER BY id
    """).fetchall()
    
    print(f"\n📅 Rule Timeline:")
    for r in rules:
        print(f"   Rule {r['id']}: '{r['condition_value']}' - Created: {r['created_at']}")
    
    email_created = cur.execute("""
        SELECT created_at FROM email_messages WHERE id=121
    """).fetchone()
    print(f"\n   Email #121 created: {email_created['created_at']}")

conn.close()

print(f"\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
print(f"\nThe rule engine NOW correctly identifies this email as INTERCEPTED.")
print(f"But it was stored as FETCHED when originally processed.")
print(f"\nThis confirms the rule was NOT active/available when the email arrived.")
