import sqlite3

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check schema first
columns = [row[1] for row in cur.execute("PRAGMA table_info(moderation_rules)").fetchall()]
print(f"Schema columns: {columns}\n")

# Get all rules
rows = cur.execute('SELECT * FROM moderation_rules ORDER BY priority DESC').fetchall()

print(f"Total rules: {len(rows)}\n")
for r in rows:
    print(f"ID: {r['id']}")
    print(f"  Rule Name: {r['rule_name']}")
    if 'keyword' in columns:
        print(f"  Keyword: {r['keyword']}")
    if 'condition_field' in columns:
        print(f"  Field: {r['condition_field']}")
    if 'condition_value' in columns:
        print(f"  Value: {r['condition_value']}")
    print(f"  Action: {r['action']}")
    print(f"  Active: {r['is_active']}")
    print(f"  Priority: {r['priority']}")
    print()

conn.close()
