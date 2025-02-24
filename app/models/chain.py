"""Chain model for the Astral API."""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.location_proof import LocationProof


class Chain(Base):
    """Chain model for storing blockchain network metadata."""

    # Override id to use chain_id as primary key
    __mapper_args__ = {"primary_key": ["chain_id"]}
    id: Mapped[int] = None  # type: ignore

    # Chain-specific columns
    chain_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
        index=True,
        doc="The chain ID (e.g. 1 for Ethereum mainnet)",
    )
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
