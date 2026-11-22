import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from src.database import Base

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.repository_permission import RepositoryPermission
    from src.models.repository_import import RepositoryImport
    from src.models.job import Job
    from src.models.snapshot import Snapshot


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        default="github",
        nullable=False
    )
    provider_repo_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True
    )
    owner: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )
    canonical_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False
    )
    visibility: Mapped[str] = mapped_column(
        String(32),
        default="PUBLIC",
        nullable=False
    )
    default_branch: Mapped[str] = mapped_column(
        String(255),
        default="main",
        nullable=False
    )
    tracked_branch: Mapped[str] = mapped_column(
        String(255),
        default="main",
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True
    )
    stargazers_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    forks_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    open_issues_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    size_kb: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="ACTIVE",
        nullable=False
    )
    analysis_status: Mapped[str] = mapped_column(
        String(32),
        default="NOT_ANALYZED",
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
        UniqueConstraint("owner_user_id", "provider", "provider_repo_id", name="uq_user_provider_repo"),
    )

    # Relationships
    owner_user: Mapped["User"] = relationship("User", back_populates="repositories")
    permissions: Mapped[List["RepositoryPermission"]] = relationship(
        "RepositoryPermission",
        back_populates="repository",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    imports: Mapped[List["RepositoryImport"]] = relationship(
        "RepositoryImport",
        back_populates="repository",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    jobs: Mapped[List["Job"]] = relationship(
        "Job",
        back_populates="repository",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    snapshots: Mapped[List["Snapshot"]] = relationship(
        "Snapshot",
        back_populates="repository",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
