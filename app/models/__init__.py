"""
Database models for Email Management Tool

NOTE: SQLAlchemy models are NOT used by the application.
The app uses direct SQLite connections via app.utils.db.
These models are kept for future migration but should NOT be imported at runtime.
"""

# Only export SimpleUser which is actually used
from .simple_user import SimpleUser

__all__ = [
    'SimpleUser',
]

# SQLAlchemy models kept for reference but not imported to avoid version conflicts
# from .base import db, Base
# from .user import User, Role
# from .email import EmailMessage, EmailAttachment
# from .rule import ModerationRule, RuleType, RuleAction
# from .account import EmailAccount
# from .audit import AuditLog