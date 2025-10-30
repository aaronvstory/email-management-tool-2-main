# Architecture & Code Usage Audit

Date: 2025-09-01
Scope: Entire repository at commit state during audit (branch `master`).

## Executive Summary

The project currently has **two divergent implementations** of the Email Management Tool and an **incomplete modular refactor**:

1. `simple_app.py` – Monolithic, production-facing entrypoint (README aligns with this). Uses SQLite directly (manual SQL), embeds routing, SMTP proxy, audit logging, rule logic, queue management, encryption, background threads.
2. `multi_account_app.py` – Alternate multi-account focused variant (leaner than `simple_app.py`, separate schema `data/emails.db`, overlaps feature set). Referenced only by a few ad‑hoc root test scripts (`test_email_simple.py`, etc.) via printed instructions—not imported by pytest fixtures.
3. `app/` package – Intended modular Flask application (factory + SQLAlchemy models) but **incomplete**: subpackages `web/`, `api/`, `services/`, `utils/`, `core/` are empty; factory references blueprints that do not exist; SQLAlchemy models are defined but unused by the active runtime.

Supporting folders:

- `initial/` – Generated scaffolding & bootstrap scripts (17 numbered scripts, early prototype code).
- `archive/old-tests/` – Legacy debugging/auth scripts.
- Numerous root-level maintenance / diagnostic scripts (migration, validation, interception tests, Playwright E2E).
- Duplicate test strategy: ad‑hoc `test_*.py` files at root + structured pytest suite under `tests/`.

## Active vs Legacy Classification

| Category                 | File / Folder                                                                                       | Status                        | Rationale                                                                                                                                                 |
| ------------------------ | --------------------------------------------------------------------------------------------------- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Primary runtime          | `simple_app.py`                                                                                     | ACTIVE                        | Referenced by README, pytest `conftest.py` imports symbols from it. Contains live feature set.                                                            |
| Alt runtime              | `multi_account_app.py`                                                                              | EXPERIMENTAL / PARTIAL ACTIVE | Not imported by automated tests; invoked manually per messages in root tests. Schema diverges (`emails` vs `email_messages`). Decide to merge or archive. |
| Modular app skeleton     | `app/` (except `models/`)                                                                           | UNUSED / BROKEN               | Factory references non-existent blueprints; would crash if invoked.                                                                                       |
| SQLAlchemy models        | `app/models/*.py`                                                                                   | UNUSED CURRENTLY              | Not imported by `simple_app.py`; project uses raw sqlite3 instead. Could become future ORM layer.                                                         |
| Config                   | `config/config.py`, `config.ini` (in `initial/`)                                                    | PARTIAL                       | `config/config.py` used by factory only. The monolith uses environment + constants.                                                                       |
| Migrations               | `migrate_database.py`, `migrate_accounts_schema.py`, `check_schema.py`                              | SUPPORT / ON-DEMAND           | Operate on existing SQLite schema(s). Active when evolving DB.                                                                                            |
| Diagnostics / validation | `email_diagnostics.py`, `validate_fixes.py`, `validate_interception_test.py`, `final_validation.py` | OCCASIONAL                    | Not part of runtime; safe to relocate to `tools/` or `scripts/`.                                                                                          |
| Interception & E2E tests | `playwright_interception_test.py`, `playwright_e2e_tests.py`, `email_interception_test.py`          | TEST UTILITIES                | Use Playwright; depend on monolith running. Move under `tests/e2e/`.                                                                                      |
| Root ad‑hoc tests        | `test_*.py` (root)                                                                                  | DUPLICATE / LEGACY            | Overlaps structured suite in `tests/`. Consolidate.                                                                                                       |
| Structured pytest suite  | `tests/`                                                                                            | ACTIVE                        | Organized into unit/integration/performance; relies on `simple_app`.                                                                                      |
| `initial/` scripts       | `initial/script_*.py`, `initial/web_app.py`, `initial/models.py` etc.                               | LEGACY                        | One-time generation scaffolding. Archive or remove after verification.                                                                                    |
| `archive/old-tests/`     | old debug files                                                                                     | ARCHIVABLE                    | Not referenced.                                                                                                                                           |
| Credentials & key        | `key.txt`, `email_accounts.json`                                                                    | ACTIVE DATA                   | Used by runtime(s). Keep under `data/` with git ignore policy.                                                                                            |
| Database files           | `email_manager.db`, `data/emails.db`                                                                | ACTIVE DATA                   | Different schemas; need unification plan.                                                                                                                 |

## Dependency Usage & Drift

Current `requirements.txt` includes many libraries not exercised by the active runtime (`simple_app.py`):

- Unused web/api: `Flask-RESTX`, `Flask-JWT-Extended`, `Flask-SSE` (no JWT tokens or RESTX namespaces present).
- Task queue stack: `celery`, `redis`, `flower` – no Celery app defined.
- Database tooling: `alembic`, `psycopg2-binary` – app uses SQLite directly; SQLAlchemy models unused.
- Monitoring: `sentry-sdk[flask]` – not initialized anywhere.
- Auth/security libs present but partial: `bcrypt` used indirectly via Werkzeug? (Currently `generate_password_hash` / `check_password_hash` used; explicit `bcrypt` hashing not configured.)
- Test/perf: `locust` present, no locustfile in repo.

Opportunity: **Slim a runtime requirements file** (e.g., `requirements.runtime.txt`) vs full dev (`requirements.dev.txt`).

## Data Model Divergence

| Aspect   | Monolith (`simple_app.py`)                                 | Multi-account variant                   | ORM Models (`app/models`)                    |
| -------- | ---------------------------------------------------------- | --------------------------------------- | -------------------------------------------- |
| Users    | `users` table (role text)                                  | `users` (is_admin boolean)              | `users` with roles/Role table (many-to-many) |
| Emails   | `email_messages` (rich moderation fields)                  | `emails` (simpler, with modified flags) | `email_messages` (ORM) + attachments         |
| Accounts | `email_accounts` (with health columns added via migration) | JSON file + limited DB?                 | `email_accounts` ORM model                   |
| Audit    | `audit_logs`                                               | (May log differently)                   | `audit_logs` ORM model                       |

Consolidation path: Embrace ORM layer for maintainability OR keep optimized raw SQL but unify schema (recommend migration to ORM).

## Recommended Target Structure (Phase 1 Refactor)

```
email_management_tool/
├── app/
│   ├── __init__.py              # Flask factory (completed)
│   ├── extensions.py            # login_manager, limiter, db wrapper
│   ├── config.py                # merged config
│   ├── models/                  # SQLAlchemy models (activate)
│   ├── routes/                  # Blueprint modules (split from monolith)
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── emails.py
│   │   ├── rules.py
│   │   ├── settings.py
│   ├── services/                # Business logic (email processing, scoring)
│   ├── smtp/                    # SMTP proxy + handlers
│   ├── tasks/                   # (future Celery tasks)
│   └── utils/                   # helpers (encryption, scoring, validators)
├── migrations/                  # Alembic (if adopting SQLAlchemy)
├── scripts/                     # migrate_database.py, diagnostics, validation
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/ (Playwright)
│   └── performance/
├── data/                        # *.db, accounts.json, key.txt
├── docs/                        # GITHUB guides, setup docs
├── static/
├── templates/
├── runtime.py                   # Thin entrypoint -> create_app()
├── requirements.runtime.txt
├── requirements.dev.txt
└── README.md
```

## File-Level Actions

| Action                          | Files                                                                                                     |
| ------------------------------- | --------------------------------------------------------------------------------------------------------- |
| KEEP (core runtime now)         | `simple_app.py` (until routes extracted), `playwright_*` (move later), migrations, `email_diagnostics.py` |
| EXTRACT logic then DELETE later | Large sections of `simple_app.py` (routes, DB init, SMTP proxy, rule engine)                              |
| MERGE or DROP                   | `multi_account_app.py` – fold multi-account enhancements into unified code; archive original.             |
| ACTIVATE & COMPLETE             | `app/__init__.py` + implement missing blueprints; wire SQLAlchemy; create `extensions.py`.                |
| ARCHIVE (tag release)           | `initial/` folder, `archive/old-tests/`                                                                   |
| MOVE to `scripts/`              | `validate_*`, `final_validation.py`, `migrate_*.py`, `check_schema.py`, `email_interception_test.py`      |
| CONSOLIDATE tests               | Move root `test_*.py` into structured `tests/` hierarchy or delete duplicates.                            |
| REDUCE requirements             | Split dev-only deps; remove Celery/Redis/Sentry until truly adopted.                                      |

## Suggested Refactor Phases

1. Hardening (Short) – Add a lightweight `runtime.py` that imports `simple_app.app` to decouple start scripts; freeze current behavior.
2. Blueprint Extraction – Carve route groups from `simple_app.py` into `app/routes/*.py`; move shared helpers to `app/services` or `app/utils`.
3. Database Migration – Introduce SQLAlchemy session for new tables; gradually wrap existing tables (hybrid approach) -> full ORM migration (generate Alembic revision).
4. Merge Multi-Account Features – Diff `multi_account_app.py` vs current logic; port enhancements (diagnostics, account JSON handling) into services; deprecate the alternate script.
5. Dependency Prune – Generate import graph to verify unused packages; adjust `requirements.*.txt`.
6. Final Cleanup – Archive `initial/`, remove redundant root tests, add CI pipeline executing pytest (unit + integration) and optional e2e behind flag.

## Risk & Mitigation

| Risk                                                    | Impact              | Mitigation                                                                                    |
| ------------------------------------------------------- | ------------------- | --------------------------------------------------------------------------------------------- |
| Hidden coupling inside monolith when splitting routes   | Runtime regressions | Build thorough route integration tests before extraction.                                     |
| Divergent DB schemas cause data loss on migration       | Data integrity      | Create migration plan; introspect existing SQLite schema; backup before altering.             |
| Removing unused dependencies breaks seldom-used scripts | Script failures     | Inventory which script imports what; keep dev requirements superset until scripts refactored. |
| Multi-threaded SMTP & IMAP handling changes timing      | Race conditions     | Add tests for interception flows; use dependency injection for handlers.                      |
| Security assumptions lost during rewrite                | Vulnerabilities     | Add security checklist (auth path tests, rate limiting, role enforcement).                    |

## Quick Wins (Low Effort / High Value)

- Introduce `scripts/` folder; relocate maintenance scripts (zero code change risk).
- Add `ARCHIVED/initial/` and reference in CHANGELOG, then remove from runtime path.
- Create minimal blueprints (even if they just import from monolith) to validate factory pipeline.
- Generate dependency usage report (e.g., `pipdeptree` + static import scan) to support slimming.
- Add pre-commit config enforcing formatting & lint only on active dirs (`app/`, `tests/`).

## Dependency Cleanup Matrix (Initial Pass)

| Package                                       | Keep Now?         | Reason                                                                  |
| --------------------------------------------- | ----------------- | ----------------------------------------------------------------------- |
| Flask, Flask-Login, Flask-Limiter, Flask-Cors | YES               | Actively planned / partial use.                                         |
| Flask-RESTX, Flask-JWT-Extended, Flask-SSE    | LATER / REMOVE    | Not in code; re-add when implementing API or SSE.                       |
| SQLAlchemy, alembic                           | YES (future)      | Needed for modular refactor.                                            |
| psycopg2-binary                               | REMOVE (optional) | Only needed if migrating to Postgres; currently SQLite.                 |
| aiosmtpd, cryptography                        | YES               | SMTP proxy & credential encryption.                                     |
| celery, redis, flower                         | DEFER             | No Celery app defined.                                                  |
| sentry-sdk[flask]                             | DEFER             | Not initialized.                                                        |
| Locust                                        | DEFER/REMOVE      | No load scripts present.                                                |
| python-magic, beautifulsoup4, bleach          | VERIFY            | If not yet sanitizing HTML attachments, may be future; keep if planned. |

## Metrics to Track Post-Refactor

- Startup time (baseline now vs after modularization)
- Memory footprint (psutil RSS) after N emails processed
- Route latency p95 under synthetic load
- DB query count per request (after ORM adoption)
- Test coverage (target >60% initially, then 80%+)

## Next Actions Checklist

- [ ] Create `scripts/` and move maintenance/diagnostic scripts
- [ ] Add `runtime.py` entrypoint using factory (or transitional wrapper)
- [ ] Implement placeholder blueprints to satisfy factory imports
- [ ] Extract first route group (authentication) from monolith
- [ ] Start ORM parity table for `users` + automated migration
- [ ] Decide canonical DB file (`data/email_management.db`), add migration script to consolidate
- [ ] Prune obvious unused dependencies into separate dev file

## Archive Recommendations

Archive (Git tag `pre-modularization`) then move:

- Entire `initial/` directory
- `archive/old-tests/`
- Root redundant `test_*.py` files (after merging relevant logic into `tests/` suite)

Retain in repo but relocated to `scripts/`:

- `migrate_database.py`, `migrate_accounts_schema.py`, `check_schema.py`
- `validate_*`, `final_validation.py`, `email_diagnostics.py`, `email_interception_test.py`
- `playwright_*` -> `tests/e2e/`

---

Prepared as part of repository hygiene and modernization effort.
