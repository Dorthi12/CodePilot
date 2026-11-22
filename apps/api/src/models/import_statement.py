import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from src.database import Base

if TYPE_CHECKING:
    from src.models.repo_file import RepoFile


class FileImport(Base):
    __tablename__ = "imports"

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
    source_module: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        index=True
    )
    imported_symbol: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    alias: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    file: Mapped["RepoFile"] = relationship("RepoFile", back_populates="imports")
