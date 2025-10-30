import os
import sqlite3

import pytest

from app.utils.rule_engine import evaluate_rules


def _create_extended_schema(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE moderation_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT,
            rule_type TEXT,
            condition_field TEXT,
            condition_operator TEXT,
            condition_value TEXT,
            action TEXT,
            priority INTEGER,
            is_active INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        INSERT INTO moderation_rules (rule_name, rule_type, condition_field, condition_operator, condition_value, action, priority, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """,
        ("Invoice keyword", "KEYWORD", "BODY", "CONTAINS", "invoice", "HOLD", 10),
    )
    conn.commit()
    conn.close()


def _create_legacy_schema(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE moderation_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT,
            keyword TEXT,
            action TEXT,
            priority INTEGER,
            is_active INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        INSERT INTO moderation_rules (rule_name, keyword, action, priority, is_active)
        VALUES (?, ?, ?, ?, 1)
        """,
        ("Legacy invoice", "invoice", "HOLD", 7),
    )
    conn.commit()
    conn.close()


@pytest.mark.parametrize("schema_builder, subject, sender", [
    (_create_extended_schema, "Important invoice", "test@example.com"),
    (_create_legacy_schema, "Legacy invoice", "raywecuya@gmail.com"),
])
def test_evaluate_rules_supports_multiple_schemas(tmp_path, schema_builder, subject, sender):
    db_path = tmp_path / "rules.db"
    schema_builder(str(db_path))

    result = evaluate_rules(subject=subject, body_text="Please review", sender=sender, recipients=["admin@example.com"], db_path=str(db_path))

    assert result["should_hold"] is True
    assert isinstance(result["risk_score"], int)
    assert result["risk_score"] >= 0
