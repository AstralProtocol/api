"""LocationProof model for the Astral API."""

from typing import TYPE_CHECKING, Any

from shapely import wkt
from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.address import Address
    from app.models.chain import Chain


class Geometry(TypeDecorator):
    """Custom type for PostGIS geometry columns."""

    impl = Text
    cache_ok = True

    def __init__(self, srid: int = 4326) -> None:
        """Initialize geometry type with SRID."""
        super().__init__()
        self.srid = srid

    def load_dialect_impl(self, dialect: Any) -> Any:
        """Load PostGIS geometry type for PostgreSQL."""
        if dialect.name == "postgresql":
            from geoalchemy2 import Geometry as PostGISGeometry

            return dialect.type_descriptor(PostGISGeometry(srid=self.srid))
        return dialect.type_descriptor(self.impl)


class LocationProof(Base):
    """LocationProof model for storing attestation data."""

    # Set explicit table name to match migration
    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        """Return the table name."""
        return "location_proof"

    # Override id from Base to add index and docstring
    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
        doc="Unique identifier for the location proof record",
    )

    # EAS Attestation fields
    schema_uid: Mapped[str] = mapped_column(
        String(66),
        nullable=False,
        doc="EAS schema UID for the location proof",
    )

    attestation_uid: Mapped[str] = mapped_column(
        String(66),
        nullable=False,
        doc="EAS attestation UID",
    )

    event_timestamp: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="Unix timestamp of the event",
    )
    expiration_time: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        doc="Unix timestamp when the attestation expires",
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Indicates whether the attestation has been revoked",
    )
    revocation_time: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        doc="Unix timestamp when revoked (if applicable)",
    )
    ref_uid: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        doc="Reference UID to another attestation",
    )
    revocable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Indicates whether the attestation can be revoked",
    )

    # Geospatial fields
    srs: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="Spatial Reference System (e.g., EPSG code)",
    )
    spatial_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Type of spatial data (point, polygon, etc.)",
    )
    location_wkt: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        doc="WKT representation of the location",
    )

    # Recipe and media fields
    recipe_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="Recipe type stored as plain text",
    )
    recipe_payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        doc="Recipe payload stored as JSONB for flexibility",
    )
    media_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="Media type stored as plain text",
    )
    media_data: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="Media data (e.g., IPFS CID)",
    )
    memo: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        doc="Optional memo or note for the attestation",
    )

    # Status and blockchain fields
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="Current status of the attestation",
    )
    block_number: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        doc="Block number when recorded",
    )
    transaction_hash: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        doc="Transaction hash for on-chain attestation",
    )
    cid: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        doc="IPFS CID if stored on IPFS",
    )

    # Foreign Keys
    chain_id: Mapped[int] = mapped_column(
        ForeignKey("chain.chain_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="References the Chains table",
    )
    attester_id: Mapped[int] = mapped_column(
        ForeignKey("address.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="References the attester's address",
    )
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("address.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="References the recipient's address",
    )

    # Additional data
    extra: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Additional extensible data",
    )

    # Relationships
    chain: Mapped["Chain"] = relationship("Chain", back_populates="location_proofs")

    attester: Mapped["Address"] = relationship(
        "Address",
        back_populates="attested_proofs",
        foreign_keys=[attester_id],
    )

    recipient: Mapped["Address"] = relationship(
        "Address",
        back_populates="received_proofs",
        foreign_keys=[recipient_id],
    )


def validate_wkt(value: str) -> str:
    """Validate that a string is a valid WKT geometry."""
    try:
        wkt.loads(value)
        return value
    except Exception as e:
        raise ValueError(f"Invalid WKT geometry: {e}")
