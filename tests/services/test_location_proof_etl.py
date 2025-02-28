"""Tests for the LocationProof ETL validation process."""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from eth_abi import encode
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.address import Address
from app.models.chain import Chain
from app.models.location_proof import LocationProof
from app.services.eas_integration import EASIntegrationService
from app.services.schema_encoder import SchemaEncoder


@pytest.fixture
def sample_attestation() -> Dict[str, Any]:
    """Create a sample attestation for testing."""
    # Create sample data matching our schema
    schema_data = (
        1234567890,  # eventTimestamp
        "EPSG:4326",  # srs
        "Point",  # locationType
        "40.7128,-74.0060",  # location
        ["recipe1"],  # recipeType
        [b"payload1"],  # recipePayload
        ["image/jpeg"],  # mediaType
        ["data1"],  # mediaData
        "Test memo",  # memo
    )

    # Encode the test data
    encoded_data = encode(SchemaEncoder.SCHEMA_TYPES, schema_data)

    schema_id = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

    return {
        "id": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "attester": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "recipient": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        "refUID": "0x0000000000000000000000000000000000000000000000000000000000000000",
        "revocable": True,
        "revocationTime": 0,
        "expirationTime": 0,
        "time": 1234567890,
        "data": "0x" + encoded_data.hex(),
        "schemaId": schema_id,
    }


@pytest.fixture
def sample_chain() -> Dict[str, Any]:
    """Create a sample chain for testing."""
    return {
        "id": 1,
        "chain_id": 11155111,  # Sepolia testnet
        "name": "Sepolia",
        "chain": "ETH",
        "rpc": ["https://rpc.sepolia.org"],
        "faucets": [],
        "native_currency": {
            "name": "Sepolia Ether",
            "symbol": "ETH",
            "decimals": "18",
        },
        "features": [
            {
                "name": "EAS",
                "url": "https://sepolia.easscan.org/graphql",
            }
        ],
        "info_url": "https://sepolia.etherscan.io",
        "short_name": "sep",
        "network_id": 11155111,
        "icon": "ethereum",
        "explorers": [
            {
                "name": "etherscan-sepolia",
                "url": "https://sepolia.etherscan.io",
                "standard": "EIP3091",
            }
        ],
    }


@pytest.mark.asyncio
async def test_parse_attestation_data(sample_attestation: Dict[str, Any]) -> None:
    """Test parsing attestation data."""
    # Create EAS integration service
    mock_session_factory = AsyncMock()
    service = EASIntegrationService(mock_session_factory)

    # Parse attestation data
    parsed_data = service._parse_attestation_data(sample_attestation)

    # Verify parsed data
    assert parsed_data is not None
    assert parsed_data["event_timestamp"] == 1234567890
    assert parsed_data["srs"] == "EPSG:4326"
    assert parsed_data["spatial_type"] == "Point"
    assert parsed_data["location_wkt"] == "40.7128,-74.0060"
    assert parsed_data["recipe_type"] == "recipe1"
    assert "data" in parsed_data["recipe_payload"]
    assert parsed_data["media_type"] == "image/jpeg"
    assert parsed_data["media_data"] == "data1"
    assert parsed_data["memo"] == "Test memo"


@pytest.mark.asyncio
async def test_parse_attestation_data_invalid() -> None:
    """Test parsing invalid attestation data."""
    # Create EAS integration service
    mock_session_factory = AsyncMock()
    service = EASIntegrationService(mock_session_factory)

    # Test with missing data field
    invalid_attestation = {
        "id": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "attester": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "recipient": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        # Missing data field
    }

    parsed_data = service._parse_attestation_data(invalid_attestation)
    assert parsed_data is None

    # Test with invalid data format
    invalid_attestation = {
        "id": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "attester": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "recipient": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        "data": "12345",  # Invalid data type (not hex)
    }

    parsed_data = service._parse_attestation_data(invalid_attestation)
    assert parsed_data is None

    # Test with invalid hex data
    invalid_attestation = {
        "id": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "attester": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "recipient": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        "data": "0xZZZZ",  # Invalid hex data
    }

    parsed_data = service._parse_attestation_data(invalid_attestation)
    assert parsed_data is None


@pytest.mark.asyncio
async def test_chain_reference_handling(
    sample_attestation: Dict[str, Any], sample_chain: Dict[str, Any]
) -> None:
    """Test chain reference handling in the ETL process."""
    # Create mock session and chain
    mock_session = AsyncMock(spec=AsyncSession)

    # Create a Chain instance
    chain = Chain(**sample_chain)

    # Mock address creation
    mock_address = Address(id=1, address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")

    # Create EAS integration service with mocked session factory
    mock_session_factory = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    service = EASIntegrationService(mock_session_factory)

    # Mock the _parse_attestation_data method to return a valid parsed data
    schema_uid = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    attestation_uid = (
        "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    )
    tx_hash = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

    parsed_data = {
        "event_timestamp": 1234567890,
        "srs": "EPSG:4326",
        "spatial_type": "Point",
        "location_wkt": "40.7128,-74.0060",
        "recipe_type": "recipe1",
        "recipe_payload": {"data": "payload1"},
        "media_type": "image/jpeg",
        "media_data": "data1",
        "memo": "Test memo",
        "schema_uid": schema_uid,
        "attestation_uid": attestation_uid,
        "expiration_time": 0,
        "revoked": False,
        "revocation_time": None,
        "ref_uid": None,
        "revocable": True,
        "status": "onchain",
        "block_number": 12345678,
        "transaction_hash": tx_hash,
        "cid": None,
        "extra": {},
    }

    with patch.object(service, "_parse_attestation_data", return_value=parsed_data):
        with patch.object(
            service, "_get_or_create_address", new_callable=AsyncMock
        ) as mock_get_address:
            mock_get_address.return_value = mock_address

            # Mock the chain query
            async def mock_execute_side_effect(*args: Any, **kwargs: Any) -> MagicMock:
                mock_result = MagicMock()
                mock_result.scalars().first.return_value = chain
                return mock_result

            mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

            # Process the attestation
            result = await service._process_attestations(
                mock_session, 11155111, [sample_attestation]
            )

            # Verify that the attestation was processed
            assert result == 1

            # Verify that session.add was called with a LocationProof object
            assert mock_session.add.called

            # Get the LocationProof object that was added
            location_proof = mock_session.add.call_args[0][0]
            assert isinstance(location_proof, LocationProof)

            # Verify that the chain_id is correctly set
            assert location_proof.chain_id == chain.id


@pytest.mark.asyncio
async def test_end_to_end_attestation_processing(
    sample_attestation: Dict[str, Any], sample_chain: Dict[str, Any]
) -> None:
    """Test end-to-end attestation processing."""
    # Create mock session, chain, and addresses
    mock_session = AsyncMock(spec=AsyncSession)

    # Create a Chain instance
    chain = Chain(**sample_chain)

    # Create attester and recipient addresses
    attester_addr = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
    recipient_addr = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
    attester = Address(id=1, address=attester_addr)
    recipient = Address(id=2, address=recipient_addr)

    # Create EAS integration service with mocked session factory
    mock_session_factory = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    service = EASIntegrationService(mock_session_factory)

    # Mock the _parse_attestation_data method to return valid parsed data
    schema_uid = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    attestation_uid = (
        "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    )
    tx_hash = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

    parsed_data = {
        "event_timestamp": 1234567890,
        "srs": "EPSG:4326",
        "spatial_type": "Point",
        "location_wkt": "40.7128,-74.0060",
        "recipe_type": "recipe1",
        "recipe_payload": {"data": "payload1"},
        "media_type": "image/jpeg",
        "media_data": "data1",
        "memo": "Test memo",
        "schema_uid": schema_uid,
        "attestation_uid": attestation_uid,
        "expiration_time": 0,
        "revoked": False,
        "revocation_time": None,
        "ref_uid": None,
        "revocable": True,
        "status": "onchain",
        "block_number": 12345678,
        "transaction_hash": tx_hash,
        "cid": None,
        "extra": {},
    }

    with patch.object(service, "_parse_attestation_data", return_value=parsed_data):
        # Mock the chain query
        async def mock_execute_side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            mock_result = MagicMock()
            mock_result.scalars().first.return_value = chain
            return mock_result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

        # Mock the _get_or_create_address method to return appropriate addresses
        with patch.object(
            service, "_get_or_create_address", new_callable=AsyncMock
        ) as mock_get_address:
            # Return different addresses based on the input address
            async def side_effect(session: AsyncSession, address: str) -> Address:
                if address == attester_addr:
                    return attester
                else:
                    return recipient

            mock_get_address.side_effect = side_effect

            # Process the attestation
            result = await service._process_attestations(
                mock_session, 11155111, [sample_attestation]
            )

            # Verify that the attestation was processed
            assert result == 1

            # Verify that session.add was called with a LocationProof object
            assert mock_session.add.called

            # Get the LocationProof object that was added
            location_proof = mock_session.add.call_args[0][0]
            assert isinstance(location_proof, LocationProof)

            # Verify that the relationships are correctly set
            assert location_proof.chain_id == chain.id
            assert location_proof.attester == attester
            assert location_proof.recipient == recipient


@pytest.mark.asyncio
async def test_validate_location_proof_data() -> None:
    """Test validation of location proof data."""
    # Create EAS integration service
    mock_session_factory = AsyncMock()
    service = EASIntegrationService(mock_session_factory)

    # Valid data
    valid_data = {
        "event_timestamp": 1234567890,
        "srs": "EPSG:4326",
        "spatial_type": "Point",
        "location_wkt": "40.7128,-74.0060",
        "recipe_type": "recipe1",
        "recipe_payload": {"data": "payload1"},
        "media_type": "image/jpeg",
        "media_data": "data1",
        "memo": "Test memo",
    }

    # Test valid data
    assert service._validate_location_proof_data(valid_data) is True

    # Test missing required field
    invalid_data = valid_data.copy()
    del invalid_data["srs"]
    assert service._validate_location_proof_data(invalid_data) is False

    # Test invalid eventTimestamp
    invalid_data = valid_data.copy()
    invalid_data["event_timestamp"] = "1234567890"  # string instead of int
    assert service._validate_location_proof_data(invalid_data) is False

    # Test invalid srs
    invalid_data = valid_data.copy()
    invalid_data["srs"] = ""  # empty string
    assert service._validate_location_proof_data(invalid_data) is False

    # Test invalid locationType
    invalid_data = valid_data.copy()
    invalid_data["spatial_type"] = 123  # int instead of string
    assert service._validate_location_proof_data(invalid_data) is False

    # Test invalid location
    invalid_data = valid_data.copy()
    invalid_data["location_wkt"] = None  # None instead of string
    assert service._validate_location_proof_data(invalid_data) is False

    # Test invalid recipeType
    invalid_data = valid_data.copy()
    invalid_data["recipe_type"] = 123  # int instead of string
    assert service._validate_location_proof_data(invalid_data) is False

    # Test invalid recipePayload
    invalid_data = valid_data.copy()
    invalid_data["recipe_payload"] = "payload1"  # string instead of dict
    assert service._validate_location_proof_data(invalid_data) is False
