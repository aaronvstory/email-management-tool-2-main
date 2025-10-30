import json
import re
import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Union

from app.utils.db import DB_PATH


_HOLD_ACTIONS = {'HOLD', 'QUARANTINE', 'REJECT', 'BLOCK'}


def _normalize_recipients(recipients: Union[Sequence[str], str, None]) -> List[str]:
    if recipients is None:
        return []
    if isinstance(recipients, (list, tuple, set)):
        return [str(r) for r in recipients if r]
    if isinstance(recipients, str):
        try:
            data = json.loads(recipients)
            if isinstance(data, list):
                return [str(r) for r in data if r]
        except Exception:
            pass
        return [recipients]
    return [str(recipients)]


def _extract_sender_domain(sender: str) -> str:
    if not sender:
        return ''
    match = re.search(r'@([A-Za-z0-9.-]+)', sender)
    return match.group(1).lower() if match else ''


def evaluate_rules(
    subject: Optional[str] = None,
    body_text: Optional[str] = None,
    sender: Optional[str] = None,
    recipients: Union[Sequence[str], str, None] = None,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    subject_text = subject or ''
    body_text = body_text or ''
    sender_text = sender or ''
    recipients_list = _normalize_recipients(recipients)
    recipients_text = ' '.join(recipients_list)
    sender_domain = _extract_sender_domain(sender_text)

    content_body = f"{subject_text} {body_text}".lower()
    content_subject = subject_text.lower()
    content_sender = sender_text.lower()
    content_recipients = recipients_text.lower()

    matched_rules: List[Dict[str, Any]] = []
    matched_keywords: List[str] = []
    actions: List[str] = []
    risk_score = 0

    conn = None
    has_extended_schema = False
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        columns: List[str] = []
        try:
            column_rows = cur.execute("PRAGMA table_info(moderation_rules)").fetchall()
            columns = [row[1] if isinstance(row, tuple) else row["name"] for row in column_rows]
        except Exception:
            columns = []
        extended_cols = {"rule_type", "condition_field", "condition_operator", "condition_value"}
        has_extended_schema = extended_cols.issubset(set(columns))
        if has_extended_schema:
            cur.execute(
                """
                SELECT id, rule_name, rule_type, condition_field, condition_operator,
                       condition_value, action, priority
                FROM moderation_rules
                WHERE is_active = 1
                ORDER BY priority DESC
                """
            )
        else:
            cur.execute(
                """
                SELECT id, rule_name, keyword, action, priority
                FROM moderation_rules
                WHERE is_active = 1
                ORDER BY priority DESC
                """
            )
        rows = cur.fetchall()
    except Exception:
        rows = []
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    for row in rows:
        if has_extended_schema:
            rule_type = (row['rule_type'] or '').upper()
            condition_field = (row['condition_field'] or '').upper()
            condition_value = (row['condition_value'] or '').strip()
            operator = (row['condition_operator'] or 'CONTAINS').upper()
            action = (row['action'] or 'HOLD').upper()
            priority = int(row['priority'] or 0)
        else:
            rule_type = 'KEYWORD'
            condition_field = 'BODY'
            keyword_val = ''
            try:
                if 'keyword' in row.keys():  # type: ignore[attr-defined]
                    keyword_val = row['keyword'] or ''
            except Exception:
                keyword_val = row[2] if len(row) > 2 else ''  # defensive tuple fallback
            condition_value = keyword_val.strip()
            operator = 'CONTAINS'
            action = (row['action'] or 'HOLD').upper()
            priority = int(row['priority'] or 0)

        if not condition_value:
            continue

        # Backward compatibility for legacy rows
        if not condition_field:
            condition_field = 'BODY'
        if rule_type == 'SENDER' and condition_field == 'BODY':
            condition_field = 'SENDER'
        if rule_type == 'RECIPIENT' and condition_field == 'BODY':
            condition_field = 'RECIPIENT'

        if rule_type == 'REGEX' or operator == 'REGEX':
            patterns = [condition_value]
        else:
            patterns = [p.strip() for p in condition_value.split(',') if p.strip()]

        field_text = ''
        field_text_raw = ''
        if condition_field == 'SUBJECT':
            field_text = content_subject
            field_text_raw = subject_text
        elif condition_field == 'SENDER':
            field_text = content_sender
            field_text_raw = sender_text
        elif condition_field == 'RECIPIENT':
            field_text = content_recipients
            field_text_raw = recipients_text
        elif condition_field == 'SENDER_DOMAIN':
            field_text = sender_domain
            field_text_raw = sender_domain
        else:  # BODY, default fallback
            field_text = content_body
            field_text_raw = f"{subject_text} {body_text}".strip()

        matched_terms: List[str] = []
        for pattern in patterns:
            if not pattern:
                continue
            if rule_type == 'REGEX' or operator == 'REGEX':
                try:
                    if re.search(pattern, field_text_raw, flags=re.IGNORECASE):
                        matched_terms.append(pattern)
                except re.error:
                    continue
            elif operator == 'EQUALS':
                if field_text == pattern.lower():
                    matched_terms.append(pattern)
            elif operator == 'STARTS_WITH':
                if field_text.startswith(pattern.lower()):
                    matched_terms.append(pattern)
            elif operator == 'ENDS_WITH':
                if field_text.endswith(pattern.lower()):
                    matched_terms.append(pattern)
            else:  # CONTAINS or fallback
                if pattern.lower() in field_text:
                    matched_terms.append(pattern)

        if not matched_terms:
            continue

        matched_rules.append({
            'id': row['id'],
            'rule_name': row['rule_name'],
            'action': action,
            'priority': priority,
        })
        actions.append(action)
        matched_keywords.extend(matched_terms)
        risk_score += max(priority, 1)

    if not matched_keywords:
        default_keywords = {
            'urgent': 5,
            'confidential': 10,
            'payment': 8,
            'password': 10,
            'account': 5,
            'verify': 7,
            'suspended': 9,
            'click here': 8,
            'act now': 7,
            'limited time': 6,
        }
        for word, weight in default_keywords.items():
            if word in content_body:
                matched_keywords.append(word)
                risk_score += weight

    risk_score = min(risk_score, 100)
    should_hold = any(action in _HOLD_ACTIONS for action in actions) or bool(matched_rules)

    return {
        'matched_rules': matched_rules,
        'risk_score': risk_score,
        'keywords': matched_keywords,
        'actions': actions,
        'should_hold': should_hold,
    }


__all__ = ['evaluate_rules']
