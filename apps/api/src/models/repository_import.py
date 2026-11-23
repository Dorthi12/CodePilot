import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from src.database import Base

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.repository import Repository


class RepositoryImport(Base):
    __tablename__ = "repository_imports"

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
    repository_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        default="github",
        nullable=False
    )
    provider_repo_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    repo_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    source_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="SUCCEEDED",
        nullable=False
    )  # 'SUCCEEDED', 'FAILED', 'IN_PROGRESS'
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    repository: Mapped[Optional["Repository"]] = relationship("Repository", back_populates="imports")
