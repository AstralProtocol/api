"""Address schemas for request/response validation."""

from pydantic import Field

from app.schemas.base import BaseSchema, TimestampedSchema


class AddressBase(BaseSchema):
    """Shared properties for address schemas."""

    address: str = Field(
        ...,
        description="The blockchain address (e.g., Ethereum address)",
        pattern="^0x[a-fA-F0-9]{40}$",  # Ethereum address format
    )
    label: str | None = Field(
        None, description="Optional description or label for the address"
    )
    is_verified: bool = Field(
        False,
        description="Indicates if the user has proven ownership via a valid signature",
    )
    digital_signature: str | None = Field(
        None,
        description="The digital signature provided to verify address ownership",
    )


class AddressCreate(AddressBase):
    """Properties to receive on address creation."""

    user_id: int = Field(..., description="ID of the user who owns this address")


class AddressUpdate(AddressBase):
    """Properties to receive on address update."""

    pass


class Address(AddressBase, TimestampedSchema):
    """Properties to return to client."""

    id: int = Field(..., description="Unique identifier for the address record")
    user_id: int = Field(..., description="ID of the user who owns this address")


class AddressInDB(Address):
    """Additional properties stored in DB."""

    pass
