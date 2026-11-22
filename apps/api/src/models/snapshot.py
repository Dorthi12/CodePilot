import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from src.database import Base

if TYPE_CHECKING:
    from src.models.repository import Repository
    from src.models.repo_file import RepoFile


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    commit_sha: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True
    )
    branch: Mapped[str] = mapped_column(
        String(255),
        default="main",
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        nullable=False,
        index=True
    )
    total_files: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    total_lines: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint("repository_id", "commit_sha", name="uq_snapshot_repo_commit"),
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="snapshots")
    files: Mapped[List["RepoFile"]] = relationship(
        "RepoFile",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
