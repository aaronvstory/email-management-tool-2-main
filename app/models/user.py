"""
User and Role models for authentication and authorization
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table, Enum, Integer
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import enum
from .base import Base, TimestampMixin, UUIDMixin

# Association table for many-to-many relationship between users and roles
user_roles = Table('user_roles', Base.metadata,
    Column('user_id', String(36), ForeignKey('users.id'), primary_key=True),
    Column('role_id', String(36), ForeignKey('roles.id'), primary_key=True)
)

class RoleEnum(enum.Enum):
    """User role enumeration"""
    ADMIN = "admin"
    REVIEWER = "reviewer"
    VIEWER = "viewer"

class User(Base, UUIDMixin, TimestampMixin, UserMixin):
    """User model for authentication"""
    __tablename__ = 'users'
    
    # Basic information
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Profile
    first_name = Column(String(80))
    last_name = Column(String(80))
    department = Column(String(100))
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Security
    last_login = Column(DateTime)
    last_password_change = Column(DateTime, default=datetime.utcnow)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)
    
    # Two-factor authentication
    totp_secret = Column(String(32))
    totp_enabled = Column(Boolean, default=False)
    
    # Relationships
    roles = relationship('Role', secondary=user_roles, back_populates='users', lazy='joined')
    audit_logs = relationship('AuditLog', back_populates='user', lazy='dynamic')
    reviewed_emails = relationship('EmailMessage', back_populates='reviewer', lazy='dynamic')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
        self.last_password_change = datetime.now(timezone.utc)
        
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def has_role(self, role_name):
        """Check if user has a specific role"""
        return any(role.name == role_name for role in self.roles)
    
    def can_review(self):
        """Check if user can review emails"""
        return self.has_role(RoleEnum.REVIEWER.value) or self.has_role(RoleEnum.ADMIN.value)
    
    def can_admin(self):
        """Check if user has admin privileges"""
        return self.has_role(RoleEnum.ADMIN.value)
    
    @property
    def full_name(self):
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def __repr__(self):
        return f'<User {self.username}>'


class Role(Base, UUIDMixin, TimestampMixin):
    """Role model for authorization"""
    __tablename__ = 'roles'
    
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    
    # Relationships
    users = relationship('User', secondary=user_roles, back_populates='roles')
    
    def __repr__(self):
        return f'<Role {self.name}>'