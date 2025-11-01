import sqlite3
from datetime import datetime

conn = sqlite3.connect('email_manager.db')
cur = conn.cursor()

# Add invoice rule with extended schema
cur.execute("""
    INSERT INTO moderation_rules 
    (rule_name, rule_type, condition_field, condition_operator, condition_value, action, priority, is_active, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    'Invoice Detection',           # rule_name
    'KEYWORD',                     # rule_type
    'BODY',                        # condition_field (checks both subject + body)
    'CONTAINS',                    # condition_operator
    'invoice',                     # condition_value
    'HOLD',                        # action
    75,                            # priority (higher than existing rule)
    1,                             # is_active
    datetime.now().isoformat()     # created_at
))

conn.commit()
rule_id = cur.lastrowid

print(f"✅ Added 'Invoice Detection' rule (ID: {rule_id})")
print(f"   Field: BODY (checks subject + body combined)")
print(f"   Operator: CONTAINS")
print(f"   Value: invoice")
print(f"   Action: HOLD")
print(f"   Priority: 75")

# Verify
rows = cur.execute('SELECT * FROM moderation_rules WHERE id = ?', (rule_id,)).fetchall()
print(f"\n📋 Verification:")
for row in rows:
    print(f"   {row}")

conn.close()
