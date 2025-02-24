"""Address model for the Astral API."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.location_proof import LocationProof
    from app.models.user import User


class Address(Base):
    """Address model for storing blockchain addresses."""

    # Override id from Base to add index and docstring
    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
        doc="Unique identifier for the address record",
    )

    # Foreign Keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        index=True,
        doc="References the Users table to link an address to a user",
    )

    # Address-specific columns
    address: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True,
        nullable=False,
        doc="The blockchain address (e.g., Ethereum address). Must be unique",
    )
    label: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        doc="Optional description or label for the address",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Indicates if the user has proven ownership via a valid signature",
    )
    digital_signature: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        doc="The digital signature provided to verify address ownership",
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="addresses")

    attested_proofs: Mapped[list["LocationProof"]] = relationship(
        "LocationProof",
        back_populates="attester",
        foreign_keys="[LocationProof.attester_id]",
        cascade="all, delete-orphan",
    )

    received_proofs: Mapped[list["LocationProof"]] = relationship(
        "LocationProof",
        back_populates="recipient",
        foreign_keys="[LocationProof.recipient_id]",
        cascade="all, delete-orphan",
    )
