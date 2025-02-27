"""Tests for the SchemaEncoder class."""

from typing import List, Tuple

import pytest
from eth_abi import encode
from eth_abi.exceptions import DecodingError

from app.services.schema_encoder import SchemaEncoder


def test_decode_valid_data() -> None:
    """Test decoding valid EAS attestation data."""
    # Create sample data matching our schema
    test_data: Tuple[
        int, str, str, str, List[str], List[bytes], List[str], List[str], str
    ] = (
        1234567890,  # eventTimestamp
        "EPSG:4326",  # srs
        "Point",  # locationType
        "40.7128,-74.0060",  # location
        ["recipe1", "recipe2"],  # recipeType
        [b"payload1", b"payload2"],  # recipePayload
        ["image/jpeg", "image/png"],  # mediaType
        ["data1", "data2"],  # mediaData
        "Test memo",  # memo
    )

    # Encode the test data
    encoded_data = encode(SchemaEncoder.SCHEMA_TYPES, test_data)

    # Decode and verify
    result = SchemaEncoder.decode_data(encoded_data)

    assert result["eventTimestamp"] == 1234567890
    assert result["srs"] == "EPSG:4326"
    assert result["locationType"] == "Point"
    assert result["location"] == "40.7128,-74.0060"
    assert result["recipeType"] == ["recipe1", "recipe2"]
    assert result["recipePayload"] == [b"payload1", b"payload2"]
    assert result["mediaType"] == ["image/jpeg", "image/png"]
    assert result["mediaData"] == ["data1", "data2"]
    assert result["memo"] == "Test memo"


def test_decode_minimal_data() -> None:
    """Test decoding data with empty arrays."""
    test_data: Tuple[
        int, str, str, str, List[str], List[bytes], List[str], List[str], str
    ] = (
        1234567890,
        "EPSG:4326",
        "Point",
        "40.7128,-74.0060",
        [],  # empty recipeType
        [],  # empty recipePayload
        [],  # empty mediaType
        [],  # empty mediaData
        "",  # empty memo
    )

    encoded_data = encode(SchemaEncoder.SCHEMA_TYPES, test_data)
    result = SchemaEncoder.decode_data(encoded_data)

    assert result["recipeType"] == []
    assert result["recipePayload"] == []
    assert result["mediaType"] == []
    assert result["mediaData"] == []
    assert result["memo"] == ""


def test_invalid_data() -> None:
    """Test that invalid data raises appropriate exceptions."""
    # Create invalid data (wrong number of fields)
    test_data: Tuple[int, str, str] = (
        1234567890,
        "EPSG:4326",
        "Point",
    )  # Missing other fields

    encoded_data = encode(("uint256", "string", "string"), test_data)

    with pytest.raises(DecodingError):
        SchemaEncoder.decode_data(encoded_data)


def test_validate_decoded_data() -> None:
    """Test validation of decoded data."""
    # Valid data
    valid_data = {
        "eventTimestamp": 1234567890,
        "srs": "EPSG:4326",
        "locationType": "Point",
        "location": "40.7128,-74.0060",
        "recipeType": ["recipe1"],
        "recipePayload": [b"payload1"],
        "mediaType": ["image/jpeg"],
        "mediaData": ["data1"],
        "memo": "Test memo",
    }

    # Should not raise any exceptions
    SchemaEncoder.validate_decoded_data(valid_data)

    # Test invalid eventTimestamp type
    invalid_data = valid_data.copy()
    invalid_data["eventTimestamp"] = "1234567890"  # string instead of int
    with pytest.raises(ValueError, match="eventTimestamp must be an integer"):
        SchemaEncoder.validate_decoded_data(invalid_data)

    # Test invalid array content
    invalid_data = valid_data.copy()
    invalid_data["recipePayload"] = ["not bytes"]  # strings instead of bytes
    with pytest.raises(ValueError, match="All elements in recipePayload must be bytes"):
        SchemaEncoder.validate_decoded_data(invalid_data)

    # Test invalid string field
    invalid_data = valid_data.copy()
    invalid_data["location"] = 12345  # int instead of string
    with pytest.raises(ValueError, match="location must be a string"):
        SchemaEncoder.validate_decoded_data(invalid_data)
