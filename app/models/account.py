"""
Email account model for IMAP/SMTP configuration
"""
from sqlalchemy import Column, String, Boolean, Integer, JSON, DateTime
from cryptography.fernet import Fernet
import os
from .base import Base, TimestampMixin, UUIDMixin

class EmailAccount(Base, UUIDMixin, TimestampMixin):
    """Email account configuration model"""
    __tablename__ = 'email_accounts'
    
    # Account information
    name = Column(String(100), nullable=False, unique=True)
    email_address = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(String(500))
    
    # SMTP configuration
    smtp_host = Column(String(255), nullable=False)
    smtp_port = Column(Integer, default=587)
    smtp_use_tls = Column(Boolean, default=True)
    smtp_use_ssl = Column(Boolean, default=False)
    smtp_username = Column(String(255))
    smtp_password_encrypted = Column(String(500))  # Encrypted password
    
    # IMAP configuration (for reading emails)
    imap_host = Column(String(255))
    imap_port = Column(Integer, default=993)
    imap_use_ssl = Column(Boolean, default=True)
    imap_username = Column(String(255))
    imap_password_encrypted = Column(String(500))  # Encrypted password
    imap_folder = Column(String(100), default='INBOX')
    
    # Account settings
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False)
    max_send_per_hour = Column(Integer, default=100)
    max_send_per_day = Column(Integer, default=1000)
    
    # Statistics
    emails_sent = Column(Integer, default=0)
    emails_received = Column(Integer, default=0)
    last_sync = Column(DateTime)
    last_error = Column(String(500))
    
    # Metadata
    tags = Column(JSON)
    custom_headers = Column(JSON)  # Custom headers to add to emails
    
    # Encryption key (should be stored securely in production)
    _encryption_key = os.environ.get('ENCRYPTION_KEY', Fernet.generate_key())
    _cipher = Fernet(_encryption_key if isinstance(_encryption_key, bytes) else _encryption_key.encode())
    
    def set_smtp_password(self, password):
        """Encrypt and store SMTP password"""
        if password:
            self.smtp_password_encrypted = self._cipher.encrypt(password.encode()).decode()
    
    def get_smtp_password(self):
        """Decrypt and return SMTP password"""
        if self.smtp_password_encrypted:
            return self._cipher.decrypt(self.smtp_password_encrypted.encode()).decode()
        return None
    
    def set_imap_password(self, password):
        """Encrypt and store IMAP password"""
        if password:
            self.imap_password_encrypted = self._cipher.encrypt(password.encode()).decode()
    
    def get_imap_password(self):
        """Decrypt and return IMAP password"""
        if self.imap_password_encrypted:
            return self._cipher.decrypt(self.imap_password_encrypted.encode()).decode()
        return None
    
    def __repr__(self):
        return f'<EmailAccount {self.name} - {self.email_address}>'