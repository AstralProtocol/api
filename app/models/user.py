"""User model for the Astral API."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.address import Address


class User(Base):
    """User model for storing user information."""

    # Override id from Base to add index and docstring
    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
        doc="Unique identifier for each user",
    )

    # User-specific columns
    name: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        doc="Optional display name for the user",
    )
    role: Mapped[str] = mapped_column(
        String,
        default="user",
        nullable=False,
        doc='Role of the user (e.g., "admin", "user"). Defaults to "user".',
    )

    # Relationships
    addresses: Mapped[list["Address"]] = relationship(
        "Address",
        back_populates="user",
        cascade="all, delete-orphan",
    )
