"""
Moderation rule models
"""
from sqlalchemy import Column, String, Text, Boolean, Integer, JSON, Enum, DateTime
from sqlalchemy.orm import relationship
import enum
from .base import Base, TimestampMixin, UUIDMixin

class RuleType(enum.Enum):
    """Rule type enumeration"""
    KEYWORD = "keyword"
    SENDER = "sender"
    RECIPIENT = "recipient"
    ATTACHMENT = "attachment"
    SIZE = "size"
    REGEX = "regex"
    DOMAIN = "domain"
    CONTENT = "content"

class RuleAction(enum.Enum):
    """Rule action enumeration"""
    HOLD = "hold"
    APPROVE = "approve"
    REJECT = "reject"
    QUARANTINE = "quarantine"
    FLAG = "flag"

class ModerationRule(Base, UUIDMixin, TimestampMixin):
    """Email moderation rule model"""
    __tablename__ = 'moderation_rules'
    
    # Rule definition
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    rule_type = Column(Enum(RuleType), nullable=False, index=True)
    pattern = Column(Text, nullable=False)  # Pattern to match (keyword, regex, etc.)
    
    # Rule configuration
    action = Column(Enum(RuleAction), default=RuleAction.HOLD, nullable=False)
    priority = Column(Integer, default=50, nullable=False)  # 0-100, higher = more priority
    risk_score = Column(Integer, default=50)  # Risk points to add when matched
    
    # Rule conditions
    case_sensitive = Column(Boolean, default=False)
    whole_word = Column(Boolean, default=False)
    check_subject = Column(Boolean, default=True)
    check_body = Column(Boolean, default=True)
    check_attachments = Column(Boolean, default=False)
    check_headers = Column(Boolean, default=False)
    
    # Rule scope
    apply_to_internal = Column(Boolean, default=True)
    apply_to_external = Column(Boolean, default=True)
    sender_whitelist = Column(JSON)  # List of whitelisted senders
    sender_blacklist = Column(JSON)  # List of blacklisted senders
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    hit_count = Column(Integer, default=0)  # Number of times rule has been triggered
    last_hit = Column(DateTime)  # Last time rule was triggered
    
    # Metadata
    tags = Column(JSON)  # Tags for categorization
    notes = Column(Text)  # Admin notes
    
    @property
    def is_high_priority(self):
        """Check if rule is high priority"""
        return self.priority >= 80
    
    @property
    def effectiveness_rate(self):
        """Calculate rule effectiveness"""
        # This could be calculated based on false positives vs true positives
        return 0.0  # Placeholder
    
    def matches(self, email_content):
        """Check if rule matches email content"""
        # This would implement the actual matching logic
        # Based on rule_type and pattern
        return False  # Placeholder
    
    def __repr__(self):
        return f'<ModerationRule {self.name} - {self.rule_type.value}>'