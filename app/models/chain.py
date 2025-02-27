"""Chain model for the Astral API."""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.location_proof import LocationProof


class Chain(Base):
    """Chain model for storing blockchain network metadata."""

    # Override __tablename__ to match migration
    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        """Return the table name."""
        return "chain"

    # Override id with a non-primary key version
    # This effectively disables the id column from Base
    # Use type: ignore to bypass the type checker for this special case
    id: Mapped[int] = mapped_column(primary_key=False, nullable=True)  # type: ignore

    # Use chain_id as primary key instead of id
    chain_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        doc="The chain ID (e.g. 1 for Ethereum mainnet)",
    )

    # Chain-specific columns
    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc='Full name of the blockchain network (e.g., "Ethereum Mainnet")',
    )
    chain: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc='Abbreviated chain symbol (e.g., "ETH")',
    )
    rpc: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        doc="Array of RPC endpoint URLs",
    )
    faucets: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Array of faucet URLs (if any)",
    )
    native_currency: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        doc="JSON object containing native currency details",
    )
    features: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Array of feature objects",
    )
    info_url: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        doc="URL for more information about the blockchain network",
    )
    short_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="Short name for display purposes",
    )
    network_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Network identifier",
    )
    icon: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="Identifier for an icon (useful for UI display)",
    )
    explorers: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Array of blockchain explorer objects",
    )

    # Relationships
    location_proofs: Mapped[list["LocationProof"]] = relationship(
        "LocationProof", back_populates="chain", cascade="all, delete-orphan"
    )
