"""
Base model and database configuration
"""
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import Column, DateTime, String
import uuid

# Create declarative base
Base = declarative_base()

class TimestampMixin:
    """Mixin for adding timestamp fields"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class UUIDMixin:
    """Mixin for UUID primary key"""
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

# Database session management
class Database:
    def __init__(self, database_url):
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=self.engine))
        
    def create_all(self):
        """Create all tables"""
        Base.metadata.create_all(bind=self.engine)
        
    def drop_all(self):
        """Drop all tables"""
        Base.metadata.drop_all(bind=self.engine)
        
    def get_session(self):
        """Get a new database session"""
        return self.SessionLocal()

# Global database instance (initialized in app)
db = None