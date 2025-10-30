"""
Email message and attachment models
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer, LargeBinary, JSON, Enum
from sqlalchemy.orm import relationship
import enum
from .base import Base, TimestampMixin, UUIDMixin

class EmailStatus(enum.Enum):
    """Email status enumeration"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    FAILED = "failed"
    QUARANTINED = "quarantined"

class EmailPriority(enum.Enum):
    """Email priority enumeration"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class EmailMessage(Base, UUIDMixin, TimestampMixin):
    """Email message model"""
    __tablename__ = 'email_messages'
    
    # Email headers
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    sender = Column(String(255), nullable=False, index=True)
    recipients = Column(JSON, nullable=False)  # List of recipients
    cc = Column(JSON)  # List of CC recipients
    bcc = Column(JSON)  # List of BCC recipients
    subject = Column(String(500))
    
    # Email content
    raw_content = Column(LargeBinary)  # Original raw email
    processed_content = Column(LargeBinary)  # Modified email after review
    body_text = Column(Text)  # Plain text body
    body_html = Column(Text)  # HTML body
    headers = Column(JSON)  # All email headers as JSON
    
    # Moderation
    status = Column(Enum(EmailStatus), default=EmailStatus.PENDING, nullable=False, index=True)
    priority = Column(Enum(EmailPriority), default=EmailPriority.NORMAL, nullable=False)
    keywords_matched = Column(JSON)  # List of matched keywords
    rules_matched = Column(JSON)  # List of matched rule IDs
    risk_score = Column(Integer, default=0)  # Risk assessment score
    
    # Review information
    reviewer_id = Column(String(36), ForeignKey('users.id'))
    reviewed_at = Column(DateTime)
    review_notes = Column(Text)
    modifications = Column(JSON)  # Track what was modified
    
    # Delivery information
    sent_at = Column(DateTime)
    delivery_attempts = Column(Integer, default=0)
    last_error = Column(Text)
    
    # Metadata
    size = Column(Integer)  # Email size in bytes
    has_attachments = Column(Boolean, default=False)
    attachment_count = Column(Integer, default=0)
    from_internal = Column(Boolean, default=True)  # Internal vs external sender
    contains_pii = Column(Boolean, default=False)  # Personal Identifiable Information flag
    
    # Relationships
    attachments = relationship('EmailAttachment', back_populates='email', cascade='all, delete-orphan', lazy='joined')
    reviewer = relationship('User', back_populates='reviewed_emails')
    audit_logs = relationship('AuditLog', back_populates='email', lazy='dynamic')
    
    @property
    def recipient_list(self):
        """Get formatted recipient list"""
        if isinstance(self.recipients, list):
            return ', '.join(self.recipients)
        return self.recipients
    
    @property
    def is_high_risk(self):
        """Check if email is high risk"""
        return self.risk_score >= 70
    
    @property
    def is_external(self):
        """Check if email is to external recipients"""
        return not self.from_internal
    
    @property
    def age_hours(self):
        """Get age of email in hours"""
        if self.created_at:
            delta = datetime.now(timezone.utc) - self.created_at
            return delta.total_seconds() / 3600
        return 0
    
    def __repr__(self):
        return f'<EmailMessage {self.message_id} - {self.status.value}>'


class EmailAttachment(Base, UUIDMixin, TimestampMixin):
    """Email attachment model"""
    __tablename__ = 'email_attachments'
    
    # Reference to email
    email_id = Column(String(36), ForeignKey('email_messages.id'), nullable=False)
    
    # Attachment information
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100))
    size = Column(Integer)  # Size in bytes
    content = Column(LargeBinary)  # Actual attachment content
    
    # Security scanning
    is_safe = Column(Boolean, default=None)  # None = not scanned, True = safe, False = malicious
    scan_results = Column(JSON)  # Virus/malware scan results
    file_hash = Column(String(64))  # SHA256 hash of content
    
    # Relationships
    email = relationship('EmailMessage', back_populates='attachments')
    
    @property
    def size_mb(self):
        """Get size in megabytes"""
        if self.size:
            return round(self.size / (1024 * 1024), 2)
        return 0
    
    @property
    def is_document(self):
        """Check if attachment is a document"""
        doc_types = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt']
        return any(self.filename.lower().endswith(ext) for ext in doc_types)
    
    @property
    def is_image(self):
        """Check if attachment is an image"""
        img_types = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg']
        return any(self.filename.lower().endswith(ext) for ext in img_types)
    
    def __repr__(self):
        return f'<EmailAttachment {self.filename} ({self.size_mb}MB)>'