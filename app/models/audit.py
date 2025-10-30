"""
Audit log model for tracking all system actions
"""
from sqlalchemy import Column, String, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin, UUIDMixin

class AuditLog(Base, UUIDMixin, TimestampMixin):
    """Audit log model for tracking all actions"""
    __tablename__ = 'audit_logs'
    
    # Action information
    action = Column(String(100), nullable=False, index=True)
    action_type = Column(String(50), index=True)  # CREATE, UPDATE, DELETE, VIEW, APPROVE, REJECT, etc.
    resource_type = Column(String(50), index=True)  # email, rule, user, account, etc.
    resource_id = Column(String(36), index=True)  # ID of the resource affected
    
    # User information
    user_id = Column(String(36), ForeignKey('users.id'))
    user_name = Column(String(100))  # Denormalized for historical record
    user_role = Column(String(50))  # Role at time of action
    ip_address = Column(String(45))  # IPv4 or IPv6 address
    user_agent = Column(String(500))  # Browser/client information
    
    # Email specific (if action relates to an email)
    email_id = Column(String(36), ForeignKey('email_messages.id'))
    email_subject = Column(String(500))  # Denormalized for quick reference
    
    # Details
    details = Column(Text)  # Human-readable description
    changes = Column(JSON)  # JSON object showing what changed (before/after)
    metadata = Column(JSON)  # Additional context information
    
    # Status
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    
    # Relationships
    user = relationship('User', back_populates='audit_logs')
    email = relationship('EmailMessage', back_populates='audit_logs')
    
    @property
    def is_sensitive_action(self):
        """Check if this is a sensitive action"""
        sensitive_actions = ['DELETE', 'APPROVE', 'REJECT', 'MODIFY_RULE', 'CREATE_USER', 'DELETE_USER']
        return self.action_type in sensitive_actions
    
    @property
    def is_error(self):
        """Check if this action resulted in an error"""
        return not self.success
    
    def __repr__(self):
        return f'<AuditLog {self.action} by {self.user_name} at {self.created_at}>'