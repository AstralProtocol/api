"""User schemas for the Astral API."""

from pydantic import Field

from app.schemas.base import BaseSchema, TimestampedSchema


class UserBase(BaseSchema):
    """Shared properties for user schemas."""

    name: str | None = Field(None, description="Optional display name for the user")
    role: str = Field("user", description='Role of the user (e.g., "admin", "user")')


class UserCreate(UserBase):
    """Properties to receive on user creation."""

    pass


class UserUpdate(UserBase):
    """Properties to receive on user update."""

    pass


class User(UserBase, TimestampedSchema):
    """Properties to return to client."""

    id: int = Field(..., description="Unique identifier for each user")


class UserInDB(User):
    """Additional properties stored in DB."""

    pass
