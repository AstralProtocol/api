"""SchemaEncoder for decoding EAS attestation data.

This module provides functionality to decode EAS attestation data based on our schema.
See EAS documentation for more details about schema encoding and decoding.
"""

from typing import Any, Dict

from eth_abi import decode
from eth_abi.exceptions import DecodingError


class SchemaEncoder:
    """Handles encoding/decoding of EAS attestation data for our specific schema."""

    # Our schema's type tuple for eth_abi decoding
    SCHEMA_TYPES = (
        "uint256",  # eventTimestamp
        "string",  # srs
        "string",  # locationType
        "string",  # location
        "string[]",  # recipeType
        "bytes[]",  # recipePayload
        "string[]",  # mediaType
        "string[]",  # mediaData
        "string",  # memo
    )

    # Field names in order matching the schema types
    FIELD_NAMES = (
        "eventTimestamp",
        "srs",
        "locationType",
        "location",
        "recipeType",
        "recipePayload",
        "mediaType",
        "mediaData",
        "memo",
    )

    # Fields that should be lists (not tuples)
    ARRAY_FIELDS = {
        "recipeType",
        "recipePayload",
        "mediaType",
        "mediaData",
    }

    @classmethod
    def decode_data(cls, encoded_data: bytes) -> Dict[str, Any]:
        """Decode EAS attestation data according to our schema.

        Args:
            encoded_data: The encoded attestation data as bytes

        Returns:
            Dict containing the decoded data with field names as keys

        Raises:
            DecodingError: If the data cannot be decoded according to the schema
            ValueError: If the decoded data structure doesn't match expectations
        """
        try:
            # Decode the data using eth_abi
            decoded_tuple = decode(cls.SCHEMA_TYPES, encoded_data)

            # Convert to dictionary and handle array types
            result = {}
            for field_name, value in zip(cls.FIELD_NAMES, decoded_tuple):
                if field_name in cls.ARRAY_FIELDS and isinstance(value, tuple):
                    result[field_name] = list(value)
                else:
                    result[field_name] = value

            return result

        except DecodingError as e:
            raise DecodingError(f"Failed to decode EAS data: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error processing decoded data: {str(e)}")

    @staticmethod
    def validate_decoded_data(data: Dict[str, Any]) -> None:
        """Validate that decoded data matches expected types and structure.

        Args:
            data: The decoded data dictionary to validate

        Raises:
            ValueError: If the data structure is invalid
        """
        # Check eventTimestamp is an integer
        if not isinstance(data.get("eventTimestamp"), int):
            raise ValueError("eventTimestamp must be an integer")

        # Check string fields
        string_fields = ["srs", "locationType", "location", "memo"]
        for field in string_fields:
            if not isinstance(data.get(field), str):
                raise ValueError(f"{field} must be a string")

        # Check array fields
        array_fields = ["recipeType", "mediaType", "mediaData"]
        for field in array_fields:
            if not isinstance(data.get(field), list):
                raise ValueError(f"{field} must be an array")
            # Check all elements are strings
            if not all(isinstance(item, str) for item in data.get(field, [])):
                raise ValueError(f"All elements in {field} must be strings")

        # Check recipePayload is an array of bytes
        if not isinstance(data.get("recipePayload"), list):
            raise ValueError("recipePayload must be an array")
        if not all(isinstance(item, bytes) for item in data.get("recipePayload", [])):
            raise ValueError("All elements in recipePayload must be bytes")
