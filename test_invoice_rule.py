from app.utils.rule_engine import evaluate_rules

# Test 1: Invoice in subject
print("Test 1: Invoice in SUBJECT")
result = evaluate_rules(
    subject="Payment Invoice #12345",
    body_text="Please find the attached invoice for your review.",
    sender="ndayijecika@gmail.com",
    recipients=["mcintyre@corrinbox.com"]
)
print(f"  should_hold: {result['should_hold']}")
print(f"  risk_score: {result['risk_score']}")
print(f"  keywords: {result['keywords']}")
print(f"  matched_rules: {result['matched_rules']}")
print()

# Test 2: Invoice in body only
print("Test 2: Invoice in BODY only")
result = evaluate_rules(
    subject="Important Document",
    body_text="Here is your invoice for October 2025",
    sender="ndayijecika@gmail.com",
    recipients=["mcintyre@corrinbox.com"]
)
print(f"  should_hold: {result['should_hold']}")
print(f"  risk_score: {result['risk_score']}")
print(f"  keywords: {result['keywords']}")
print(f"  matched_rules: {result['matched_rules']}")
print()

# Test 3: No invoice keyword
print("Test 3: NO invoice keyword")
result = evaluate_rules(
    subject="Hello",
    body_text="Just a regular email",
    sender="ndayijecika@gmail.com",
    recipients=["mcintyre@corrinbox.com"]
)
print(f"  should_hold: {result['should_hold']}")
print(f"  risk_score: {result['risk_score']}")
print(f"  keywords: {result['keywords']}")
print(f"  matched_rules: {result['matched_rules']}")
print()

# Test 4: Case insensitive - INVOICE (uppercase)
print("Test 4: INVOICE (uppercase)")
result = evaluate_rules(
    subject="INVOICE DUE",
    body_text="Payment required",
    sender="ndayijecika@gmail.com",
    recipients=["mcintyre@corrinbox.com"]
)
print(f"  should_hold: {result['should_hold']}")
print(f"  risk_score: {result['risk_score']}")
print(f"  keywords: {result['keywords']}")
print(f"  matched_rules: {result['matched_rules']}")
