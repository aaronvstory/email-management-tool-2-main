# Repository Guidelines

## Project Structure & Module Organization
The Flask app lives in `app/`: persistence models in `models/`, HTTP surfaces in `routes/`, service logic in `services/`, and background jobs in `workers/` and `utils/`. `simple_app.py` wires everything together and is the entry for new endpoints or schedulers. Config defaults stay in `config/`; runtime assets split between `templates/` and `static/`. SQLite artifacts (`email_manager.db*`) sit in the repo root with logs under `logs/`. References are curated in `docs/`, while `archive/` preserves snapshots and the quarantined test tree.

## Build, Test, and Development Commands
- `python -m venv .venv; .\\.venv\\Scripts\\Activate.ps1; pip install -r requirements.txt` — bootstrap dependencies.
- `pwsh .\\manage.ps1 start` — run SMTP proxy plus dashboard; stop via `Ctrl+C` or `pwsh .\\manage.ps1 stop`.
- `python simple_app.py` — dev loop with auto-reload.
- `python cleanup_and_start.py` — clear stuck ports and restart services.
- `black .`, `pylint app simple_app.py`, `mypy app` — quality gates before opening a PR.

## Coding Style & Naming Conventions
Use 4-space indentation, type hints on new Python, and `snake_case` for modules, functions, and Jinja macros. Parameterize SQL and route database work through helpers in `app/services/` where possible. Reuse Bootstrap 5 patterns already defined in `templates/` and utility classes from `static/css/`; defer to `docs/STYLEGUIDE.md` for color, spacing, and motion guidance. Shared JavaScript belongs in the existing bundles—avoid inline scripts unless scoped to a single template.

## Testing Guidelines
Until the migration finishes, automated suites live in `archive/ui_cleanup_2025-10-13/tests/`. Use `pytest archive/ui_cleanup_2025-10-13/tests/interception -q` for core moderation flows, or `pytest archive/ui_cleanup_2025-10-13/tests/test_intercept_flow.py -vv` when iterating. Mirror runtime package names when adding coverage and update `TEST_ISOLATION_STATUS.md` if you quarantine or revive cases. Capture one happy-path interception check and call out manual dashboard or SMTP validation in your PR notes.

## Commit & Pull Request Guidelines
Stay with the Conventional Commit pattern seen in history (`feat(ui): ...`, `refactor(workers): ...`) and limit scopes to real directories. PRs must show test output, reference the driving issue, and attach screenshots or HAR captures when UI or API surfaces change. Keep changesets tight—separate styling from backend logic—and call out migrations explicitly. Request maintainer review before merging to `main`.

## Security & Configuration Tips
Keep secrets out of version control—confirm `.gitignore` covers `.env`, `email_manager.db*`, and any export paths you add. Rotate SMTP credentials through `config/email_accounts.json` and `.env`, then run `pwsh .\\setup_security.ps1` to confirm ACLs. Gate telemetry via environment variables and sanity-check using `python scripts/live_check.py --safety` before promoting a build.
