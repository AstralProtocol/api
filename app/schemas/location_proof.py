"""Location proof schemas for the Astral API."""

from typing import Dict, Literal

from pydantic import Field, field_validator

from app.schemas.base import TimestampedSchema


class LocationProofBase(TimestampedSchema):
    """Shared properties for location proof schemas."""

    # EAS Attestation fields
    schema_uid: str = Field(
        ...,
        description="EAS schema UID for the location proof",
        pattern=r"^0x[a-fA-F0-9]{64}$",
    )
    event_timestamp: int = Field(
        ..., description="Unix timestamp when the event occurred"
    )
    expiration_time: int | None = Field(
        None,
        description="Unix timestamp when the attestation expires, if applicable",
    )
    revoked: bool = Field(
        False,
        description="Indicates whether the attestation has been revoked",
    )
    revocation_time: int | None = Field(
        None,
        description="Unix timestamp when revoked (if applicable)",
    )
    ref_uid: str | None = Field(
        None,
        description="Reference UID to another attestation, if applicable",
    )
    revocable: bool = Field(
        True,
        description="Indicates whether the attestation can be revoked",
    )

    # Geospatial fields
    srs: str = Field(
        "EPSG:4326",
        description="Spatial Reference System (e.g., EPSG code)",
        pattern="^EPSG:[0-9]+$",
    )
    location_type: Literal["point", "linestring", "polygon", "bbox"] = Field(
        ...,
        description="Type of spatial data (e.g., point, polygon, etc.)",
    )
    location: str = Field(
        ...,
        description="WKT representation of the geometry",
        examples=[
            "POINT(-71.064544 42.28787)",
            "POLYGON((-71.064544 42.28787, -71.064544 42.28787))",
        ],
    )

    # Recipe and media fields
    recipe_type: str = Field(..., description="Recipe type stored as plain text")
    recipe_payload: Dict = Field(
        ...,
        description="Recipe payload stored as JSONB for flexibility",
    )
    media_type: str = Field(..., description="Media type stored as plain text")
    media_data: str = Field(..., description="Media data (e.g., IPFS CID)")
    memo: str | None = Field(
        None, description="Optional memo or note for the attestation"
    )

    # Status and blockchain fields
    status: Literal[
        "onchain (pending)",
        "onchain (validated)",
        "onchain (invalidated)",
        "IPFS",
        "off-chain",
    ] = Field(
        ...,
        description="Current status of the attestation",
    )
    block_number: int | None = Field(
        None,
        description="Block number when the attestation was recorded",
    )
    transaction_hash: str | None = Field(
        None,
        description="Transaction hash linking to the on-chain attestation",
        pattern="^0x[a-fA-F0-9]{64}$",
    )
    cid: str | None = Field(
        None,
        description="IPFS CID if the attestation is stored on IPFS",
    )

    # Additional data
    extra: Dict = Field(
        default_factory=dict,
        description="Additional extensible data",
    )

    @field_validator("location")
    def validate_wkt(cls, v: str) -> str:
        """Validate Well-Known Text (WKT) format."""
        # TODO: Add proper WKT validation
        return v


class LocationProofCreate(LocationProofBase):
    """Properties to receive on location proof creation."""

    chain_id: int = Field(
        ...,
        description="ID of the blockchain network the attestation is on",
    )
    attester_id: int = Field(
        ...,
        description="ID of the address that created the attestation",
    )
    recipient_id: int = Field(
        ...,
        description="ID of the address that received the attestation",
    )


class LocationProofUpdate(LocationProofBase):
    """Properties to receive on location proof update."""

    pass


class LocationProof(LocationProofBase):
    """Properties to return to client."""

    id: int = Field(..., description="Unique identifier for the location proof record")
    chain_id: int = Field(
        ...,
        description="ID of the blockchain network the attestation is on",
    )
    attester_id: int = Field(
        ...,
        description="ID of the address that created the attestation",
    )
    recipient_id: int = Field(
        ...,
        description="ID of the address that received the attestation",
    )


class LocationProofInDB(LocationProof):
    """Additional properties stored in DB."""

    pass
