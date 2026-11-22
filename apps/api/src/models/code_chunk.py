import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from src.database import Base

if TYPE_CHECKING:
    from src.models.repo_file import RepoFile
    from src.models.symbol import Symbol


class CodeChunk(Base):
    __tablename__ = "code_chunks"

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
    symbol_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("symbols.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    chunk_type: Mapped[str] = mapped_column(
        String(64),
        default="CODE",
        nullable=False
    )  # FUNCTION, CLASS, METHOD, MODULE, BLOCK
    start_line: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    end_line: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    file: Mapped["RepoFile"] = relationship("RepoFile", back_populates="code_chunks")
    symbol: Mapped[Optional["Symbol"]] = relationship("Symbol", back_populates="code_chunks")
