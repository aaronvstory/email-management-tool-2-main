"""
Common header names used to coordinate interception and release workflows.
"""

# Header injected on released emails so IMAP watchers can skip re-quarantining
RELEASE_BYPASS_HEADER = "X-EMT-Release-Bypass"

# Header carrying the email_messages table primary key for downstream reconciliation
RELEASE_EMAIL_ID_HEADER = "X-EMT-Email-ID"

