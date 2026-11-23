"""SQLAlchemy models for Mastermind Feature 5 (Unit Test Generation).

Specifications:
- Master Architecture Specification v2.1 §6.6, §10 (M5)
- API and Data Specification v1.0 §4.6
"""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class TestArtifactModel(Base):
    """SQLAlchemy model for generated test artifacts."""
    __tablename__ = "test_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    snapshot_id = Column(String(255), nullable=False, index=True)
    analysis_run_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    file_path = Column(String(1024), nullable=False, index=True)
    content = Column(Text, nullable=False)
    framework = Column(String(50), nullable=False, default="pytest")
    validation_status = Column(String(50), nullable=False, default="PENDING")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class TestRunModel(Base):
    """SQLAlchemy model for isolated sandbox test executions."""
    __tablename__ = "test_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    run_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    sandbox_image = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="PENDING", index=True)
    profile = Column(String(10), default="S1")
    network_mode = Column(String(20), nullable=False, default="none")
    risk_level = Column(String(50), nullable=False, default="STANDARD")
    limits = Column(JSONB, nullable=False, default=dict)
    command = Column(Text, nullable=False, default="pytest -v")
    exit_code = Column(Integer)
    stdout_redacted = Column(Text)
    stderr_redacted = Column(Text)
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime(timezone=True))
    duration_ms = Column(Float, default=0.0)

    results = relationship("TestResultModel", back_populates="test_run", cascade="all, delete-orphan")
    coverage = relationship("CoverageReportModel", back_populates="test_run", uselist=False, cascade="all, delete-orphan")


class TestResultModel(Base):
    """SQLAlchemy model for individual test case results."""
    __tablename__ = "test_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    test_run_id = Column(UUID(as_uuid=True), ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_name = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False, default="PASSED", index=True)
    duration_ms = Column(Float, default=0.0)
    failure_ref = Column(Text)
    failure_message = Column(Text)
    failure_trace_redacted = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    test_run = relationship("TestRunModel", back_populates="results")


class CoverageReportModel(Base):
    """SQLAlchemy model for coverage reports."""
    __tablename__ = "coverage_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    test_run_id = Column(UUID(as_uuid=True), ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    tool = Column(String(100), nullable=False, default="pytest-cov")
    target_file = Column(String(1024), nullable=False)
    before = Column(JSONB, nullable=False, default=dict)
    after = Column(JSONB, nullable=False, default=dict)
    delta = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    test_run = relationship("TestRunModel", back_populates="coverage")
