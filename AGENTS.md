# Repository Guidelines

## Project Structure & Module Organization
Core Flask code lives in `app/` (`routes/` for HTTP controllers, `services/` for moderation logic, `utils/` for shared helpers, `workers/` for background jobs). Configuration stays in `config/config.ini` and should be overridden via per-host `.env`. UI assets live in `templates/` and `static/` (custom Stitch styling in `static/css/stitch.components.css`); backups, data dumps, and logs sit in `backups/`, `data/`, and `logs/`. Root batch and PowerShell launchers handle day-to-day tasks, while reusable tooling resides under `scripts/`.

## Build, Test, and Development Commands
- `pip install -r requirements-dev.txt` provisions the virtualenv with linters, type checkers, and pytest extras.
- `.\manage.ps1 start` (or `start.bat`) boots the SMTP proxy and dashboard; `.\manage.ps1 logs` tails runtime output.
- `python -m pytest` executes backend tests; add `--cov=app --cov-report=term-missing` to review coverage.
- `npm run lint` enforces JS/CSS quality; `npm run format:check` validates template formatting before commit.

## Coding Style & Naming Conventions
Format Python with Black (4-space indent) and keep modules `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`. Ensure touched modules pass `pylint` and `mypy`; favour dependency injection in `services/` and keep side effects inside `workers/`. Front-end code follows ESLint + Prettier defaults (2-space indent, single quotes) and Stylelint rules; organise new assets under `static/js/<feature>/` and `static/css/<feature>/`. Template fragments belong in `templates/partials/` with feature-prefixed filenames such as `moderation_header.html`.

## Testing Guidelines
Pytest with pytest-flask and pytest-asyncio powers suites in `tests/`; mirror application structure when naming files (e.g., `tests/services/test_rules.py`). Use descriptive fixtures (`moderation_queue`, `sample_message_html`) and mark async cases with `pytest.mark.asyncio`. Maintain current coverage (>=85% on moderation workflows) and refresh canonical payloads in `data/inbound_raw/` when behaviour changes. Run `scripts/test_interception_flow.sh` for end-to-end smoke checks inside WSL-enabled shells.

## Commit & Pull Request Guidelines
Follow the conventional commit format observed in history (`feat(ui): ...`, `fix(core): ...`, `chore(docs): ...`). Keep commits focused on a single concern and add short bullet points in the body when context helps reviewers. PRs should reference issues, summarise behaviour changes, list test commands run, and attach before/after screenshots for UI tweaks. Request at least one maintainer review and wait for CI to pass before merging.

## Security & Configuration Tips
Never commit `key.txt`, `.env`, or SQLite artifacts (`email_manager.db*`, `data/emails.db`); confirm `.gitignore` coverage before pushing. Rotate the Fernet key by removing your local `key.txt` and rerunning `setup.bat` or `manage.ps1 config` so the provisioning scripts regenerate secrets. Store SMTP credentials in Windows Credential Manager or another vault, not in tracked config files.
