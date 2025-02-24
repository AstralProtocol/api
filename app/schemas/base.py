"""Base schema with common functionality."""

from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel, ConfigDict

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseSchema(BaseModel):
    """Base schema with common functionality."""

    model_config = ConfigDict(from_attributes=True)


class TimestampedSchema(BaseSchema):
    """Base schema with timestamp fields."""

    created_at: datetime
    updated_at: datetime
