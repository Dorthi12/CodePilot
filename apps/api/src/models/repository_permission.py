import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from src.database import Base

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.repository import Repository


class RepositoryPermission(Base):
    __tablename__ = "repository_permissions"

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
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(
        String(32),
        default="OWNER",
        nullable=False
    )  # 'OWNER', 'ADMIN', 'VIEWER'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint("repository_id", "user_id", name="uq_repo_user_permission"),
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="permissions")
    user: Mapped["User"] = relationship("User")
