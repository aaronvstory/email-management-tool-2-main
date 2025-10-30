"""
IMAP utility functions for folder normalization and validation.
"""

VALID_FOLDERS = {"INBOX", "Drafts", "Sent", "Trash", "Junk", "Archive", "Quarantine"}


def normalize_folder(name: str) -> str:
    """
    Normalize IMAP folder names to prevent 'Incorrect label names' errors in strict mocks.

    Args:
        name: Raw folder name from user input or configuration

    Returns:
        Normalized folder name that's valid for IMAP operations

    Examples:
        >>> normalize_folder("inbox")
        'INBOX'
        >>> normalize_folder('"Inbox"')
        'INBOX'
        >>> normalize_folder("Spam")
        'Junk'
        >>> normalize_folder("")
        'INBOX'
    """
    if not name:
        return "INBOX"

    # Strip quotes, backslashes, and whitespace
    n = name.strip().strip('"').replace("\\", "").replace("//", "/")

    # Map common variants to standard names
    aliases = {
        "Inbox": "INBOX",
        "inbox": "INBOX",
        "Spam": "Junk",
    }
    n = aliases.get(n, n)

    # Return normalized name if valid, otherwise default to INBOX
    return n if n in VALID_FOLDERS else "INBOX"
