"""
Complete diagnostic - check EVERYTHING about the interception system
"""
import sqlite3
import requests
from datetime import datetime

print("=" * 80)
print("COMPLETE INTERCEPTION SYSTEM DIAGNOSTIC")
print(f"Time: {datetime.now()}")
print("=" * 80)

# 1. Check DB state
conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check active rules
rules = cur.execute("""
    SELECT id, rule_name, condition_field, condition_value, is_active, priority  
    FROM moderation_rules WHERE is_active=1 ORDER BY priority DESC
""").fetchall()

print(f"\n✅ ACTIVE RULES: {len(rules)}")
for r in rules:
    print(f"  #{r['id']}: {r['rule_name']} | {r['condition_field']}={r['condition_value']} | Priority={r['priority']}")

# Check latest email
latest = cur.execute("""
    SELECT id, subject, interception_status, risk_score, created_at
    FROM email_messages ORDER BY id DESC LIMIT 1
""").fetchone()

print(f"\n📧 LATEST EMAIL:")
if latest:
    print(f"  ID: {latest['id']}")
    print(f"  Subject: {latest['subject']}")
    print(f"  Status: {latest['interception_status']}")
    print(f"  Risk: {latest['risk_score']}")
    print(f"  Created: {latest['created_at']}")
else:
    print(f"  No emails in database!")

# Check accounts
accounts = cur.execute("""
    SELECT id, account_name, email_address, is_active, imap_health_status
    FROM email_accounts WHERE is_active=1
""").fetchall()

print(f"\n👤 ACTIVE ACCOUNTS: {len(accounts)}")
for acc in accounts:
    print(f"  #{acc['id']}: {acc['email_address']} | IMAP: {acc['imap_health_status']}")

conn.close()

# 2. Check if app is running
print(f"\n🌐 WEB APP STATUS:")
try:
    resp = requests.get('http://127.0.0.1:5001/health', timeout=5)
    print(f"  ✅ App is RUNNING (HTTP {resp.status_code})")
except:
    try:
        resp = requests.get('http://127.0.0.1:5001/', timeout=5)
        print(f"  ✅ App is RUNNING (HTTP {resp.status_code})")
    except:
        print(f"  ❌ App is NOT responding!")

# 3. Test rule engine directly
print(f"\n🧪 TESTING RULE ENGINE:")
from app.utils.rule_engine import evaluate_rules

test_result = evaluate_rules(
    subject="TEST INVOICE #999",
    body_text="This email contains the invoice keyword",
    sender="ndayijecika@gmail.com",
    recipients=["mcintyre@corrinbox.com"]
)

print(f"  Input: subject='TEST INVOICE #999', body='...invoice keyword...'")
print(f"  Result:")
print(f"    should_hold: {test_result['should_hold']} {'✅' if test_result['should_hold'] else '❌ FAIL!'}")
print(f"    risk_score: {test_result['risk_score']}")
print(f"    keywords: {test_result['keywords']}")
print(f"    matched_rules: {test_result['matched_rules']}")

# 4. Summary
print(f"\n" + "=" * 80)
print(f"DIAGNOSIS SUMMARY")
print(f"=" * 80)

if test_result['should_hold']:
    print(f"\n✅ Rule engine is WORKING - invoice detection active")
    print(f"\n⚠️  If emails still aren't being intercepted, the issue is:")
    print(f"   1. IMAP watcher not running/fetching emails")
    print(f"   2. IMAP watcher not calling evaluate_rules properly")
    print(f"   3. Emails going to wrong account")
    print(f"   4. Timing/delay issue")
else:
    print(f"\n❌ Rule engine is BROKEN - invoice rule not matching!")

print(f"\n📝 NEXT STEPS:")
print(f"   1. Send test email: ndayijecika@gmail.com → mcintyre@corrinbox.com")
print(f"   2. Subject: 'DIAGNOSTIC TEST INVOICE #999'")
print(f"   3. Wait 60 seconds")
print(f"   4. Run: python verify_latest_email.py")
