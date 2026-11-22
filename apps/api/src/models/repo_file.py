import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from src.database import Base

if TYPE_CHECKING:
    from src.models.snapshot import Snapshot
    from src.models.symbol import Symbol
    from src.models.import_statement import FileImport
    from src.models.code_chunk import CodeChunk


class RepoFile(Base):
    __tablename__ = "repo_files"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        index=True
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )
    extension: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    size_bytes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    line_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
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
        UniqueConstraint("snapshot_id", "path", name="uq_repo_file_snapshot_path"),
    )

    # Relationships
    snapshot: Mapped["Snapshot"] = relationship("Snapshot", back_populates="files")
    symbols: Mapped[List["Symbol"]] = relationship(
        "Symbol",
        back_populates="file",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    imports: Mapped[List["FileImport"]] = relationship(
        "FileImport",
        back_populates="file",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    code_chunks: Mapped[List["CodeChunk"]] = relationship(
        "CodeChunk",
        back_populates="file",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
