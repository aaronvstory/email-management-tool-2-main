# Changelog

All notable changes to the Email Management Tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Account Management UI & API Improvements (2025-10-31)

#### UI Enhancements
- **Visible Buttons on Dark Theme** - All account action buttons now have proper contrast (`static/css/unified.css:5646-5694`)
  - `.btn-account` styling with visible borders and dark background (#27272a)
  - Responsive `.account-actions-row` for graceful button wrapping on small screens
  - Flexible toolbars (`.header-actions`, `.command-actions`, `.action-bar`)

- **Improved Compose Textarea** - Increased height to 16rem (256px) for better usability (`static/css/unified.css`)

- **Reset Circuit Button** - New UI control to clear error states and retry failed accounts
  - Added to both card view and table view in `templates/partials/account_components.html`
  - Icon: `bi-arrow-clockwise`
  - Tooltip: "Reset circuit breaker and clear error states"

#### API Endpoints
- **Circuit Reset API** - `POST /api/accounts/<int:account_id>/circuit/reset` (`app/routes/accounts.py:255-280`)
  - Clears `last_error`, `connection_status` fields
  - Resets `smtp_health_status` and `imap_health_status` to 'unknown'
  - Enables retry after circuit breaker trips
  - Returns: `{ok: true/false, success: true/false, error: "..."}`

- **Credentials Update API** - `POST /api/accounts/<int:account_id>/credentials` (`app/routes/accounts.py:208-252`)
  - Update IMAP/SMTP usernames and passwords
  - Encrypts credentials before storing
  - Validates required fields
  - Returns: `{ok: true/false, success: true/false, error: "..."}`

#### JavaScript Improvements
- **Safe JSON Fetching** - New `jsonFetch()` helper in `templates/accounts.html:48-64`
  - Consistent error handling across all API calls
  - Clear user feedback via toast notifications
  - No more silent failures

- **Refactored Functions** - Updated to use `jsonFetch()`:
  - `startWatcher()` - Cleaner async/await pattern (lines 116-128)
  - `stopWatcher()` - Cleaner async/await pattern (lines 130-142)
  - `deleteAccount()` - Simplified from 30 to 13 lines (lines 161-173)
  - **NEW**: `resetCircuit()` - Circuit breaker reset (lines 144-155)

- **Bootstrap Safety** - `initializeTooltips()` guard prevents errors when Bootstrap isn't loaded (`templates/accounts.html:309-322`)

#### Database
- **Health Monitoring Columns** - Confirmed existing in `email_accounts` table:
  - `smtp_health_status` TEXT
  - `imap_health_status` TEXT
  - `connection_status` TEXT
  - `last_health_check` TEXT
  - `last_successful_connection` TEXT

#### Documentation
- **Updated README.md** - Added "How to Run Locally" and "Basic Test Checklist" sections
- **Task Progress** - Comprehensive verification results in `.taskmaster/TASK_PROGRESS.md`
- **Screenshots** - 7 screenshots documenting UI verification and workflows

### Fixed
- Zero console errors on `/accounts` page (only expected Bootstrap warning)
- Buttons now wrap gracefully on narrow screens (no crowding)
- Consistent JSON error responses for all `/api/*` routes

### Testing
- ✅ Account 1 workflow: Reset Circuit → Test → Start
- ✅ Account 2 workflow: Stop → Start → Test
- ✅ All API endpoints return proper JSON responses
- ✅ UI responsive behavior verified across multiple pages
- ✅ Screenshot documentation for all verification steps

### Known Limitations
- Attachment download shows "disabled" message (existing limitation, not part of this release)
- Bootstrap tooltip warning is expected and gracefully handled

---

## Previous Releases

See git commit history for changes prior to this changelog's introduction.
