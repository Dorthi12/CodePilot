import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from src.database import Base

if TYPE_CHECKING:
    from src.models.repo_file import RepoFile
    from src.models.code_chunk import CodeChunk


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repo_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )
    qualified_name: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        index=True
    )
    kind: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True
    )  # FUNCTION, CLASS, METHOD, INTERFACE, VARIABLE
    scope: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    start_line: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    end_line: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    start_column: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    end_column: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    signature: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    docstring: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    file: Mapped["RepoFile"] = relationship("RepoFile", back_populates="symbols")
    code_chunks: Mapped[List["CodeChunk"]] = relationship(
        "CodeChunk",
        back_populates="symbol"
    )
