import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from src.database import Base

if TYPE_CHECKING:
    from src.models.oauth_connection import OAuthConnection


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    github_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        index=True,
        nullable=True
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
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

    # Relationships
    oauth_connections: Mapped[List["OAuthConnection"]] = relationship(
        "OAuthConnection",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
