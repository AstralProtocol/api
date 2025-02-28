"""Integration tests for the LocationProof ETL process."""

from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.address import Address
from app.models.chain import Chain
from app.models.location_proof import LocationProof
from app.models.sync_state import SyncState
from app.services.eas_integration import EASIntegrationService


class MockGQLResponse:
    """Mock GQL response for testing."""

    def __init__(self, data: Dict[str, Any]) -> None:
        """Initialize with data."""
        self.data = data


@pytest.fixture
def mock_gql_client() -> MagicMock:
    """Create a mock GQL client for testing."""
    return MagicMock()


@pytest.mark.asyncio
async def test_sync_attestations_integration(mock_gql_client: MagicMock) -> None:
    """Test the end-to-end attestation synchronization process."""
    # Create a mock session
    mock_session = AsyncMock(spec=AsyncSession)

    # Create a mock session factory as an async generator
    async def mock_session_factory() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    # Create a test chain
    chain = Chain(
        id=1,
        chain_id=11155111,  # Sepolia testnet
        name="Sepolia",
        chain="ETH",
        rpc=["https://rpc.sepolia.org"],
        faucets=[],
        native_currency={
            "name": "Sepolia Ether",
            "symbol": "ETH",
            "decimals": 18,
        },
        features=[
            {
                "name": "EAS",
                "url": "https://sepolia.easscan.org/graphql",
            }
        ],
        info_url="https://sepolia.etherscan.io",
        short_name="sep",
        network_id=11155111,
        icon="ethereum",
        explorers=[
            {
                "name": "etherscan-sepolia",
                "url": "https://sepolia.etherscan.io",
                "standard": "EIP3091",
            }
        ],
    )

    # Create a sync state
    sync_state = SyncState(
        chain_id=chain.id,
        last_block_number=0,
        last_timestamp=0,
        schema_uid="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    )

    # Mock the session.execute method to return the chain and sync state
    async def mock_execute_side_effect(*args: Any, **kwargs: Any) -> MagicMock:
        query = args[0]
        if hasattr(query, "column_descriptions"):
            target_class = query.column_descriptions[0]["entity"]
            if target_class == Chain:
                mock_result = MagicMock()
                mock_result.scalars().first.return_value = chain
                return mock_result
            elif target_class == SyncState:
                mock_result = MagicMock()
                mock_result.scalars().first.return_value = sync_state
                return mock_result
            elif target_class == LocationProof:
                mock_result = MagicMock()
                mock_result.scalars().first.return_value = None
                return mock_result
        return MagicMock()

    mock_session.execute.side_effect = mock_execute_side_effect

    # Create mock addresses
    attester = Address(id=1, address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")
    recipient = Address(id=2, address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8")

    # Create the EAS integration service with the mock session factory
    eas_service = EASIntegrationService(mock_session_factory)

    # Set up the service with mock clients and schema UIDs
    eas_service.clients = {11155111: mock_gql_client}
    schema_uid = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    eas_service.schema_uids = {11155111: schema_uid}
    eas_service.initialized = True

    # Mock the _get_or_create_address method
    async def mock_get_or_create_address(
        session: AsyncSession, address_str: str
    ) -> Address:
        if address_str == attester.address:
            return attester
        elif address_str == recipient.address:
            return recipient
        return Address(id=0, address=address_str)

    # Create a sample attestation
    sample_attestation = {
        "id": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "attester": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "recipient": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        "refUID": "0x0000000000000000000000000000000000000000000000000000000000000000",
        "revocable": True,
        "revocationTime": 0,
        "expirationTime": 0,
        "time": 1234567890,
        # Shortened hex data for readability and to avoid line length issues
        "data": "0x0000000000000000000000000000000000000000000000000000000049950b20",
        "schemaId": schema_uid,
        "blockNumber": "12345678",
    }

    # Mock the _query_attestations method
    with patch.object(
        eas_service, "_get_or_create_address", side_effect=mock_get_or_create_address
    ):
        with patch.object(
            eas_service, "_query_attestations", return_value=[sample_attestation]
        ):
            # Mock the _parse_attestation_data method
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
                "attestation_uid": sample_attestation["id"],
                "status": "onchain",
                "revocable": True,
                "revocation_time": 0,
                "expiration_time": 0,
                "ref_uid": sample_attestation["refUID"],
                "block_number": 12345678,
                "transaction_hash": None,
                "extra": {},
            }
            with patch.object(
                eas_service, "_parse_attestation_data", return_value=parsed_data
            ):
                # Call the sync_attestations method
                result = await eas_service.sync_attestations([11155111])

                # Verify that attestations were synced
                assert result[11155111] == 1

                # Verify that session.add was called with a LocationProof object
                assert mock_session.add.called

                # Verify that the sync state was updated
                assert sync_state.last_block_number == 12345678
                assert sync_state.last_timestamp == 1234567890
                assert sync_state.last_attestation_uid == sample_attestation["id"]

                # Verify that session.commit was called
                assert mock_session.commit.called
