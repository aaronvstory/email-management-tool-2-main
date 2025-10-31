"""Interception & Inbox Blueprint (Phase 2 Migration).

Contains: healthz, interception dashboard APIs, inbox API, edit, release, discard.
Diff and attachment scrubbing supported.
"""
import logging
import os
import time
import statistics
from datetime import datetime, timezone
import sqlite3
import re
import sys
import traceback
import hashlib
from pathlib import Path
import json

from typing import Dict, Any, Optional, Union, cast, Iterable
from flask import Blueprint, jsonify, render_template, request, current_app, send_file, abort
from flask_login import login_required, current_user
from email.parser import BytesParser
from email.policy import default as default_policy
from email.utils import make_msgid
import difflib
import imaplib, ssl

from app.utils.db import get_db, DB_PATH
from app.utils.crypto import decrypt_credential, encrypt_credential
from app.utils.imap_helpers import _imap_connect_account, _ensure_quarantine, _move_uid_to_quarantine
from app.utils.email_markers import RELEASE_BYPASS_HEADER, RELEASE_EMAIL_ID_HEADER
from app.services.imap_utils import normalize_folder
from app.services.audit import log_action
import socket
from app.extensions import csrf, limiter
from app.utils.rate_limit import get_rate_limit_config, simple_rate_limit

# Prometheus metrics
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from functools import wraps
import shutil
import threading
from contextlib import contextmanager


import mimetypes

try:
    import magic  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    magic = None

from typing import List
from typing import Set
import tempfile
import mmap
import html
from email.message import EmailMessage
from app.utils.metrics import record_release, track_latency, release_latency
_RELEASE_RATE_LIMIT = get_rate_limit_config('release', default_requests=30)
_EDIT_RATE_LIMIT = get_rate_limit_config('edit', default_requests=30)
_RELEASE_LIMIT_STRING = str(_RELEASE_RATE_LIMIT['limit_string'])
_EDIT_LIMIT_STRING = str(_EDIT_RATE_LIMIT['limit_string'])


bp_interception = Blueprint('interception_bp', __name__)
log = logging.getLogger(__name__)

def _db():
    """Get database connection with Row factory"""
    return get_db()

WORKER_HEARTBEATS = {}
_HEALTH_CACHE: Dict[str, Any] = {'ts': 0.0, 'payload': None}

_FILENAME_SANITIZER = re.compile(r'[^A-Za-z0-9._-]+')


def _get_storage_roots() -> tuple[Path, Path]:
    """Return absolute paths for attachments and staged roots."""
    app = current_app
    attachments_root = Path(app.config.get('ATTACHMENTS_ROOT_DIR', 'attachments')).resolve()
    staged_root = Path(app.config.get('ATTACHMENTS_STAGED_ROOT_DIR', 'attachments_staged')).resolve()
    attachments_root.mkdir(parents=True, exist_ok=True)
    staged_root.mkdir(parents=True, exist_ok=True)
    return attachments_root, staged_root


def _sanitize_filename(value: Optional[str]) -> str:
    if not value:
        return 'attachment'
    candidate = value.strip().replace('\\', '_').replace('/', '_')
    sanitized = _FILENAME_SANITIZER.sub('_', candidate)
    sanitized = sanitized.strip('._')
    return sanitized[:255] or 'attachment'


def _is_under(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _serialize_attachment_row(row: sqlite3.Row) -> Dict[str, Any]:
    """Safely serialize attachment row with defaults for missing fields."""
    try:
        return {
            'id': row.get('id') or 0,
            'email_id': row.get('email_id') or 0,
            'filename': row.get('filename') or 'unknown',
            'mime_type': row.get('mime_type') or 'application/octet-stream',
            'size': row.get('size') or 0,
            'sha256': row.get('sha256') or '',
            'disposition': row.get('disposition') or '',
            'content_id': row.get('content_id') or '',
            'is_original': bool(row.get('is_original', False)),
            'is_staged': bool(row.get('is_staged', False)),
        }
    except Exception as e:
        log.warning(f"Failed to serialize attachment row: {e}")
        return {
            'id': 0,
            'email_id': 0,
            'filename': 'error',
            'mime_type': 'application/octet-stream',
            'size': 0,
            'sha256': '',
            'disposition': '',
            'content_id': '',
            'is_original': False,
            'is_staged': False,
        }


def _attachments_feature_enabled(flag: str) -> bool:
    return bool(current_app.config.get(flag, False))


def _ensure_attachments_extracted(conn: sqlite3.Connection, row: sqlite3.Row) -> Iterable[sqlite3.Row]:
    """Ensure original attachments for the given email are extracted to disk and recorded."""
    email_id = row['id']
    cur = conn.cursor()
    existing = cur.execute(
        "SELECT * FROM email_attachments WHERE email_id=? AND is_original=1 ORDER BY id",
        (email_id,),
    ).fetchall()
    if existing:
        return existing

    raw_bytes = None
    raw_path = row['raw_path']
    raw_content = row['raw_content']
    if raw_path and os.path.exists(raw_path):
        try:
            raw_bytes = Path(raw_path).read_bytes()
        except (OSError, IOError) as exc:
            log.warning("[attachments] Failed reading raw_path", extra={'email_id': email_id, 'path': raw_path, 'error': str(exc)})
    if raw_bytes is None and raw_content:
        raw_bytes = raw_content if isinstance(raw_content, bytes) else raw_content.encode('utf-8', 'ignore')

    if not raw_bytes:
        return existing

    try:
        message = BytesParser(policy=default_policy).parsebytes(raw_bytes)
    except (ValueError, TypeError) as exc:
        log.warning("[attachments] Failed parsing raw email", extra={'email_id': email_id, 'error': str(exc)})
        return existing

    attachments_root, _ = _get_storage_roots()
    email_dir = attachments_root / str(email_id)
    try:
        email_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("[attachments] Failed to create storage directory", extra={'email_id': email_id, 'path': str(email_dir), 'error': str(exc)})
        return existing

    counter = 0
    for part in message.walk():
        if part.is_multipart():
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        disposition = (part.get_content_disposition() or '').lower() or None
        filename = part.get_filename()
        content_id = part.get('Content-ID')
        if not filename and disposition != 'attachment' and not content_id:
            # Skip inline body parts without filenames
            continue

        counter += 1
        base_name = _sanitize_filename(filename) if filename else f'attachment-{counter}'
        mime_type = part.get_content_type() or 'application/octet-stream'
        if '.' not in base_name:
            subtype = mime_type.split('/')[-1] if '/' in mime_type else None
            if subtype and subtype not in ('plain', 'html'):
                base_name = f'{base_name}.{subtype.lower()}'

        final_name = base_name
        suffix_count = 1
        while (email_dir / final_name).exists():
            path_obj = Path(base_name)
            final_name = f"{path_obj.stem}_{suffix_count}{path_obj.suffix}"
            suffix_count += 1

        destination = email_dir / final_name
        try:
            destination.write_bytes(payload)
        except (OSError, IOError) as exc:
            log.warning("[attachments] Failed writing attachment", extra={'email_id': email_id, 'file': final_name, 'error': str(exc)})
            continue

        sha256 = hashlib.sha256(payload).hexdigest()
        cur.execute(
            """
            INSERT OR IGNORE INTO email_attachments
                (email_id, filename, mime_type, size, sha256, disposition, content_id, is_original, is_staged, storage_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, ?)
            """,
            (
                email_id,
                final_name,
                mime_type,
                len(payload),
                sha256,
                disposition,
                (content_id or '').strip('<>') if content_id else None,
                str(destination),
            ),
        )

    conn.commit()
    return cur.execute(
        "SELECT * FROM email_attachments WHERE email_id=? AND is_original=1 ORDER BY id",
        (email_id,),
    ).fetchall()


def _ensure_manifest_structure(manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(manifest, dict):
        manifest = {}
    items = manifest.get('items')
    if not isinstance(items, list):
        manifest['items'] = []
    else:
        manifest['items'] = [item for item in items if isinstance(item, dict)]
    return manifest


def _load_manifest_from_row(row: Union[sqlite3.Row, Dict[str, Any]]) -> Dict[str, Any]:
    raw = None
    email_id = None
    if isinstance(row, sqlite3.Row):
        keys = row.keys()
        if 'attachments_manifest' in keys:
            raw = row['attachments_manifest']
        if 'id' in keys:
            email_id = row['id']
    elif isinstance(row, dict):
        raw = row.get('attachments_manifest')
        email_id = row.get('id')

    if not raw:
        return {'items': []}

    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', 'ignore')

    try:
        manifest = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning(
            '[attachments] Failed to decode manifest',
            extra={'email_id': email_id, 'error': str(exc)},
        )
        manifest = {}

    return _ensure_manifest_structure(manifest)


def _dump_manifest(manifest: Dict[str, Any]) -> str:
    snapshot = _ensure_manifest_structure(dict(manifest))
    snapshot['updated_at'] = datetime.now(timezone.utc).isoformat()
    return json.dumps(snapshot)


def _manifest_remove_entries(
    manifest: Dict[str, Any], *, aid: Optional[int] = None, staged_ref: Optional[int] = None
) -> Dict[str, Any]:
    manifest = _ensure_manifest_structure(manifest)
    if aid is None and staged_ref is None:
        return manifest

    filtered: List[Dict[str, Any]] = []
    for item in manifest['items']:
        matches_aid = aid is not None and item.get('aid') == aid
        matches_staged = staged_ref is not None and (
            item.get('staged_ref') == staged_ref or item.get('staged_id') == staged_ref
        )
        if matches_aid or matches_staged:
            continue
        filtered.append(item)

    manifest['items'] = filtered
    return manifest


def _manifest_append_entry(manifest: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
    manifest = _manifest_remove_entries(
        manifest,
        aid=entry.get('aid') if entry.get('aid') is not None else None,
        staged_ref=entry.get('staged_ref'),
    )
    manifest['items'].append(entry)
    return manifest


def _acquire_release_lock(conn: sqlite3.Connection, email_id: int) -> bool:
    try:
        conn.execute(
            "INSERT INTO email_release_locks(email_id, acquired_at) VALUES(?, datetime('now'))",
            (email_id,),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def _release_release_lock(conn: sqlite3.Connection, email_id: int) -> None:
    try:
        conn.execute(
            "DELETE FROM email_release_locks WHERE email_id=?",
            (email_id,),
        )
        conn.commit()
    except sqlite3.Error as e:
        log.warning(f"[release] Failed to release lock for email {email_id}: {e}")
        conn.rollback()


def _get_idempotency_record(conn: sqlite3.Connection, key: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM idempotency_keys WHERE key=?",
        (key,),
    ).fetchone()


def _set_idempotency_record(
    conn: sqlite3.Connection,
    key: str,
    email_id: int,
    status: str,
    response: Optional[Dict[str, Any]] = None,
) -> None:
    response_json = json.dumps(response) if response is not None else None
    conn.execute(
        "INSERT INTO idempotency_keys(key, email_id, status, response_json)\n         VALUES(?, ?, ?, ?)\n         ON CONFLICT(key) DO UPDATE SET status=excluded.status, response_json=excluded.response_json",
        (key, email_id, status, response_json),
    )
    conn.commit()


def _assemble_attachment_plan(
    attachments: Iterable[sqlite3.Row],
    manifest: Dict[str, Any],
) -> Dict[str, Any]:
    originals: List[sqlite3.Row] = []
    staged_map: Dict[int, sqlite3.Row] = {}
    for row in attachments:
        if row['is_original']:
            originals.append(row)
        elif row['is_staged']:
            staged_map[row['id']] = row

    items = manifest.get('items', []) if isinstance(manifest, dict) else []
    manifest_by_aid: Dict[int, List[Dict[str, Any]]] = {}
    additions: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        action = str(item.get('action', '')).lower()
        aid = item.get('aid')
        if action == 'add':
            additions.append(item)
        elif aid is not None:
            aid_int = int(aid)
            manifest_by_aid.setdefault(aid_int, []).append(item)

    originals.sort(key=lambda r: r['id'])
    final_entries: List[Dict[str, Any]] = []
    removed_entries: List[Dict[str, Any]] = []
    replaced_entries: List[Dict[str, Any]] = []

    for original in originals:
        actions = manifest_by_aid.get(original['id'], [])
        replace_entry = next((entry for entry in actions if str(entry.get('action', '')).lower() == 'replace'), None)
        remove_entry = next((entry for entry in actions if str(entry.get('action', '')).lower() == 'remove'), None)

        if replace_entry:
            staged_ref = replace_entry.get('staged_ref')
            staged_row = staged_ref is not None and staged_map.get(int(staged_ref))
            if staged_row:
                final_entries.append({
                    'row': staged_row,
                    'source': 'staged',
                    'manifest': replace_entry,
                    'replaces': original,
                })
                replaced_entries.append({
                    'original': original,
                    'staged': staged_row,
                    'manifest': replace_entry,
                })
                continue

        if remove_entry:
            removed_entries.append({'row': original, 'manifest': remove_entry})
            continue

        final_entries.append({'row': original, 'source': 'original'})

    added_entries: List[Dict[str, Any]] = []
    for item in additions:
        staged_ref = item.get('staged_ref')
        if staged_ref is None:
            continue
        staged_row = staged_map.get(int(staged_ref))
        if not staged_row:
            continue
        entry = {
            'row': staged_row,
            'source': 'staged',
            'manifest': item,
            'is_addition': True,
        }
        final_entries.append(entry)
        added_entries.append(entry)

    for entry in final_entries:
        row = entry['row']
        disposition = (row['disposition'] or '').lower() if row['disposition'] else ''
        entry['is_inline'] = bool(disposition == 'inline' or row['content_id'])

    return {
        'final': final_entries,
        'removed': removed_entries,
        'replaced': replaced_entries,
        'added': added_entries,
    }


def _build_release_message(
    row: sqlite3.Row,
    original_msg: EmailMessage,
    payload: Dict[str, Any],
    plan: Dict[str, Any],
    attachments_root: Path,
    staged_root: Path,
    strip_notice: bool = False,
) -> EmailMessage:
    subject = payload.get('edited_subject')
    if not subject:
        subject = row['subject'] if 'subject' in row.keys() else None
    if not subject:
        subject = original_msg.get('Subject', '')

    text_body = payload.get('edited_body')
    if text_body is None:
        text_body = row['body_text'] if 'body_text' in row.keys() else None
    if text_body is None:
        text_body = ''

    html_body = payload.get('edited_body_html')
    if html_body is None:
        html_body = row['body_html'] if 'body_html' in row.keys() else None
    if html_body is None and text_body:
        html_body = '<br>'.join(html.escape(text_body).splitlines())

    if strip_notice:
        text_body = (text_body or '') + '\n\n[Attachments removed]'
        if html_body:
            html_body = html_body + '<br><br><em>[Attachments removed]</em>'
        else:
            html_body = '<em>[Attachments removed]</em>'

    message = EmailMessage()
    message['Subject'] = subject

    for header, value in original_msg.items():
        header_lower = header.lower()
        if header_lower in {'subject', 'content-type', 'content-transfer-encoding', 'mime-version'}:
            continue
        if header_lower == 'message-id':
            continue
        message[header] = value

    message.make_mixed()

    body_container = EmailMessage()
    body_container.make_alternative()
    # Must use add_alternative for both text and HTML on a multipart/alternative container
    body_container.add_alternative(text_body or '', subtype='plain')
    if html_body:
        body_container.add_alternative(html_body, subtype='html')

    inline_entries = [entry for entry in plan['final'] if entry.get('is_inline')]
    regular_entries = [entry for entry in plan['final'] if not entry.get('is_inline')]

    if inline_entries and html_body:
        related_container = EmailMessage()
        related_container.make_related()
        related_container.attach(body_container)
        for entry in inline_entries:
            row_entry = entry['row']
            storage_path = Path(row_entry['storage_path']).resolve()
            if not storage_path.exists() or not storage_path.is_file():
                continue
            if not (_is_under(storage_path, attachments_root) or _is_under(storage_path, staged_root)):
                continue
            maintype, subtype = _split_mime_type(row_entry['mime_type'])
            with storage_path.open('rb') as fh:
                data = fh.read()
            related_container.add_attachment(
                data,
                maintype=maintype,
                subtype=subtype,
                filename=row_entry['filename'] or f'attachment-{row_entry["id"]}',
                disposition='inline',
                cid=f"{row_entry['content_id']}" if row_entry.get('content_id') else None,
            )
        message.attach(related_container)
    else:
        message.attach(body_container)

    for entry in regular_entries:
        row_entry = entry['row']
        storage_path = Path(row_entry['storage_path']).resolve()
        if not storage_path.exists() or not storage_path.is_file():
            continue
        if not (_is_under(storage_path, attachments_root) or _is_under(storage_path, staged_root)):
            continue
        maintype, subtype = _split_mime_type(row_entry['mime_type'])
        with storage_path.open('rb') as fh:
            data = fh.read()
        message.add_attachment(
            data,
            maintype=maintype,
            subtype=subtype,
            filename=row_entry['filename'] or f'attachment-{row_entry["id"]}',
        )

    needs_new_message_id = bool(
        payload.get('edited_subject')
        or payload.get('edited_body')
        or payload.get('edited_body_html')
        or plan['added']
        or plan['removed']
        or plan['replaced']
    )

    original_mid = (original_msg.get('Message-ID') or '').strip()
    if original_mid:
        message['X-EMT-Released-From'] = original_mid

    if needs_new_message_id or not original_mid:
        message['Message-ID'] = make_msgid()
    else:
        message['Message-ID'] = original_mid

    return message


def _split_mime_type(value: Optional[str]) -> tuple[str, str]:
    if value and '/' in value:
        maintype, subtype = value.split('/', 1)
        return maintype or 'application', subtype or 'octet-stream'
    if value:
        return value, 'octet-stream'
    return 'application', 'octet-stream'


def _allowed_mime_types() -> Set[str]:
    raw = current_app.config.get('ATTACHMENT_ALLOWED_MIME', '')
    if isinstance(raw, str):
        values = [token.strip().lower() for token in raw.split(',') if token.strip()]
        return set(values)
    if isinstance(raw, (list, tuple, set)):
        return {str(token).strip().lower() for token in raw if str(token).strip()}
    return {'application/pdf', 'image/png', 'image/jpeg', 'text/plain'}


def _detect_mime_type(file_bytes: bytes, filename: Optional[str] = None) -> str:
    detected: Optional[str] = None
    if magic:
        try:
            detected = magic.from_buffer(file_bytes, mime=True)
        except Exception as exc:  # pragma: no cover - debugging aid
            log.debug('[attachments] magic detection failed', extra={'error': str(exc)})
    if not detected and filename:
        detected = mimetypes.guess_type(filename)[0]
    return (detected or 'application/octet-stream').lower()


def _allocate_staged_path(base_dir: Path, filename: str) -> Path:
    sanitized = _sanitize_filename(filename)
    if not sanitized:
        sanitized = 'attachment'
    candidate = base_dir / sanitized
    if not candidate.exists():
        return candidate

    stem = Path(sanitized).stem or 'attachment'
    suffix = Path(sanitized).suffix
    counter = 1
    while True:
        candidate = base_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1

SMTP_HOST = os.environ.get('SMTP_PROXY_HOST', '127.0.0.1')
SMTP_PORT = int(os.environ.get('SMTP_PROXY_PORT', '8587'))


# =============================================================================
# Helper Functions for IMAP Operations and Gmail-specific Searches
# =============================================================================

def _server_supports_x_gm(imap_conn):
    """Check if server supports Gmail extensions (X-GM-EXT-1)."""
    try:
        typ, data = imap_conn.capability()
        caps = b' '.join(data).upper() if data else b''
        return b'X-GM-EXT-1' in caps
    except:
        return False

def _uid_store(imap_conn, uid, op, labels):
    """Wrapper for UID STORE operations with error handling."""
    try:
        return imap_conn.uid('STORE', str(uid), op, labels)
    except (imaplib.IMAP4.error, OSError) as e:
        log.warning(f"[_uid_store] UID STORE failed uid={uid} op={op}: {e}")
        return ('NO', [])

def _gm_search(imap_conn, raw_query):
    """Gmail X-GM-RAW search (must be called after select())."""
    try:
        typ, data = imap_conn.uid('SEARCH', None, 'X-GM-RAW', raw_query)
        if typ != 'OK' or not data or not data[0]:
            return []
        return [int(x) for x in data[0].split()]
    except (imaplib.IMAP4.error, ValueError) as e:
        log.warning(f"[_gm_search] Gmail search failed query={raw_query}: {e}")
        return []

def _gm_fetch_thrid(imap_conn, uid):
    """Fetch Gmail thread ID for a given UID (current mailbox)."""
    if not uid:
        return None
    try:
        typ, data = imap_conn.uid('FETCH', str(uid), '(X-GM-THRID)')
        if typ != 'OK' or not data or data[0] is None:
            return None
        # Parse: b'393 (X-GM-THRID 1760901299040 UID 393)'
        raw = data[0][1] if isinstance(data[0], tuple) else data[0]
        m = re.search(rb'X-GM-THRID\s+(\d+)', raw)
        return m.group(1).decode() if m else None
    except Exception as e:
        log.debug(f"[_gm_fetch_thrid] Failed uid={uid}: {e}")
        return None

def _find_uid_by_message_id(imap_conn, mailbox, msgid):
    """Find UID by Message-ID header (single result expected)."""
    try:
        imap_conn.select(mailbox)
        typ, data = imap_conn.uid('SEARCH', None, 'HEADER', 'Message-ID', f'"{msgid}"')
        if typ == 'OK' and data and data[0]:
            uids = [int(x) for x in data[0].split()]
            return uids[0] if uids else None
    except (imaplib.IMAP4.error, ValueError) as e:
        log.warning(f"[_find_uid_by_message_id] Message-ID search failed in {mailbox}: {e}")
        return None

def _robust_message_id_search(imap_conn, folder, message_id, is_gmail=False, tries=3, delay=0.4):
    """
    Searches for a message by Message-ID using multiple strategies with retry logic.
    Returns list of UIDs found, or empty list if not found.

    Tries in order (Gmail):
    1. HEADER X-Google-Original-Message-ID (Gmail rewrites invalid Message-IDs)
    2. X-GM-RAW combo search (rfc822msgid OR X-Google-Original-Message-ID)
    3. Gmail X-GM-RAW rfc822msgid search
    4. HEADER Message-ID variants (stripped/original/quoted)

    Tries in order (Non-Gmail):
    1. HEADER Message-ID with stripped angle brackets
    2. HEADER Message-ID with original format
    3. HEADER Message-ID with quoted format

    Retries up to 'tries' times with 'delay' seconds between attempts to handle Gmail indexing lag.
    """
    if not message_id:
        return []

    mid = message_id.strip()
    stripped = mid.strip('<>').strip().replace('"', '')  # Sanitize to prevent search syntax injection
    quoted = f'"{mid}"'

    def _one_try():
        """Single attempt through all search strategies."""
        strategies = []

        # Gmail-specific strategies (highest confidence first)
        if is_gmail:
            # Gmail rewrites invalid Message-IDs and stores original in X-Google-Original-Message-ID
            strategies.append(('HEADER-XGOOG', stripped, 'HEADER X-Google-Original-Message-ID'))
            # Combo search: catches both rewritten and non-rewritten cases
            strategies.append(('X-GM-RAW', f'(rfc822msgid:{stripped} OR header:x-google-original-message-id:{stripped})', 'X-GM-RAW combo'))
            # Original X-GM-RAW rfc822msgid (for non-rewritten Message-IDs)
            strategies.append(('X-GM-RAW', f'rfc822msgid:{stripped}', 'Gmail X-GM-RAW rfc822msgid'))

        # Generic HEADER searches (work on Hostinger and other IMAP servers)
        strategies.extend([
            ('HEADER', stripped, 'HEADER (stripped)'),
            ('HEADER', mid, 'HEADER (original)'),
            ('HEADER', quoted, 'HEADER (quoted)'),
        ])

        for kind, arg, label in strategies:
            try:
                if kind == 'X-GM-RAW':
                    typ, data = imap_conn.uid('SEARCH', None, 'X-GM-RAW', arg)
                elif kind == 'HEADER-XGOOG':
                    typ, data = imap_conn.uid('SEARCH', None, 'HEADER', 'X-Google-Original-Message-ID', arg)
                else:
                    typ, data = imap_conn.uid('SEARCH', None, kind, 'Message-ID', arg)

                log.info("[Search] Attempt", extra={"kind": kind, "label": label, "typ": typ, "raw": str(data)[:200], "folder": folder})

                if typ == 'OK' and data and data[0]:
                    uids = [u.decode() if isinstance(u, bytes) else u for u in data[0].split()]
                    if uids:
                        log.info("[Search] SUCCESS", extra={"label": label, "uids": uids, "folder": folder})
                        return uids
            except Exception as e:
                log.debug("[Search] Error", extra={"label": label, "err": str(e)})
        return []

    # Retry loop to handle Gmail indexing lag with exponential backoff
    for attempt in range(max(1, tries)):
        if attempt > 0:
            # Exponential backoff: 0.25s, 0.5s, 1s for better Gmail indexing lag handling
            backoff_delay = delay * (2 ** (attempt - 1))
            log.info(f"[Search] Retry attempt {attempt + 1}/{tries}", extra={"folder": folder, "message_id": mid[:50], "backoff": backoff_delay})
            time.sleep(backoff_delay)

        uids = _one_try()
        if uids:
            return uids

    log.warning("[Search] FAILED all strategies after retries", extra={"message_id": mid, "folder": folder, "tries": tries})
    return []


@bp_interception.route('/healthz')
@limiter.exempt
def healthz():
    """Health check endpoint with security configuration status (without exposing secrets)."""
    now = time.time()
    if _HEALTH_CACHE['payload'] and now - _HEALTH_CACHE['ts'] < 5:
        cached = dict(_HEALTH_CACHE['payload']); cached['cached'] = True
        return jsonify(cached), 200 if cached.get('ok') else 503
    info: Dict[str, Any] = {
        'ok': True,
        'db': None,
        'held_count': 0,
        'released_24h': 0,
        'median_latency_ms': None,
        'workers': [],
        'timestamp': datetime.now(timezone.utc).isoformat() + 'Z'
    }

    # Add security configuration status (without exposing secret values)
    try:
        from flask import current_app
        secret_key = current_app.config.get('SECRET_KEY', '')
        info['security'] = {
            'secret_key_configured': bool(secret_key and len(secret_key) >= 32),
            'secret_key_prefix': secret_key[:8] if secret_key else '',  # Only first 8 chars for verification
            'csrf_enabled': current_app.config.get('WTF_CSRF_ENABLED', False),
            'csrf_time_limit': current_app.config.get('WTF_CSRF_TIME_LIMIT'),
            'session_cookie_secure': current_app.config.get('SESSION_COOKIE_SECURE', False),
            'session_cookie_httponly': current_app.config.get('SESSION_COOKIE_HTTPONLY', True),
        }
    except Exception:
        info['security'] = {'status': 'unavailable'}

    # Add IMAP watcher configuration status
    try:
        import os
        idle_disabled = str(os.getenv('IMAP_DISABLE_IDLE', '0')).lower() in ('1', 'true', 'yes')
        poll_interval = int(os.getenv('IMAP_POLL_INTERVAL', '30'))
        info['imap_config'] = {
            'mode': 'polling' if idle_disabled else 'idle+polling',
            'idle_disabled': idle_disabled,
            'poll_interval_seconds': poll_interval,
            'verbose_logging': str(os.getenv('IMAP_LOG_VERBOSE', '0')).lower() in ('1', 'true', 'yes'),
            'circuit_threshold': int(os.getenv('IMAP_CIRCUIT_THRESHOLD', '5'))
        }
    except Exception:
        info['imap_config'] = {'status': 'unavailable'}

    try:
        conn = _db(); cur = conn.cursor()
        info['held_count'] = cur.execute("SELECT COUNT(*) FROM email_messages WHERE direction='inbound' AND interception_status='HELD'").fetchone()[0]
        info['released_24h'] = cur.execute("SELECT COUNT(*) FROM email_messages WHERE direction='inbound' AND interception_status='RELEASED' AND created_at >= datetime('now','-1 day')").fetchone()[0]
        lat_rows = cur.execute("SELECT latency_ms FROM email_messages WHERE latency_ms IS NOT NULL ORDER BY id DESC LIMIT 200").fetchall()
        latencies = [r['latency_ms'] for r in lat_rows if r['latency_ms'] is not None]
        if latencies:
            info['median_latency_ms'] = int(statistics.median(latencies))
        # Worker heartbeats from DB (last 2 minutes)
        try:
            rows = cur.execute(
                """
                SELECT worker_id, last_heartbeat, status
                FROM worker_heartbeats
                WHERE datetime(last_heartbeat) > datetime('now', '-2 minutes')
                ORDER BY last_heartbeat DESC
                """
            ).fetchall()
            info['workers'] = [dict(r) for r in rows]
        except Exception:
            info['workers'] = []
        conn.close(); info['db'] = 'ok'
    except Exception as e:
        info['ok'] = False; info['error'] = str(e)
    # SMTP status
    smtp_info = {'listening': False, 'last_selfcheck_ts': None, 'last_inbound_ts': None}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        err = s.connect_ex((SMTP_HOST, SMTP_PORT))
        s.close()
        smtp_info['listening'] = (err == 0)
    except Exception:
        smtp_info['listening'] = False
    try:
        conn2 = _db(); cur2 = conn2.cursor()
        try:
            row = cur2.execute("SELECT value FROM system_status WHERE key='smtp_last_selfcheck' LIMIT 1").fetchone()
            if row and row['value']:
                smtp_info['last_selfcheck_ts'] = row['value']
        except Exception:
            pass
        try:
            r2 = cur2.execute("SELECT MAX(created_at) AS ts FROM email_messages WHERE direction='inbound'").fetchone()
            smtp_info['last_inbound_ts'] = r2['ts'] if r2 and r2['ts'] else None
        except Exception:
            pass
        conn2.close()
    except Exception:
        pass
    info['smtp'] = smtp_info
    _HEALTH_CACHE['ts'] = now; _HEALTH_CACHE['payload'] = info
    log.debug("[interception::healthz] refreshed", extra={'ok': info.get('ok'), 'held_count': info.get('held_count'), 'workers': len(info.get('workers', []))})
    return jsonify(info), 200 if info.get('ok') else 503

@bp_interception.route('/api/smtp-health')
@limiter.exempt
def api_smtp_health():
    """Lightweight SMTP health endpoint."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        ok = (s.connect_ex((SMTP_HOST, SMTP_PORT)) == 0)
        s.close()
    except Exception:
        ok = False
    last_sc = None; last_in = None
    try:
        conn = _db(); cur = conn.cursor()
        try:
            row = cur.execute("SELECT value FROM system_status WHERE key='smtp_last_selfcheck' LIMIT 1").fetchone()
            if row and row['value']:
                last_sc = row['value']
        except Exception:
            pass
        try:
            r2 = cur.execute("SELECT MAX(created_at) AS ts FROM email_messages WHERE direction='inbound'").fetchone()
            last_in = r2['ts'] if r2 and r2['ts'] else None
        except Exception:
            pass
        conn.close()
    except Exception:
        pass
    return jsonify({'ok': ok, 'listening': ok, 'last_selfcheck_ts': last_sc, 'last_inbound_ts': last_in})

@bp_interception.route('/metrics')
@limiter.exempt
def metrics():
    """
    Prometheus metrics endpoint.

    Exposes all instrumented metrics in Prometheus format.
    Update gauge metrics with current system state before returning.
    """
    try:
        # Update gauge metrics with current system state
        from app.utils.metrics import update_held_count, update_pending_count
        conn = _db()
        cur = conn.cursor()

        # Update held count
        held_count = cur.execute(
            "SELECT COUNT(*) FROM email_messages WHERE interception_status='HELD'"
        ).fetchone()[0]
        update_held_count(held_count)

        # Update pending count
        pending_count = cur.execute(
            "SELECT COUNT(*) FROM email_messages WHERE status='PENDING'"
        ).fetchone()[0]
        update_pending_count(pending_count)

        conn.close()
    except Exception as e:
        log.warning(f"Failed to update gauge metrics: {e}")

    # Generate and return Prometheus metrics
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@bp_interception.route('/interception')
@login_required
def interception_dashboard():
    """Redirect to unified email management with HELD filter"""
    from flask import redirect
    return redirect('/emails-unified?status=HELD')

@bp_interception.route('/interception-legacy')
@login_required
def interception_dashboard_legacy():
    """Legacy interception dashboard - kept for reference"""
    return render_template('dashboard_interception.html')

@bp_interception.route('/api/interception/held')
@login_required
def api_interception_held():
    conn = _db(); cur = conn.cursor()
    rows = cur.execute("""
        SELECT id, account_id, interception_status, original_uid, sender, recipients, subject, latency_ms, created_at
        FROM email_messages
        WHERE direction='inbound' AND interception_status='HELD'
          AND sender != 'selfcheck@localhost'
        ORDER BY id DESC LIMIT 200
    """).fetchall()
    latencies = [r['latency_ms'] for r in rows if r['latency_ms'] is not None]
    median_latency = int(statistics.median(latencies)) if latencies else None
    released24 = cur.execute("""
        SELECT COUNT(*) FROM email_messages
        WHERE direction='inbound' AND interception_status='RELEASED' AND created_at >= datetime('now','-1 day')
    """).fetchone()[0]
    accounts_active = cur.execute("SELECT COUNT(DISTINCT account_id) FROM email_messages WHERE direction='inbound'").fetchone()[0]
    conn.close()
    # Fix timezone: SQLite datetime('now') returns UTC without 'Z', JavaScript needs 'Z' suffix
    messages = []
    for r in rows:
        msg = dict(r)
        if msg.get('created_at') and isinstance(msg['created_at'], str):
            if not msg['created_at'].endswith('Z') and 'T' not in msg['created_at']:
                msg['created_at'] = msg['created_at'].replace(' ', 'T') + 'Z'
        messages.append(msg)
    return jsonify({'messages':messages, 'stats':{'held':len(rows),'released24h':released24,'median_latency_ms':median_latency,'accounts_active':accounts_active}})

@bp_interception.route('/api/interception/held/<int:msg_id>')
@login_required
def api_interception_get(msg_id:int):
    include_diff = request.args.get('include_diff') == '1'
    conn = _db(); cur = conn.cursor()
    row = cur.execute("SELECT * FROM email_messages WHERE id=? AND direction='inbound'", (msg_id,)).fetchone()
    if not row:
        conn.close(); return jsonify({'error':'not found'}), 404
    data = dict(row)
    raw_path = data.get('raw_path'); snippet = None
    if raw_path and os.path.exists(raw_path):
        try:
            with open(raw_path,'rb') as f: emsg = BytesParser(policy=default_policy).parsebytes(f.read())
            text_part = None
            if emsg.is_multipart():
                for part in emsg.walk():
                    if part.get_content_type()=='text/plain':
                        text_part = part.get_content(); break
                if text_part is None:
                    for part in emsg.walk():
                        if part.get_content_type()=='text/html':
                            import re; text_part = re.sub('<[^>]+>',' ', part.get_content()); break
            else:
                if emsg.get_content_type()=='text/plain': text_part = emsg.get_content()
                elif emsg.get_content_type()=='text/html':
                    import re; text_part = re.sub('<[^>]+>',' ', emsg.get_content())
            if text_part:
                snippet = ' '.join(text_part.split())[:500]
        except Exception:
            snippet = None
    data['preview_snippet'] = snippet
    if include_diff and snippet is not None:
        try:
            current_body = (row['body_text'] or '').strip()
            if current_body and current_body != snippet:
                diff_lines = list(difflib.unified_diff(snippet.splitlines(), current_body.splitlines(), fromfile='original', tofile='edited', lineterm=''))
                data['body_diff'] = diff_lines[:500]
        except Exception:
            data['body_diff'] = None
    conn.close(); return jsonify(data)

@bp_interception.route('/api/email/<int:email_id>/attachments', methods=['GET'])
@login_required
def api_email_attachments(email_id: int):
    if not _attachments_feature_enabled('ATTACHMENTS_UI_ENABLED'):
        return jsonify({'ok': False, 'error': 'disabled'}), 403

    conn = _db()
    try:
        row = conn.execute(
            "SELECT * FROM email_messages WHERE id=?",
            (email_id,),
        ).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'not-found'}), 404

        original_rows = list(_ensure_attachments_extracted(conn, row))
        manifest = _load_manifest_from_row(row)
        version = row['version'] if 'version' in row.keys() and row['version'] is not None else 0

        etag = f'W/"attachments-{email_id}-{version}"'
        if_none_match = request.headers.get('If-None-Match')
        if if_none_match and if_none_match.strip() == etag:
            response = current_app.response_class(status=304)
            response.headers['ETag'] = etag
            return response

        payload = {
            'ok': True,
            'email_id': email_id,
            'version': version,
            'attachments': [_serialize_attachment_row(r) for r in original_rows],
            'manifest': manifest,
        }
        response = jsonify(payload)
        response.headers['ETag'] = etag
        return response
    finally:
        conn.close()


@bp_interception.route('/api/attachment/<int:attachment_id>/download', methods=['GET'])
@login_required
def api_attachment_download(attachment_id: int):
    conn = _db()
    try:
        row = conn.execute("SELECT * FROM email_attachments WHERE id=?", (attachment_id,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'not-found'}), 404

        attachments_root, staged_root = _get_storage_roots()
        storage_path = Path(row['storage_path']).resolve()

        if not storage_path.exists() or not storage_path.is_file():
            log.warning("[attachments] File missing for download", extra={'attachment_id': attachment_id, 'path': str(storage_path)})
            return jsonify({'ok': False, 'error': 'not-found'}), 404

        if not (_is_under(storage_path, attachments_root) or _is_under(storage_path, staged_root)):
            log.warning("[attachments] Download path outside storage roots", extra={'attachment_id': attachment_id, 'path': str(storage_path)})
            abort(404)

        download_name = row['filename'] or f'attachment-{attachment_id}'
        mimetype = row['mime_type'] or 'application/octet-stream'
        return send_file(storage_path, mimetype=mimetype, as_attachment=True, download_name=download_name)
    finally:
        conn.close()


@bp_interception.route('/api/email/<int:email_id>/attachments/upload', methods=['POST'])
@login_required
def api_email_attachments_upload(email_id: int):
    if not _attachments_feature_enabled('ATTACHMENTS_EDIT_ENABLED'):
        return jsonify({'ok': False, 'error': 'disabled'}), 403

    upload_file = request.files.get('file')
    if not upload_file or upload_file.filename == '':
        return jsonify({'ok': False, 'error': 'missing-file'}), 400

    replace_raw = request.form.get('replace_aid')
    version_raw = request.form.get('version')

    replace_aid: Optional[int] = None
    if replace_raw:
        try:
            replace_aid = int(replace_raw)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'invalid-replace-id'}), 422

    expected_version: Optional[int] = None
    if version_raw not in (None, ''):
        try:
            expected_version = int(version_raw)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'invalid-version'}), 422

    file_bytes = upload_file.read()
    if not file_bytes:
        return jsonify({'ok': False, 'error': 'empty-file'}), 400

    max_bytes = int(current_app.config.get('ATTACHMENT_MAX_BYTES', 25 * 1024 * 1024))
    if len(file_bytes) > max_bytes:
        return jsonify({'ok': False, 'error': 'size-exceeded', 'limit': max_bytes}), 413

    mime_type = _detect_mime_type(file_bytes, upload_file.filename)
    allowed_mime = _allowed_mime_types()
    if allowed_mime and mime_type not in allowed_mime:
        return jsonify({'ok': False, 'error': 'mime-disallowed', 'mime': mime_type}), 415

    conn = _db()
    written_path: Optional[Path] = None
    try:
        conn.execute('BEGIN')
        row = conn.execute(
            "SELECT id, attachments_manifest, version FROM email_messages WHERE id=?",
            (email_id,),
        ).fetchone()
        if not row:
            conn.rollback()
            return jsonify({'ok': False, 'error': 'not-found'}), 404

        manifest = _load_manifest_from_row(row)
        base_version = row['version'] if row['version'] is not None else 0
        version_check = expected_version if expected_version is not None else base_version

        replace_row = None
        if replace_aid is not None:
            replace_row = conn.execute(
                "SELECT * FROM email_attachments WHERE id=? AND email_id=?",
                (replace_aid, email_id),
            ).fetchone()
            if not replace_row:
                conn.rollback()
                return jsonify({'ok': False, 'error': 'replace-target-missing'}), 404

        max_count = int(current_app.config.get('ATTACHMENTS_MAX_COUNT', 25))
        if max_count > 0 and replace_row is None:
            total_count = conn.execute(
                "SELECT COUNT(*) FROM email_attachments WHERE email_id=?",
                (email_id,),
            ).fetchone()[0]
            if total_count >= max_count:
                conn.rollback()
                return jsonify({'ok': False, 'error': 'max-count-exceeded', 'limit': max_count}), 422

        _, staged_root = _get_storage_roots()
        email_dir = staged_root / str(email_id)
        email_dir.mkdir(parents=True, exist_ok=True)

        allocated_path = _allocate_staged_path(email_dir, upload_file.filename or 'attachment')
        allocated_path.write_bytes(file_bytes)
        written_path = allocated_path

        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)
        filename = allocated_path.name

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO email_attachments
                (email_id, filename, mime_type, size, sha256, disposition, content_id, is_original, is_staged, storage_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, ?)
            """,
            (
                email_id,
                filename,
                mime_type,
                file_size,
                sha256_hash,
                'attachment',
                None,
                str(allocated_path),
            ),
        )
        staged_id = cur.lastrowid

        manifest_entry: Dict[str, Any] = {
            'action': 'replace' if replace_row else 'add',
            'staged_ref': staged_id,
            'filename': filename,
            'mime_type': mime_type,
            'size': file_size,
            'sha256': sha256_hash,
            'uploaded_at': datetime.now(timezone.utc).isoformat(),
        }
        if replace_row:
            manifest_entry['aid'] = replace_row['id']
            manifest_entry['original_filename'] = replace_row['filename']
        manifest = _manifest_append_entry(manifest, manifest_entry)

        manifest_text = _dump_manifest(manifest)
        cur.execute(
            "UPDATE email_messages SET attachments_manifest=?, version=version+1 WHERE id=? AND version=?",
            (manifest_text, email_id, version_check),
        )
        if cur.rowcount == 0:
            conn.rollback()
            if written_path and written_path.exists():
                try:
                    written_path.unlink()
                except Exception:
                    log.warning(
                        '[attachments] Failed to remove staged file after version mismatch',
                        extra={'email_id': email_id, 'path': str(written_path)},
                    )
            latest = conn.execute(
                "SELECT attachments_manifest, version FROM email_messages WHERE id=?",
                (email_id,),
            ).fetchone()
            latest_manifest = _load_manifest_from_row(latest)
            latest_version = latest['version'] if latest and 'version' in latest.keys() else version_check
            return (
                jsonify(
                    {
                        'ok': False,
                        'error': 'version-mismatch',
                        'latest_version': latest_version,
                        'manifest': latest_manifest,
                    }
                ),
                409,
            )

        attachment_row = conn.execute(
            "SELECT * FROM email_attachments WHERE id=?",
            (staged_id,),
        ).fetchone()
        new_version_row = conn.execute(
            "SELECT version FROM email_messages WHERE id=?",
            (email_id,),
        ).fetchone()
        conn.commit()

        new_version = new_version_row['version'] if new_version_row else version_check + 1
        payload = {
            'ok': True,
            'staged_id': staged_id,
            'version': new_version,
            'attachment': _serialize_attachment_row(attachment_row),
            'manifest': manifest,
        }
        return jsonify(payload), 201
    except Exception:
        conn.rollback()
        if written_path and written_path.exists():
            try:
                written_path.unlink()
            except Exception:
                log.warning(
                    '[attachments] Failed to clean staged file on error',
                    extra={'email_id': email_id, 'path': str(written_path)},
                )
        raise
    finally:
        conn.close()


@bp_interception.route('/api/email/<int:email_id>/attachments/mark', methods=['POST'])
@login_required
def api_email_attachments_mark(email_id: int):
    if not _attachments_feature_enabled('ATTACHMENTS_EDIT_ENABLED'):
        return jsonify({'ok': False, 'error': 'disabled'}), 403

    payload = request.get_json(silent=True) or {}
    action = str(payload.get('action') or '').lower()
    version_value = payload.get('version')

    if action not in {'add', 'replace', 'remove', 'keep'}:
        return jsonify({'ok': False, 'error': 'invalid-action'}), 422

    if version_value is None:
        return jsonify({'ok': False, 'error': 'version-required'}), 400
    try:
        version_check = int(version_value)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'invalid-version'}), 422

    aid_value = payload.get('aid')
    staged_value = payload.get('staged_ref')

    aid: Optional[int] = None
    if aid_value is not None:
        try:
            aid = int(aid_value)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'invalid-aid'}), 422

    staged_ref: Optional[int] = None
    if staged_value is not None:
        try:
            staged_ref = int(staged_value)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'invalid-staged-ref'}), 422

    conn = _db()
    try:
        conn.execute('BEGIN')
        email_row = conn.execute(
            "SELECT id, attachments_manifest, version FROM email_messages WHERE id=?",
            (email_id,),
        ).fetchone()
        if not email_row:
            conn.rollback()
            return jsonify({'ok': False, 'error': 'not-found'}), 404

        manifest = _load_manifest_from_row(email_row)

        cur = conn.cursor()
        attachment_for_aid = None
        if aid is not None:
            attachment_for_aid = cur.execute(
                "SELECT * FROM email_attachments WHERE id=? AND email_id=?",
                (aid, email_id),
            ).fetchone()
            if not attachment_for_aid:
                conn.rollback()
                return jsonify({'ok': False, 'error': 'aid-not-found'}), 404

        staged_row = None
        if staged_ref is not None:
            staged_row = cur.execute(
                "SELECT * FROM email_attachments WHERE id=? AND email_id=?",
                (staged_ref, email_id),
            ).fetchone()
            if not staged_row:
                conn.rollback()
                return jsonify({'ok': False, 'error': 'staged-not-found'}), 404
            if not staged_row['is_staged']:
                conn.rollback()
                return jsonify({'ok': False, 'error': 'staged-invalid'}), 422

        if action == 'add':
            if staged_row is None:
                conn.rollback()
                return jsonify({'ok': False, 'error': 'staged-required'}), 422
            manifest_entry = {
                'action': 'add',
                'staged_ref': staged_row['id'],
                'filename': staged_row['filename'],
                'mime_type': staged_row['mime_type'],
                'size': staged_row['size'],
                'sha256': staged_row['sha256'],
                'uploaded_at': datetime.now(timezone.utc).isoformat(),
            }
            manifest = _manifest_append_entry(manifest, manifest_entry)
        elif action == 'replace':
            if aid is None or staged_row is None:
                conn.rollback()
                return jsonify({'ok': False, 'error': 'aid-and-staged-required'}), 422
            manifest_entry = {
                'action': 'replace',
                'aid': aid,
                'staged_ref': staged_row['id'],
                'filename': staged_row['filename'],
                'mime_type': staged_row['mime_type'],
                'size': staged_row['size'],
                'sha256': staged_row['sha256'],
                'uploaded_at': datetime.now(timezone.utc).isoformat(),
            }
            if attachment_for_aid:
                manifest_entry['original_filename'] = attachment_for_aid['filename']
            manifest = _manifest_append_entry(manifest, manifest_entry)
        elif action == 'remove':
            if aid is None:
                conn.rollback()
                return jsonify({'ok': False, 'error': 'aid-required'}), 422
            manifest = _manifest_remove_entries(manifest, aid=aid)
            manifest_entry = {
                'action': 'remove',
                'aid': aid,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }
            manifest['items'].append(manifest_entry)
        elif action == 'keep':
            if aid is None:
                conn.rollback()
                return jsonify({'ok': False, 'error': 'aid-required'}), 422
            manifest = _manifest_remove_entries(manifest, aid=aid)
            manifest_entry = {
                'action': 'keep',
                'aid': aid,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }
            manifest['items'].append(manifest_entry)

        manifest_text = _dump_manifest(manifest)
        cur.execute(
            "UPDATE email_messages SET attachments_manifest=?, version=version+1 WHERE id=? AND version=?",
            (manifest_text, email_id, version_check),
        )
        if cur.rowcount == 0:
            conn.rollback()
            latest = conn.execute(
                "SELECT attachments_manifest, version FROM email_messages WHERE id=?",
                (email_id,),
            ).fetchone()
            latest_manifest = _load_manifest_from_row(latest)
            latest_version = latest['version'] if latest and 'version' in latest.keys() else version_check
            return (
                jsonify(
                    {
                        'ok': False,
                        'error': 'version-mismatch',
                        'latest_version': latest_version,
                        'manifest': latest_manifest,
                    }
                ),
                409,
            )

        new_version_row = conn.execute(
            "SELECT version FROM email_messages WHERE id=?",
            (email_id,),
        ).fetchone()
        conn.commit()

        new_version = new_version_row['version'] if new_version_row else version_check + 1
        return jsonify({'ok': True, 'version': new_version, 'manifest': manifest})
    finally:
        conn.close()


@bp_interception.route('/api/email/<int:email_id>/attachments/staged/<int:staged_id>', methods=['DELETE'])
@login_required
def api_email_attachments_delete_staged(email_id: int, staged_id: int):
    if not _attachments_feature_enabled('ATTACHMENTS_EDIT_ENABLED'):
        return jsonify({'ok': False, 'error': 'disabled'}), 403

    version_raw = request.args.get('version')
    expected_version: Optional[int] = None
    if version_raw not in (None, ''):
        try:
            expected_version = int(version_raw)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'invalid-version'}), 422

    conn = _db()
    staged_path: Optional[Path] = None
    try:
        conn.execute('BEGIN')
        cur = conn.cursor()
        staged_row = cur.execute(
            "SELECT * FROM email_attachments WHERE id=? AND email_id=?",
            (staged_id, email_id),
        ).fetchone()
        if not staged_row:
            conn.rollback()
            return jsonify({'ok': False, 'error': 'not-found'}), 404
        if not staged_row['is_staged']:
            conn.rollback()
            return jsonify({'ok': False, 'error': 'not-staged'}), 422

        email_row = cur.execute(
            "SELECT id, attachments_manifest, version FROM email_messages WHERE id=?",
            (email_id,),
        ).fetchone()
        if not email_row:
            conn.rollback()
            return jsonify({'ok': False, 'error': 'not-found'}), 404

        manifest = _load_manifest_from_row(email_row)
        manifest = _manifest_remove_entries(manifest, staged_ref=staged_row['id'])
        manifest_text = _dump_manifest(manifest)

        base_version = email_row['version'] if email_row['version'] is not None else 0
        version_check = expected_version if expected_version is not None else base_version

        cur.execute(
            "UPDATE email_messages SET attachments_manifest=?, version=version+1 WHERE id=? AND version=?",
            (manifest_text, email_id, version_check),
        )
        if cur.rowcount == 0:
            conn.rollback()
            latest = cur.execute(
                "SELECT attachments_manifest, version FROM email_messages WHERE id=?",
                (email_id,),
            ).fetchone()
            latest_manifest = _load_manifest_from_row(latest)
            latest_version = latest['version'] if latest and 'version' in latest.keys() else version_check
            return (
                jsonify(
                    {
                        'ok': False,
                        'error': 'version-mismatch',
                        'latest_version': latest_version,
                        'manifest': latest_manifest,
                    }
                ),
                409,
            )

        staged_path = Path(staged_row['storage_path']).resolve()
        cur.execute(
            "DELETE FROM email_attachments WHERE id=?",
            (staged_id,),
        )

        new_version_row = cur.execute(
            "SELECT version FROM email_messages WHERE id=?",
            (email_id,),
        ).fetchone()
        conn.commit()

        new_version = new_version_row['version'] if new_version_row else version_check + 1

        try:
            _, staged_root = _get_storage_roots()
        except Exception:
            staged_root = None
        if (
            staged_path
            and staged_path.exists()
            and staged_path.is_file()
            and staged_root
            and _is_under(staged_path, staged_root)
        ):
            try:
                staged_path.unlink()
            except Exception as exc:
                log.warning(
                    '[attachments] Failed to remove staged file after delete',
                    extra={'email_id': email_id, 'path': str(staged_path), 'error': str(exc)},
                )

        return jsonify({'ok': True, 'removed': staged_id, 'version': new_version, 'manifest': manifest})
    finally:
        conn.close()

@bp_interception.route('/api/interception/release/<int:msg_id>', methods=['POST'])
@csrf.exempt
@limiter.limit(_RELEASE_LIMIT_STRING)
@simple_rate_limit('release', config=_RELEASE_RATE_LIMIT)
@login_required
def api_interception_release(msg_id: int):
    payload = request.get_json(silent=True) or {}
    edited_subject = payload.get('edited_subject')
    edited_body = payload.get('edited_body')
    edited_body_html = payload.get('edited_body_html')
    target_folder = normalize_folder(payload.get('target_folder', 'INBOX'))
    strip_attachments = bool(payload.get('strip_attachments'))
    idempotency_key = request.headers.get('X-Idempotency-Key')

    conn = _db()
    cur = conn.cursor()
    log.debug("[interception::release] begin", extra={'email_id': msg_id, 'target': target_folder})
    app_log = logging.getLogger("simple_app")

    lock_acquired = False
    temp_path: Optional[Path] = None
    mapped_bytes = None
    staged_rows: List[sqlite3.Row] = []
    response_payload: Dict[str, Any] = {}

    try:
        # Fast idempotency check before acquiring lock
        if idempotency_key:
            record = _get_idempotency_record(conn, idempotency_key)
            if record:
                status = (record['status'] or '').lower()
                stored_response = record['response_json']
                if status == 'success' and stored_response:
                    return current_app.response_class(stored_response, mimetype='application/json')
                if status == 'pending':
                    return jsonify({'ok': False, 'reason': 'release-in-progress'}), 409
                if status not in {'success', 'pending'}:
                    conn.execute("DELETE FROM idempotency_keys WHERE key=?", (idempotency_key,))
                    conn.commit()

        # Fetch message metadata
        row = cur.execute(
            """
        SELECT em.*, ea.imap_host, ea.imap_port, ea.imap_username, ea.imap_password, ea.imap_use_ssl
        FROM email_messages em JOIN email_accounts ea ON em.account_id = ea.id
        WHERE em.id=? AND em.direction='inbound'
        """,
            (msg_id,),
        ).fetchone()
        if not row:
            return jsonify({'ok': False, 'reason': 'not-found'}), 404

        app_log.debug("Entered release handler", extra={"email_id": msg_id})

        # Enhanced debugging for error tracking
        try:
            app_log.debug(f"[Release DEBUG] Checking interception_status for email {msg_id}")
            interception_status = str((row['interception_status'] or '')).upper()
            app_log.debug(f"[Release DEBUG] Interception status: {interception_status}")
        except Exception as e:
            app_log.error(f"[Release ERROR] Failed to get interception_status: {e}", exc_info=True)
            return jsonify({'ok': False, 'error': f'Failed to read status: {str(e)}'}), 500
        if interception_status == 'RELEASED':
            return jsonify({'ok': True, 'reason': 'already-released'})
        if interception_status == 'DISCARDED':
            return jsonify({'ok': False, 'reason': 'discarded'}), 409
        if interception_status != 'HELD':
            return jsonify({'ok': False, 'reason': 'not-held'}), 409

        if edited_subject is None:
            edited_subject = row['subject']
        if edited_body is None:
            edited_body = row['body_text'] or None

        # Acquire per-email release lock
        lock_acquired = _acquire_release_lock(conn, msg_id)
        if not lock_acquired:
            return jsonify({'ok': False, 'reason': 'release-in-progress'}), 409

        if idempotency_key:
            _set_idempotency_record(conn, idempotency_key, msg_id, 'pending')

        # Load original raw message
        try:
            app_log.debug(f"[Release DEBUG] Loading raw message for email {msg_id}")
            raw_path = row['raw_path']
            raw_content = row['raw_content']
            app_log.debug(f"[Release DEBUG] Raw path: {raw_path}, Raw content length: {len(raw_content) if raw_content else 0}")
        except Exception as e:
            app_log.error(f"[Release ERROR] Failed to access raw message fields: {e}", exc_info=True)
            return jsonify({'ok': False, 'error': f'Failed to access raw message: {str(e)}'}), 500
        if raw_path and os.path.exists(raw_path):
            with open(raw_path, 'rb') as f:
                original_bytes = f.read()
        elif raw_content:
            original_bytes = raw_content.encode('utf-8') if isinstance(raw_content, str) else raw_content
        else:
            raise RuntimeError('raw-missing')

        original_msg = BytesParser(policy=default_policy).parsebytes(original_bytes)

        attachments_root, staged_root = _get_storage_roots()
        attachment_rows = conn.execute(
            "SELECT * FROM email_attachments WHERE email_id=?",
            (msg_id,),
        ).fetchall()
        staged_rows = [row for row in attachment_rows if row['is_staged']]
        manifest = _load_manifest_from_row(row)
        plan = _assemble_attachment_plan(attachment_rows, manifest)
        if strip_attachments:
            removed_manifest = [
                {'row': r, 'manifest': {'action': 'remove'}}
                for r in attachment_rows
                if r['is_original']
            ]
            plan = {'final': [], 'removed': removed_manifest, 'replaced': [], 'added': []}

        payload_for_builder = dict(payload)
        payload_for_builder['edited_subject'] = edited_subject
        payload_for_builder['edited_body'] = edited_body
        payload_for_builder['edited_body_html'] = edited_body_html

        rebuilt_message = _build_release_message(
            row,
            original_msg,
            payload_for_builder,
            plan,
            attachments_root,
            staged_root,
            strip_notice=strip_attachments,
        )
        msg = rebuilt_message

        removed = [
            entry['row']['filename'] or f"attachment-{entry['row']['id']}"
            for entry in plan['removed']
        ]
        attachments_summary = {
            'added': len(plan['added']),
            'removed': len(plan['removed']),
            'replaced': len(plan['replaced']),
        }

        decrypted_pass = decrypt_credential(row['imap_password'])
        try:
            if row['imap_use_ssl']:
                imap = imaplib.IMAP4_SSL(row['imap_host'], int(row['imap_port']))
            else:
                imap = imaplib.IMAP4(row['imap_host'], int(row['imap_port']))
            if not decrypted_pass:
                raise RuntimeError('Decrypted password missing')
            imap.login(row['imap_username'], decrypted_pass)
            # Normalize folder before IMAP select to prevent label name errors
            status, _ = imap.select(target_folder)
            if status != 'OK':
                imap.select('INBOX')

            original_message_id = (row['message_id'] or '').strip()
            message_id_hdr = (msg.get('Message-ID') or '').strip()
            if not message_id_hdr:
                new_mid = make_msgid()
                msg['Message-ID'] = new_mid
                message_id_hdr = new_mid.strip()

            if original_message_id:
                if 'X-EMT-Released-From' in msg:
                    msg.replace_header('X-EMT-Released-From', original_message_id)
                else:
                    msg['X-EMT-Released-From'] = original_message_id
                app_log.info(
                    "[Idempotency] Added X-EMT-Released-From header",
                    extra={"email_id": msg_id, "original_message_id": original_message_id},
                )

            # Use internaldate if available; else use current time
            date_param = None
            try:
                if row['original_internaldate']:
                    from datetime import datetime as _dt

                    try:
                        dt = _dt.fromisoformat(str(row['original_internaldate']))
                        date_param = imaplib.Time2Internaldate(dt.timetuple())
                    except Exception:
                        date_param = None
                if not date_param:
                    import time as _t

                    date_param = imaplib.Time2Internaldate(_t.localtime())
            except Exception:
                import time as _t

                date_param = imaplib.Time2Internaldate(_t.localtime())

            already_present = False
            try:
                if message_id_hdr:
                    imap.select(target_folder)
                    typ0, data0 = imap.search(None, 'HEADER', 'Message-ID', f"{message_id_hdr}")
                    already_present = bool(data0 and data0[0] and len(data0[0].split()) > 0)
            except Exception:
                already_present = False

            release_marker = f"emt-release-{msg_id}"
            if msg.get(RELEASE_BYPASS_HEADER):
                del msg[RELEASE_BYPASS_HEADER]
            msg[RELEASE_BYPASS_HEADER] = release_marker
            if msg.get(RELEASE_EMAIL_ID_HEADER):
                del msg[RELEASE_EMAIL_ID_HEADER]
            msg[RELEASE_EMAIL_ID_HEADER] = str(msg_id)

            message_bytes = msg.as_bytes(policy=default_policy)

            with track_latency(release_latency, action='RELEASED'):
                if not already_present:
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                        tmp_file.write(message_bytes)
                        temp_path = Path(tmp_file.name)
                    with temp_path.open('rb') as mapped_file:
                        mapped_bytes = mmap.mmap(mapped_file.fileno(), 0, access=mmap.ACCESS_READ)
                        imap.append(target_folder, '', date_param, mapped_bytes[:])

                # Existing Gmail cleanup phases (B-E)
                original_uid = row['original_uid']
                try:
                    quarantine_folder = row['quarantine_folder'] if row['quarantine_folder'] else 'Quarantine'
                except (KeyError, TypeError):
                    quarantine_folder = 'Quarantine'

                host_l = str(row['imap_host'] if row['imap_host'] else '').lower()
                is_gmail = any(k in host_l for k in ("gmail", "googlemail", "google"))

                # Phase A: remove from quarantine
                if original_uid:
                    try:
                        app_log.info(
                            "[Release] Phase A: Pre-append Quarantine cleanup",
                            extra={"email_id": msg_id, "original_uid": original_uid, "folder": quarantine_folder},
                        )
                        typ, _ = imap.select(quarantine_folder)
                        if typ == 'OK':
                            imap.uid('STORE', str(original_uid), '+FLAGS', r'(\\Deleted)')
                            imap.expunge()
                            app_log.info(
                                "[Release] Phase A: SUCCESS - Original deleted",
                                extra={"email_id": msg_id, "uid": original_uid},
                            )
                        else:
                            app_log.warning(
                                f"[Release] Phase A: Failed to select {quarantine_folder}",
                                extra={"email_id": msg_id, "typ": typ},
                            )
                    except Exception as exc:
                        app_log.warning(
                            "[Release] Phase A: Quarantine cleanup failed",
                            extra={"email_id": msg_id, "error": str(exc)},
                        )
                else:
                    app_log.info(
                        "[Release] Phase A: No original_uid, skipping Quarantine delete",
                        extra={"email_id": msg_id},
                    )

                # Phase B: append edited message already handled above

                # Phase C onwards reuse existing logic
                if is_gmail and _server_supports_x_gm(imap):
                    try:
                        app_log.info(
                            "[Release] Phase C: Gmail thread cleanup starting",
                            extra={"email_id": msg_id, "is_gmail": is_gmail},
                        )
                        imap.select(target_folder)
                        edited_uid = None
                        if message_id_hdr:
                            typ, data = imap.uid('SEARCH', None, 'HEADER', 'Message-ID', f'"{message_id_hdr}"')
                            if typ == 'OK' and data and data[0]:
                                uids = [int(x) for x in data[0].split()]
                                edited_uid = uids[0] if uids else None
                                app_log.info(
                                    "[Release] Phase C: Found edited message UID",
                                    extra={"email_id": msg_id, "edited_uid": edited_uid, "message_id": message_id_hdr},
                                )
                        if not edited_uid:
                            app_log.warning(
                                "[Release] Phase C: Could not find edited message UID, skipping thread cleanup",
                                extra={"email_id": msg_id},
                            )
                        else:
                            thread_id = _gm_fetch_thrid(imap, edited_uid)
                            if thread_id:
                                app_log.info(
                                    "[Release] Phase C: Fetched thread ID",
                                    extra={"email_id": msg_id, "thread_id": thread_id},
                                )
                                imap.select('"[Gmail]/All Mail"')
                                typ, data = imap.uid('SEARCH', None, 'X-GM-RAW', f'"thread:{thread_id}"')
                                if typ == 'OK' and data and data[0]:
                                    thread_uids = [int(x) for x in data[0].split()]
                                    app_log.info(
                                        "[Release] Phase C: Found thread messages in All Mail",
                                        extra={"email_id": msg_id, "thread_id": thread_id, "count": len(thread_uids), "uids": thread_uids},
                                    )
                                    imap.select('"[Gmail]/All Mail"')
                                    edited_uid_in_allmail = None
                                    if message_id_hdr:
                                        typ2, data2 = imap.uid('SEARCH', None, 'HEADER', 'Message-ID', f'"{message_id_hdr}"')
                                        if typ2 == 'OK' and data2 and data2[0]:
                                            uids2 = [int(x) for x in data2[0].split()]
                                            edited_uid_in_allmail = uids2[0] if uids2 else None
                                    removed_labels_count = 0
                                    for uid in thread_uids:
                                        if edited_uid_in_allmail and uid == edited_uid_in_allmail:
                                            app_log.info(
                                                "[Release] Phase C: Preserving edited message",
                                                extra={"email_id": msg_id, "uid": uid},
                                            )
                                            continue
                                        try:
                                            labels_to_remove = []
                                            ftyp, fdat = imap.uid('FETCH', str(uid), '(X-GM-LABELS)')
                                            if ftyp == 'OK' and fdat and isinstance(fdat[0], tuple):
                                                raw = fdat[0][1].decode('utf-8', 'ignore') if isinstance(fdat[0][1], bytes) else str(fdat[0][1])
                                                app_log.info(
                                                    "[Release] Phase C: Fetched labels",
                                                    extra={"email_id": msg_id, "uid": uid, "raw_labels": raw[:200]},
                                                )
                                                for token in re.findall(r'"\\[?[^\"]+\\]?"|\\\\\w+', raw):
                                                    label_token = token.strip('"').strip()
                                                    if (
                                                        label_token.lower() == 'quarantine'
                                                        or label_token.endswith('/Quarantine')
                                                        or label_token.endswith('.Quarantine')
                                                        or 'Quarantine' in label_token
                                                    ):
                                                        labels_to_remove.append(label_token)
                                                        app_log.info(
                                                            "[Release] Phase C: Found Quarantine label",
                                                            extra={"email_id": msg_id, "uid": uid, "label": label_token},
                                                        )
                                            typ_store, _ = _uid_store(imap, uid, '-X-GM-LABELS', r'(\\Inbox)')
                                            if typ_store == 'OK':
                                                removed_labels_count += 1
                                                app_log.info(
                                                    "[Release] Phase C: Removed \\Inbox from thread message",
                                                    extra={"email_id": msg_id, "uid": uid},
                                                )
                                            for label in labels_to_remove:
                                                typ_quar, _ = _uid_store(imap, uid, '-X-GM-LABELS', f'("{label}")')
                                                if typ_quar == 'OK':
                                                    removed_labels_count += 1
                                                    app_log.info(
                                                        "[Release] Phase C: Removed Quarantine label",
                                                        extra={"email_id": msg_id, "uid": uid, "label": label},
                                                    )
                                        except Exception as exc:
                                            app_log.warning(
                                                "[Release] Phase C: Failed to remove labels",
                                                extra={"email_id": msg_id, "uid": uid, "error": str(exc)},
                                            )
                                    app_log.info(
                                        "[Release] Phase C: SUCCESS - Thread cleanup complete",
                                        extra={"email_id": msg_id, "thread_id": thread_id, "processed": len(thread_uids), "labels_removed": removed_labels_count},
                                    )
                                else:
                                    app_log.warning(
                                        "[Release] Phase C: No messages found in thread",
                                        extra={"email_id": msg_id, "thread_id": thread_id},
                                    )
                            else:
                                app_log.warning(
                                    "[Release] Phase C: Could not fetch thread ID",
                                    extra={"email_id": msg_id, "edited_uid": edited_uid},
                                )
                    except Exception as exc:
                        app_log.error(
                            "[Release] Phase C: Thread cleanup failed",
                            extra={"email_id": msg_id, "error": str(exc), "traceback": traceback.format_exc()},
                        )
                # Failsafe INBOX cleanup and verification remain unchanged
                try:
                    typ, data = imap.select("INBOX", readonly=False)
                    app_log.debug(
                        "INBOX select for failsafe cleanup",
                        extra={"email_id": msg_id, "typ": typ, "is_gmail": is_gmail},
                    )
                    if typ == "OK" and original_message_id:
                        inbox_count = data[0].decode() if data and data[0] else "?"
                        all_typ, all_data = imap.uid('SEARCH', None, 'ALL')
                        all_uids = all_data[0].decode() if all_data and all_data[0] else ""
                        uid_list = all_uids.split()[:5]
                        app_log.debug(
                            "INBOX state before search",
                            extra={
                                "email_id": msg_id,
                                "inbox_message_count": inbox_count,
                                "total_uids": len(all_uids.split()) if all_uids else 0,
                                "sample_uids": uid_list,
                                "searching_for_message_id": original_message_id,
                            },
                        )
                        uids = _robust_message_id_search(imap, "INBOX", original_message_id, is_gmail=is_gmail)
                        if uids:
                            app_log.info(
                                "[Failsafe] Found original in INBOX, removing",
                                extra={"email_id": msg_id, "uids": uids},
                            )
                            for uid in uids:
                                imap.uid('STORE', uid, '+FLAGS', r'(\\Deleted)')
                            imap.expunge()
                            app_log.info(
                                "[Failsafe] Removed original from INBOX by UID/EXPUNGE",
                                extra={"email_id": msg_id, "uids": uids},
                            )
                        else:
                            app_log.info(
                                "[Failsafe] No original found in INBOX (may already be cleaned or never existed there)",
                                extra={"email_id": msg_id},
                            )
                except Exception as exc:
                    app_log.warning(
                        "[Failsafe DEBUG] INBOX cleanup failed",
                        extra={"email_id": msg_id, "error": str(exc)},
                    )

                verify_ok = True
                duplicate_detected = False
                try:
                    if message_id_hdr:
                        app_log.info(
                            "[Release] Phase E: Starting verification",
                            extra={"email_id": msg_id, "is_gmail": is_gmail},
                        )
                        imap.select(target_folder)
                        typ, data = imap.search(None, 'HEADER', 'Message-ID', f"{message_id_hdr}")
                        found = data and data[0] and len(data[0].split()) > 0
                        verify_ok = bool(found)
                        if verify_ok:
                            app_log.info(
                                "[Release] Phase E: Edited message verified in INBOX",
                                extra={"email_id": msg_id, "message_id": message_id_hdr},
                            )
                        else:
                            app_log.error(
                                "[Release] Phase E: Edited message NOT found in INBOX",
                                extra={"email_id": msg_id, "message_id": message_id_hdr},
                            )
                        if verify_ok and is_gmail and _server_supports_x_gm(imap):
                            try:
                                imap.select(target_folder)
                                typ, data = imap.uid('SEARCH', None, 'HEADER', 'Message-ID', f'"{message_id_hdr}"')
                                edited_uid = None
                                if typ == 'OK' and data and data[0]:
                                    uids = [int(x) for x in data[0].split()]
                                    edited_uid = uids[0] if uids else None
                                if edited_uid:
                                    thread_id = _gm_fetch_thrid(imap, edited_uid)
                                    if thread_id:
                                        imap.select("INBOX")
                                        typ, data = imap.uid('SEARCH', None, 'X-GM-RAW', f'"in:inbox thread:{thread_id}"')
                                        if typ == 'OK' and data and data[0]:
                                            inbox_thread_uids = [int(x) for x in data[0].split()]
                                            app_log.info(
                                                "[Release] Phase E: Found thread messages in INBOX",
                                                extra={"email_id": msg_id, "count": len(inbox_thread_uids), "uids": inbox_thread_uids},
                                            )
                                            if len(inbox_thread_uids) > 1:
                                                duplicate_detected = True
                                                app_log.error(
                                                    "[Release] Phase E: DUPLICATE DETECTED - Multiple thread messages in INBOX",
                                                    extra={"email_id": msg_id, "count": len(inbox_thread_uids), "uids": inbox_thread_uids, "expected_uid": edited_uid},
                                                )
                                            elif len(inbox_thread_uids) == 1 and inbox_thread_uids[0] == edited_uid:
                                                app_log.info(
                                                    "[Release] Phase E: SUCCESS - Only edited message in INBOX",
                                                    extra={"email_id": msg_id, "uid": edited_uid},
                                                )
                                            else:
                                                app_log.warning(
                                                    "[Release] Phase E: Unexpected UID in INBOX",
                                                    extra={"email_id": msg_id, "found_uids": inbox_thread_uids, "expected_uid": edited_uid},
                                                )
                                        if original_message_id:
                                            imap.select("INBOX")
                                            typ, data = imap.uid('SEARCH', None, 'HEADER', 'Message-ID', f'"{original_message_id}"')
                                            if typ == 'OK' and data and data[0]:
                                                original_found = [int(x) for x in data[0].split()]
                                                if original_found:
                                                    duplicate_detected = True
                                                    app_log.error(
                                                        "[Release] Phase E: ORIGINAL STILL IN INBOX",
                                                        extra={"email_id": msg_id, "original_uids": original_found, "original_message_id": original_message_id},
                                                    )
                                                else:
                                                    app_log.info(
                                                        "[Release] Phase E: Original correctly removed from INBOX",
                                                        extra={"email_id": msg_id},
                                                    )
                                else:
                                    app_log.warning(
                                        "[Release] Phase E: Could not find edited UID for verification",
                                        extra={"email_id": msg_id},
                                    )
                            except Exception as exc:
                                app_log.warning(
                                    "[Release] Phase E: Thread verification failed (non-fatal)",
                                    extra={"email_id": msg_id, "error": str(exc)},
                                )
                    else:
                        verify_ok = True
                except Exception as exc:
                    app_log.error(
                        "[Release] Phase E: Verification failed",
                        extra={"email_id": msg_id, "error": str(exc)},
                    )
                    verify_ok = False

                if duplicate_detected:
                    app_log.error(
                        "[Release] Phase E: VERIFICATION COMPLETE - DUPLICATES DETECTED",
                        extra={"email_id": msg_id, "verify_ok": verify_ok},
                    )
                elif verify_ok:
                    app_log.info(
                        "[Release] Phase E: VERIFICATION COMPLETE - SUCCESS",
                        extra={"email_id": msg_id},
                    )
                else:
                    app_log.error(
                        "[Release] Phase E: VERIFICATION COMPLETE - FAILED",
                        extra={"email_id": msg_id},
                    )

                if not verify_ok:
                    try:
                        imap.logout()
                    except Exception as exc:
                        log.debug(
                            "[interception::release] IMAP logout failed during verify failure (non-critical)",
                            extra={'email_id': msg_id, 'error': str(exc)},
                        )
                    raise RuntimeError('verify-failed')

                try:
                    imap.logout()
                except Exception:
                    pass
        except Exception as exc:
            raise RuntimeError(f'append-failed:{exc}') from exc

        # Update database and clear manifest
        cur.execute(
            """
            UPDATE email_messages
            SET interception_status='RELEASED',
                status='DELIVERED',
                edited_message_id=?,
                attachments_manifest=NULL,
                version=version+1,
                processed_at=datetime('now'),
                action_taken_at=datetime('now')
            WHERE id=?
            """,
            (msg.get('Message-ID'), msg_id),
        )
        cur.execute(
            "DELETE FROM email_attachments WHERE email_id=? AND is_staged=1",
            (msg_id,),
        )
        conn.commit()

        for staged in staged_rows:
            try:
                storage_path = Path(staged['storage_path']).resolve()
                if storage_path.exists() and storage_path.is_file() and _is_under(storage_path, staged_root):
                    storage_path.unlink()
            except Exception as exc:
                log.warning(
                    "[attachments] Failed to remove staged file after release",
                    extra={'email_id': msg_id, 'path': staged.get('storage_path'), 'error': str(exc)},
                )

        record_release(action='RELEASED', account_id=row['account_id'] if 'account_id' in row.keys() else None)

        response_payload = {
            'ok': True,
            'released_to': target_folder,
            'attachments_removed': removed,
            'attachments_summary': attachments_summary,
        }
        if idempotency_key:
            _set_idempotency_record(conn, idempotency_key, msg_id, 'success', response_payload)

        try:
            log_action(
                'RELEASE',
                getattr(current_user, 'id', None),
                msg_id,
                f"Released to {target_folder}; edited={bool(edited_subject or edited_body)}; removed={removed}",
            )
        except Exception:
            pass
        log.info(
            "[interception::release] success",
            extra={
                'email_id': msg_id,
                'target': target_folder,
                'attachments_removed': bool(removed),
                'attachments_summary': attachments_summary,
            },
        )
        return jsonify(response_payload)

    except RuntimeError as runtime_error:
        conn.rollback()
        reason = str(runtime_error)
        error_payload = {'ok': False, 'reason': reason}
        if idempotency_key:
            _set_idempotency_record(conn, idempotency_key, msg_id, 'failed', error_payload)
        log.error(
            "[interception::release] runtime failure",
            extra={'email_id': msg_id, 'reason': reason, 'traceback': traceback.format_exc()},
            exc_info=True
        )
        return jsonify(error_payload), 502 if reason == 'verify-failed' else 500
    except Exception as exc:
        conn.rollback()
        error_type = type(exc).__name__
        error_payload = {
            'ok': False,
            'reason': 'append-failed',
            'error': str(exc),
            'error_type': error_type
        }
        if idempotency_key:
            _set_idempotency_record(conn, idempotency_key, msg_id, 'failed', error_payload)
        log.exception(
            "[interception::release] append failed",
            extra={
                'email_id': msg_id,
                'target': target_folder,
                'error_type': error_type,
                'error_message': str(exc),
                'traceback': traceback.format_exc()
            },
        )
        app_log.error(
            f"[Release] CRITICAL ERROR during release operation",
            extra={
                'email_id': msg_id,
                'error_type': error_type,
                'error': str(exc),
                'traceback': traceback.format_exc()
            },
            exc_info=True
        )
        return jsonify(error_payload), 500
    finally:
        if mapped_bytes:
            try:
                mapped_bytes.close()
            except Exception:
                pass
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        if lock_acquired:
            try:
                _release_release_lock(conn, msg_id)
            except Exception:
                pass
        conn.close()

@bp_interception.route('/api/interception/discard/<int:msg_id>', methods=['POST'])
@login_required
def api_interception_discard(msg_id:int):
    """Idempotent discard: if already DISCARDED (or not HELD), respond ok with no-op.
    Returns JSON: { ok: true, status: <current|DISCARDED>, changed: 0|1 }
    """
    conn = _db(); cur = conn.cursor()
    row = cur.execute("SELECT interception_status FROM email_messages WHERE id=?", (msg_id,)).fetchone()
    if not row:
        conn.close();
        return jsonify({'ok': False, 'reason': 'not-found'}), 404
    status = row['interception_status']
    if status == 'DISCARDED':
        conn.close();
        return jsonify({'ok': True, 'status': 'DISCARDED', 'changed': 0, 'already': True})
    if status != 'HELD':
        # No state change needed; treat as idempotent no-op
        conn.close();
        return jsonify({'ok': True, 'status': status, 'changed': 0, 'noop': True})
    # Transition HELD -> DISCARDED
    cur.execute("UPDATE email_messages SET interception_status='DISCARDED', action_taken_at=datetime('now') WHERE id=?", (msg_id,))
    changed = cur.rowcount or 0
    conn.commit(); conn.close()
    return jsonify({'ok': True, 'status': 'DISCARDED', 'changed': int(changed)})

@bp_interception.route('/api/inbox')
@login_required
def api_inbox():
    status_filter = request.args.get('status','').strip().upper() or None
    account_id = request.args.get('account_id', type=int)
    q = (request.args.get('q') or '').strip()
    limit = request.args.get('limit', type=int)
    if not limit or limit <= 0:
        limit = 200
    limit = max(10, min(limit, 500))
    conn = _db(); cur = conn.cursor(); params=[]; clauses=[]
    if status_filter:
        clauses.append("(interception_status = ? OR status = ?)"); params.extend([status_filter,status_filter])
    if account_id:
        clauses.append("account_id = ?"); params.append(account_id)
    if q:
        like=f"%{q}%"; clauses.append("(sender LIKE ? OR subject LIKE ?)"); params.extend([like,like])
    # Filter out SMTP self-check messages from inbox view
    clauses.append("sender != ?"); params.append('selfcheck@localhost')
    where = ('WHERE '+ ' AND '.join(clauses)) if clauses else ''
    rows = cur.execute(
        f"""
        SELECT id, account_id, sender, recipients, subject, interception_status, status, created_at, latency_ms, body_text, raw_path
        FROM email_messages
        {where}
        ORDER BY id DESC LIMIT ?
        """,
        (*params, limit)
    ).fetchall()
    msgs=[]
    for r in rows:
        d=dict(r); body_txt=(d.get('body_text') or '')
        d['preview_snippet']=' '.join(body_txt.split())[:160]
        msgs.append(d)
    conn.close(); return jsonify({'messages':msgs,'count':len(msgs)})

@bp_interception.route('/api/email/<int:email_id>/edit', methods=['POST'])
@csrf.exempt
@limiter.limit(_EDIT_LIMIT_STRING)
@simple_rate_limit('edit', config=_EDIT_RATE_LIMIT)
@login_required
def api_email_edit(email_id:int):
    payload = request.get_json(silent=True) or {}
    subject = payload.get('subject'); body_text = payload.get('body_text'); body_html = payload.get('body_html')
    if not any([subject, body_text, body_html]):
        return jsonify({'ok':False,'error':'no-fields'}), 400
    conn = _db(); cur = conn.cursor()
    row = cur.execute("SELECT id, interception_status FROM email_messages WHERE id=?", (email_id,)).fetchone()
    if not row: conn.close(); return jsonify({'ok':False,'error':'not-found'}), 404
    if row['interception_status'] != 'HELD': conn.close(); return jsonify({'ok':False,'error':'not-held'}), 409
    fields=[]; values=[]
    if subject is not None: fields.append('subject = ?'); values.append(subject)
    if body_text is not None: fields.append('body_text = ?'); values.append(body_text)
    if body_html is not None: fields.append('body_html = ?'); values.append(body_html)
    values.append(email_id)
    cur.execute(f"UPDATE email_messages SET {', '.join(fields)}, updated_at = datetime('now') WHERE id = ?", values)
    conn.commit()
    # Re-read to verify persistence
    verify = cur.execute("SELECT id, subject, body_text, body_html FROM email_messages WHERE id = ?", (email_id,)).fetchone()
    result = {'ok': True, 'updated_fields': [f.split('=')[0].strip() for f in fields]}
    if verify:
        result['verified'] = {k: verify[k] for k in verify.keys()}
    conn.close()
    # Best-effort audit
    try:
        log_action('EDIT', getattr(current_user, 'id', None), email_id, f"Updated fields: {', '.join(result.get('updated_fields', []))}")
    except Exception:
        pass
    return jsonify(result)


@bp_interception.route('/api/email/<int:email_id>/intercept', methods=['POST'])
@csrf.exempt
@login_required
def api_email_intercept(email_id:int):
    """Manually intercept an email with remote MOVE to Quarantine folder (migrated)."""
    conn = _db(); cur = conn.cursor()
    row = cur.execute(
        """
        SELECT em.*, ea.imap_host, ea.imap_port, ea.imap_username, ea.imap_password
        FROM email_messages em
        LEFT JOIN email_accounts ea ON em.account_id = ea.id
        WHERE em.id=?
        """,
        (email_id,),
    ).fetchone()
    if not row:
        conn.close(); return jsonify({'success': False, 'error': 'Not found'}), 404
    if not row['account_id']:
        conn.close(); return jsonify({'success': False, 'error': 'No linked account'}), 400

    previous = (row['interception_status'] or '').upper()
    if previous == 'HELD':
        conn.close()
        return jsonify({'success': True, 'email_id': email_id, 'remote_move': False, 'previous_status': previous, 'note': 'already-held'})

    remote_move = False
    note = None
    effective_quarantine = row['quarantine_folder'] if 'quarantine_folder' in row.keys() and row['quarantine_folder'] else 'Quarantine'
    resolved_uid = row['original_uid']
    log.debug("[interception::manual_intercept] begin", extra={'email_id': email_id, 'account_id': row['account_id'], 'previous_status': previous, 'resolved_uid': resolved_uid})

    try:
        host = row['imap_host']; port = int(row['imap_port'] or 993)
        username = row['imap_username']; password = decrypt_credential(row['imap_password'])
        if not password:
            raise RuntimeError('Decrypted password missing')
        imap_obj = imaplib.IMAP4_SSL(host, port) if port == 993 else imaplib.IMAP4(host, port)
        try:
            if port != 993:
                imap_obj.starttls()
        except Exception:
            pass
        imap_obj.login(username, password)
        try:
            imap_obj.select('INBOX')
        except Exception:
            imap_obj.select()

        effective_quarantine = _ensure_quarantine(imap_obj, effective_quarantine)

        def _search_uid(header: str, value: Optional[str]) -> Optional[str]:
            if not header or not value:
                return None
            for candidate in (value, f'"{value}"'):
                try:
                    typ, data = cast(Any, imap_obj).uid('SEARCH', None, 'HEADER', header, candidate)
                    if typ == 'OK' and data and data[0]:
                        parts = data[0].split()
                        if parts:
                            last = parts[-1]
                            return last.decode() if isinstance(last, bytes) else str(last)
                except Exception:
                    continue
            return None

        def _search_gmail_rfc(msg_id: Optional[str]) -> Optional[str]:
            if not msg_id or 'gmail' not in (host or '').lower():
                return None
            query = f'rfc822msgid:{msg_id}'
            try:
                typ, data = cast(Any, imap_obj).uid('SEARCH', None, 'X-GM-RAW', query)
                if typ == 'OK' and data and data[0]:
                    parts = data[0].split()
                    if parts:
                        last = parts[-1]
                        return last.decode() if isinstance(last, bytes) else str(last)
            except Exception:
                return None
            return None

        if not resolved_uid and row['message_id']:
            resolved_uid = _search_uid('Message-ID', row['message_id'])
        if not resolved_uid and row['subject']:
            resolved_uid = _search_uid('Subject', row['subject'])
        if not resolved_uid and row['message_id']:
            resolved_uid = _search_gmail_rfc(row['message_id'])

        if resolved_uid:
            uid_str = str(resolved_uid)
            log.debug("[interception::manual_intercept] moving message", extra={'email_id': email_id, 'uid': uid_str, 'target': effective_quarantine})
            remote_move = _move_uid_to_quarantine(imap_obj, uid_str, effective_quarantine)
        else:
            note = 'Remote UID not found for manual intercept'
            log.warning("[interception::manual_intercept] UID not resolved", extra={'email_id': email_id, 'account_id': row['account_id']})

        try:
            imap_obj.logout()
        except Exception:
            pass
    except Exception as exc:
        note = f'IMAP error: {exc}'

    if not remote_move:
        conn.close()
        status_code = 502 if note and 'error' in note.lower() else 409
        log.warning("[interception::manual_intercept] move failed", extra={'email_id': email_id, 'account_id': row['account_id'], 'note': note, 'status_code': status_code})
        return jsonify({'success': False, 'email_id': email_id, 'remote_move': False, 'previous_status': previous, 'note': note or 'Remote move failed'}), status_code

    if resolved_uid and not row['original_uid']:
        cur.execute('UPDATE email_messages SET original_uid=? WHERE id=?', (int(resolved_uid), email_id))

    cur.execute(
        """
        UPDATE email_messages
        SET interception_status='HELD',
            status='PENDING',
            quarantine_folder=?,
            action_taken_at=datetime('now')
        WHERE id=?
        """,
        (effective_quarantine, email_id),
    ); conn.commit()
    log.info("[interception::manual_intercept] success", extra={'email_id': email_id, 'account_id': row['account_id'], 'quarantine_folder': effective_quarantine})

    # Calculate latency_ms best-effort
    try:
        row_t = cur.execute("SELECT created_at, action_taken_at, latency_ms FROM email_messages WHERE id=?", (email_id,)).fetchone()
        if row_t and row_t['created_at'] and row_t['action_taken_at'] and row_t['latency_ms'] is None:
            cur.execute("UPDATE email_messages SET latency_ms = CAST((julianday(action_taken_at) - julianday(created_at)) * 86400000 AS INTEGER) WHERE id=?", (email_id,))
            conn.commit()
    except Exception:
        pass
    conn.close()

    # Best-effort audit log
    try:
        from app.services.audit import log_action
        user_id = getattr(current_user, 'id', None)
        log_action('MANUAL_INTERCEPT', user_id, email_id, f"Manual intercept: remote_move={remote_move}, previous_status={previous}{', note='+note if note else ''}")
    except Exception:
        pass

    return jsonify({'success': True, 'email_id': email_id, 'remote_move': True, 'previous_status': previous, 'note': note, 'quarantine_folder': effective_quarantine})


# ========== BATCH OPERATIONS FOR EMAIL MANAGEMENT ==========

@bp_interception.route('/api/emails/batch-discard', methods=['POST'])
@login_required
def api_batch_discard():
    """Batch discard emails (mark as DISCARDED, don't delete from database).

    Expects JSON body: { "email_ids": [1, 2, 3, ...] }
    Returns: { "success": true, "processed": 150, "failed": 0, "results": [...] }
    """
    try:
        data = request.get_json() or {}
        email_ids = data.get('email_ids', [])

        if not email_ids or not isinstance(email_ids, list):
            return jsonify({'success': False, 'error': 'email_ids array required'}), 400

        if len(email_ids) > 1000:
            return jsonify({'success': False, 'error': 'Maximum 1000 emails per batch'}), 400

        conn = _db()
        cur = conn.cursor()

        processed = 0
        failed = 0
        results = []

        # Batch update in single transaction for performance
        for email_id in email_ids:
            try:
                row = cur.execute(
                    "SELECT interception_status FROM email_messages WHERE id=?",
                    (email_id,)
                ).fetchone()

                if not row:
                    failed += 1
                    results.append({'id': email_id, 'status': 'not_found'})
                    continue

                if row['interception_status'] == 'DISCARDED':
                    processed += 1
                    results.append({'id': email_id, 'status': 'already_discarded'})
                    continue

                cur.execute(
                    "UPDATE email_messages SET interception_status='DISCARDED', action_taken_at=datetime('now') WHERE id=?",
                    (email_id,)
                )
                processed += 1
                results.append({'id': email_id, 'status': 'discarded'})

            except Exception as e:
                failed += 1
                results.append({'id': email_id, 'status': 'error', 'error': str(e)})
                log.error(f"[batch-discard] Failed for email {email_id}: {e}")

        conn.commit()
        conn.close()

        # Audit log for batch operation
        try:
            from app.services.audit import log_action
            user_id = getattr(current_user, 'id', None)
            log_action('BATCH_DISCARD', user_id, None, f"Batch discarded {processed} emails (failed: {failed})")
        except Exception:
            pass

        return jsonify({
            'success': True,
            'processed': processed,
            'failed': failed,
            'total': len(email_ids),
            'results': results
        })

    except Exception as e:
        log.exception("[batch-discard] Unexpected error")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp_interception.route('/api/emails/batch-delete', methods=['POST'])
@login_required
def api_batch_delete():
    """Permanently delete emails from database (hard delete).

    Expects JSON body: { "email_ids": [1, 2, 3, ...] }
    Returns: { "success": true, "deleted": 150, "failed": 0 }

    WARNING: This is permanent deletion. Cannot be undone.
    """
    try:
        data = request.get_json() or {}
        email_ids = data.get('email_ids', [])

        if not email_ids or not isinstance(email_ids, list):
            return jsonify({'success': False, 'error': 'email_ids array required'}), 400

        if len(email_ids) > 1000:
            return jsonify({'success': False, 'error': 'Maximum 1000 emails per batch'}), 400

        conn = _db()
        cur = conn.cursor()

        deleted = 0
        failed = 0

        # Use parameterized query with IN clause for batch delete
        placeholders = ','.join('?' * len(email_ids))

        try:
            cur.execute(
                f"DELETE FROM email_messages WHERE id IN ({placeholders})",
                email_ids
            )
            deleted = cur.rowcount
            conn.commit()
        except Exception as e:
            failed = len(email_ids)
            log.error(f"[batch-delete] Failed to delete emails: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            conn.close()

        # Audit log for batch deletion
        try:
            from app.services.audit import log_action
            user_id = getattr(current_user, 'id', None)
            log_action('BATCH_DELETE', user_id, None, f"Permanently deleted {deleted} emails")
        except Exception:
            pass

        return jsonify({
            'success': True,
            'deleted': deleted,
            'failed': failed,
            'total': len(email_ids)
        })

    except Exception as e:
        log.exception("[batch-delete] Unexpected error")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp_interception.route('/api/emails/delete-all-discarded', methods=['DELETE', 'POST'])
@login_required
def api_delete_all_discarded():
    """Delete ALL emails with interception_status='DISCARDED' from database.

    Query params:
        - account_id (optional): Limit to specific account
        - confirm=yes (required): Safety confirmation

    Returns: { "success": true, "deleted": 523, "message": "..." }

    WARNING: This permanently deletes ALL discarded emails. Cannot be undone.
    """
    try:
        # Safety confirmation required
        confirm = request.args.get('confirm') or request.json.get('confirm') if request.json else None
        if confirm != 'yes':
            return jsonify({
                'success': False,
                'error': 'Confirmation required. Pass confirm=yes'
            }), 400

        account_id = request.args.get('account_id', type=int)

        conn = _db()
        cur = conn.cursor()

        # Build delete query with optional account filter
        if account_id:
            cur.execute(
                "DELETE FROM email_messages WHERE interception_status='DISCARDED' AND account_id=?",
                (account_id,)
            )
        else:
            cur.execute("DELETE FROM email_messages WHERE interception_status='DISCARDED'")

        deleted = cur.rowcount
        conn.commit()
        conn.close()

        # Audit log
        try:
            from app.services.audit import log_action
            user_id = getattr(current_user, 'id', None)
            scope = f"account_id={account_id}" if account_id else "all accounts"
            log_action('DELETE_ALL_DISCARDED', user_id, None, f"Deleted {deleted} discarded emails ({scope})")
        except Exception:
            pass

        message = f"Successfully deleted {deleted} discarded email(s)"
        if account_id:
            message += f" from account {account_id}"

        return jsonify({
            'success': True,
            'deleted': deleted,
            'message': message
        })

    except Exception as e:
        log.exception("[delete-all-discarded] Unexpected error")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp_interception.route('/api/emails/bulk-release', methods=['POST'])
@login_required
@csrf.exempt
def bulk_release_emails():
    """Bulk release multiple emails to inbox"""
    try:
        data = request.get_json()
        email_ids = data.get('email_ids', [])

        if not email_ids or not isinstance(email_ids, list):
            return jsonify({'error': 'email_ids array required'}), 400

        released_count = 0
        errors = []

        with get_db() as conn:
            cursor = conn.cursor()

            for email_id in email_ids:
                try:
                    row = cursor.execute(
                        "SELECT interception_status, account_id FROM email_messages WHERE id=?",
                        (email_id,)
                    ).fetchone()

                    if not row:
                        errors.append(f"Email {email_id} not found")
                        continue

                    if row['interception_status'] != 'HELD':
                        errors.append(f"Email {email_id} not in HELD status")
                        continue

                    cursor.execute(
                        "UPDATE email_messages SET interception_status='RELEASED', status='RELEASED' WHERE id=?",
                        (email_id,)
                    )

                    log_action('email_released', current_user.id if current_user.is_authenticated else None, email_id, f'Bulk release')
                    released_count += 1

                except Exception as e:
                    log.error(f"Error releasing email {email_id}: {e}")
                    errors.append(f"Email {email_id}: {str(e)}")

            conn.commit()

        response = {'released': released_count}
        if errors:
            response['errors'] = errors

        return jsonify(response), 200

    except Exception as e:
        log.error(f"Bulk release error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp_interception.route('/api/emails/bulk-discard', methods=['POST'])
@login_required
@csrf.exempt
def bulk_discard_emails():
    """Bulk discard multiple emails"""
    try:
        data = request.get_json()
        email_ids = data.get('email_ids', [])

        if not email_ids or not isinstance(email_ids, list):
            return jsonify({'error': 'email_ids array required'}), 400

        discarded_count = 0
        errors = []

        with get_db() as conn:
            cursor = conn.cursor()

            for email_id in email_ids:
                try:
                    row = cursor.execute(
                        "SELECT interception_status FROM email_messages WHERE id=?",
                        (email_id,)
                    ).fetchone()

                    if not row:
                        errors.append(f"Email {email_id} not found")
                        continue

                    if row['interception_status'] == 'DISCARDED':
                        errors.append(f"Email {email_id} already discarded")
                        continue

                    cursor.execute(
                        "UPDATE email_messages SET interception_status='DISCARDED', status='DISCARDED' WHERE id=?",
                        (email_id,)
                    )

                    log_action('email_discarded', current_user.id if current_user.is_authenticated else None, email_id, f'Bulk discard')
                    discarded_count += 1

                except Exception as e:
                    log.error(f"Error discarding email {email_id}: {e}")
                    errors.append(f"Email {email_id}: {str(e)}")

            conn.commit()

        response = {'discarded': discarded_count}
        if errors:
            response['errors'] = errors

        return jsonify(response), 200

    except Exception as e:
        log.error(f"Bulk discard error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
