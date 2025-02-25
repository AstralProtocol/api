"""SyncState model for tracking EAS synchronization state."""

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SyncState(Base):
    """SyncState model for tracking EAS synchronization state.

    This model keeps track of the last synchronized block number, timestamp,
    and attestation UID for each chain, allowing the EAS integration service
    to resume synchronization from where it left off.
    """

    # Override id from Base to add index and docstring
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        index=True,
        doc="Unique identifier for the sync state record",
    )

    # Chain relationship
    chain_id: Mapped[int] = mapped_column(
        ForeignKey("chain.chain_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="References the Chains table",
    )

    # Sync state fields
    last_block_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        doc="Last synchronized block number",
    )

    last_timestamp: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        doc="Last synchronized timestamp (Unix timestamp)",
    )

    last_attestation_uid: Mapped[str | None] = mapped_column(
        String(66),
        nullable=True,
        doc="UID of the last synchronized attestation",
    )

    # Schema UID to track
    schema_uid: Mapped[str] = mapped_column(
        String(66),
        nullable=False,
        doc="EAS schema UID to track",
    )

    # Relationships
    chain = relationship("Chain")

    def __repr__(self) -> str:
        """Return string representation of the sync state."""
        return (
            f"<SyncState(id={self.id}, chain_id={self.chain_id}, "
            f"last_block_number={self.last_block_number}, "
            f"last_timestamp={self.last_timestamp})>"
        )
