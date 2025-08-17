"""
Database models for Screen2Deck.
Defines all database tables and relationships.
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, 
    JSON, Text, ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
import uuid
import enum
from datetime import datetime

from .database import Base

class JobStatus(enum.Enum):
    """Job status enumeration."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ExportFormat(enum.Enum):
    """Export format enumeration."""
    MTGA = "mtga"
    MOXFIELD = "moxfield"
    ARCHIDEKT = "archidekt"
    TAPPEDOUT = "tappedout"
    JSON = "json"

class User(Base):
    """User model for authentication."""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

class ApiKey(Base):
    """API key model for authentication."""
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    permissions = Column(JSON, default=["ocr:read", "ocr:write", "export:read"])
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="api_keys")

class RefreshToken(Base):
    """Refresh token model for JWT authentication."""
    __tablename__ = "refresh_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

class Job(Base):
    """OCR job model."""
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    status = Column(SQLEnum(JobStatus), default=JobStatus.QUEUED, nullable=False, index=True)
    progress = Column(Integer, default=0)
    
    # Image data
    image_hash = Column(String(64), index=True)
    image_size = Column(Integer)
    image_width = Column(Integer)
    image_height = Column(Integer)
    
    # Results
    raw_ocr = Column(JSON)
    parsed_deck = Column(JSON)
    normalized_deck = Column(JSON)
    
    # Metrics
    confidence_score = Column(Float)
    cards_detected = Column(Integer)
    processing_time_ms = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Error tracking
    error_code = Column(String(50))
    error_message = Column(Text)
    
    # Relationships
    user = relationship("User", back_populates="jobs")
    exports = relationship("Export", back_populates="job", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_job_user_status", "user_id", "status"),
        Index("idx_job_created", "created_at"),
    )

class Export(Base):
    """Export history model."""
    __tablename__ = "exports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    format = Column(SQLEnum(ExportFormat), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    job = relationship("Job", back_populates="exports")
    
    # Indexes
    __table_args__ = (
        Index("idx_export_job", "job_id"),
        Index("idx_export_format", "format"),
    )

class Card(Base):
    """Cached card data from Scryfall."""
    __tablename__ = "cards"
    
    id = Column(String(36), primary_key=True)  # Scryfall ID
    name = Column(String(255), nullable=False, index=True)
    normalized_name = Column(String(255), index=True)
    mana_cost = Column(String(50))
    type_line = Column(String(255))
    oracle_text = Column(Text)
    colors = Column(JSON)
    color_identity = Column(JSON)
    set_code = Column(String(10))
    set_name = Column(String(100))
    rarity = Column(String(20))
    image_uris = Column(JSON)
    prices = Column(JSON)
    legalities = Column(JSON)
    
    # Metadata
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index("idx_card_name", "normalized_name"),
        Index("idx_card_set", "set_code"),
    )

class AuditLog(Base):
    """Audit log for security and compliance."""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(String(255))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    request_data = Column(JSON)
    response_status = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_created", "created_at"),
    )