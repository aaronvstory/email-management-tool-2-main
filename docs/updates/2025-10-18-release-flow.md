# Release Flow Hardening – 2025-10-18

## Summary
- Added shared headers (`X-EMT-Release-Bypass`, `X-EMT-Email-ID`) to every outbound release so IMAP watchers can reliably detect edited deliveries and skip re-quarantining them.
- Taught the IMAP watcher to ignore any message stamped with the bypass header and to prune the associated UID from subsequent sweeps, preventing duplicate holds across all configured accounts.
- Hardened the quarantine cleanup step so UID searches capture string values consistently and expunge succeeds even when servers return byte arrays.
- Standardised the /email/<id> viewer with the same **Edit & Release** workflow used by the unified queue, including a combined “Save & Release” control and an explicit “Quick Release” action.

## Operator Notes
1. Restart the dashboard/worker services after deploying so each watcher loads the new header logic.
2. When reviewing a held message:
   - Use **Edit & Release** to update content and deliver in one step, or **Edit** to save drafts without releasing.
   - **Quick Release** delivers the captured message unchanged (no modal).
3. The release modal now always sends edited content (subject/body) along with the target folder, ensuring Gmail/Hostinger both receive the cleaned message and that the original quarantine copy is expunged.

## Validation Checklist
- Intercept a test email, edit in the modal, choose **Save & Release**, and confirm:
  - The edited message lands in the account inbox.
  - Quarantine no longer contains the original UID.
  - The UI reflects status `RELEASED`.
- From `/dashboard` and `/emails-unified`, confirm the same modal and buttons appear and function identically.
- Inspect IMAP logs (`app/services/imap_watcher`) for `Skipping released email` entries to verify bypass headers are honoured.
