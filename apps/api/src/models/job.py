import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, BigInteger, Float, Boolean, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from src.database import Base

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.repository import Repository


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    job_type: Mapped[str] = mapped_column(
        String(32),
        default="CLONE",
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="QUEUED",
        nullable=False,
        index=True
    )
    stage: Mapped[str] = mapped_column(
        String(32),
        default="VALIDATING",
        nullable=False
    )
    retrieval_method: Mapped[str] = mapped_column(
        String(32),
        default="GIT_CLONE",
        nullable=False
    )
    progress: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    progress_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    branch: Mapped[str] = mapped_column(
        String(255),
        default="main",
        nullable=False
    )
    commit_sha: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    bytes_downloaded: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False
    )
    total_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True
    )
    files_discovered: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    files_processed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    files_skipped: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    files_failed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    retryable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    workspace_path: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="jobs")
    repository: Mapped["Repository"] = relationship("Repository", back_populates="jobs")
