"""Unit tests for EAS integration service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chain import Chain
from app.models.sync_state import SyncState
from app.services.eas_integration import EASIntegrationService


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_session_factory() -> MagicMock:
    """Create a mock session factory."""
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = AsyncMock(spec=AsyncSession)
    return factory


@pytest.fixture
def mock_chain() -> Chain:
    """Create a mock Chain object for testing."""
    chain = Chain(
        chain_id=1,
        name="Test Chain",
        rpc_url="https://test.chain",
        eas_url="https://eas.test.chain",
        explorer_url="https://explorer.test.chain",
    )
    return chain


@pytest.fixture
def mock_sync_state() -> MagicMock:
    """Create a mock SyncState object."""
    sync_state = MagicMock(spec=SyncState)
    sync_state.chain_id = 1
    sync_state.schema_uid = (
        "0x1234567890123456789012345678901234567890123456789012345678901234"
    )
    sync_state.last_block_number = 100
    sync_state.last_timestamp = 1000000
    sync_state.last_attestation_uid = None
    return sync_state


@pytest.mark.asyncio
async def test_initialize(mock_session_factory: MagicMock) -> None:
    """Test that the EAS service initializes correctly."""
    # Arrange
    service = EASIntegrationService(mock_session_factory)

    # Create a mock chain
    chain = Chain(
        chain_id=1,
        name="Test Chain",
        rpc_url="https://test.chain",
        eas_url="https://eas.test.chain",
        explorer_url="https://explorer.test.chain",
    )

    # Mock the session's execute method to return our mock chain
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [chain]
    mock_session = mock_session_factory.return_value.__aenter__.return_value
    mock_session.execute.return_value = mock_result

    # Mock the _get_schema_uid method
    schema_uid = "0x1234567890123456789012345678901234567890123456789012345678901234"
    with patch.object(
        service, "_get_schema_uid", new_callable=AsyncMock
    ) as mock_get_schema:
        mock_get_schema.return_value = schema_uid

        # Mock the _get_eas_endpoint method
        with patch.object(
            service, "_get_eas_endpoint", return_value="https://eas.test.chain"
        ):
            # Act
            await service.initialize()

            # Assert
            mock_session.execute.assert_called_once()
            assert 1 in service.clients
            assert service.schema_uids == {1: schema_uid}
            assert service.initialized is True


@pytest.mark.asyncio
async def test_get_or_create_sync_state_existing(
    mock_session_factory: MagicMock, mock_session: AsyncMock, mock_sync_state: MagicMock
) -> None:
    """Test getting an existing sync state."""
    # Mock session.execute to return our mock sync state
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_sync_state
    mock_session.execute.return_value = mock_result

    # Create service with mocked session factory
    service = EASIntegrationService(mock_session_factory)

    # Get the sync state
    result = await service._get_or_create_sync_state(
        mock_session, mock_sync_state.chain_id, mock_sync_state.schema_uid
    )

    # Verify that the result is our mock sync state
    assert result == mock_sync_state

    # Verify that the session was used correctly
    mock_session.execute.assert_called_once()
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_sync_state_new(
    mock_session_factory: MagicMock, mock_session: AsyncMock
) -> None:
    """Test creating a new sync state."""
    # Mock session.execute to return no sync state
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_result

    # Create service with mocked session factory
    service = EASIntegrationService(mock_session_factory)

    # Get the sync state (which should create a new one)
    chain_id = 1
    schema_uid = "0x1234567890123456789012345678901234567890123456789012345678901234"
    result = await service._get_or_create_sync_state(mock_session, chain_id, schema_uid)

    # Verify that a new sync state was created
    assert result is not None
    assert isinstance(result, SyncState)
    assert result.chain_id == chain_id
    assert result.schema_uid == schema_uid
    assert result.last_block_number == 0
    assert result.last_timestamp == 0
    assert result.last_attestation_uid is None

    # Verify that the session was used correctly
    mock_session.execute.assert_called_once()
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_query_attestations(mock_session_factory: MagicMock) -> None:
    """Test querying attestations from EAS API."""
    # Create service with mocked session factory
    service = EASIntegrationService(mock_session_factory)

    # Mock GraphQL client
    mock_client = MagicMock()
    mock_result = {
        "attestations": [
            {
                "id": "0xabc123",
                "attester": "0x1234567890123456789012345678901234567890",
                "recipient": "0x0987654321098765432109876543210987654321",
                "revoked": False,
                "revocationTime": None,
                "expirationTime": None,
                "time": "1000000",
                "data": "0x1234",
                "schemaId": (
                    "0x1234567890123456789012345678901234567890123456789012345678901234"
                ),
                "refUID": None,
                "txid": "0xdef456",
                "blockNumber": "101",
            }
        ]
    }
    mock_client.execute_async.return_value = mock_result

    # Query attestations
    schema_uid = "0x1234567890123456789012345678901234567890123456789012345678901234"
    last_block = 100
    last_timestamp = 1000000
    last_uid = None

    result = await service._query_attestations(
        mock_client, schema_uid, last_block, last_timestamp, last_uid
    )

    # Verify that the result is correct
    assert result == mock_result["attestations"]

    # Verify that the client was used correctly
    mock_client.execute_async.assert_called_once()

    # Verify that the query parameters are correct
    call_args = mock_client.execute_async.call_args[1]
    assert "variable_values" in call_args
    assert call_args["variable_values"]["schemaId"] == schema_uid
    assert "where" in call_args["variable_values"]
    where = call_args["variable_values"]["where"]
    assert where["schemaId"]["equals"] == schema_uid
    assert where["time"]["gt"] == str(last_timestamp)
    assert where["blockNumber"]["gt"] == str(last_block)


@pytest.mark.asyncio
async def test_parse_attestation_data(mock_session_factory: MagicMock) -> None:
    """Test parsing attestation data."""
    # Create service with mocked session factory
    service = EASIntegrationService(mock_session_factory)

    # Create a mock attestation
    attestation = {
        "id": "0xabc123",
        "data": "0x1234",
        # Other fields not relevant for this test
    }

    # Parse the attestation data
    result = service._parse_attestation_data(attestation)

    # Verify that the result is correct
    assert result is not None
    assert "srs" in result
    assert "spatial_type" in result
    assert "location_wkt" in result
    assert "recipe_type" in result
    assert "recipe_payload" in result
    assert "media_type" in result
    assert "media_data" in result
    assert "memo" in result

    # Verify that the WKT is valid
    assert result["location_wkt"] == "POINT(0 0)"


@pytest.mark.asyncio
async def test_sync_attestations_handles_errors(
    mock_session_factory: MagicMock,
) -> None:
    """Test that sync_attestations handles errors gracefully."""
    # Arrange
    service = EASIntegrationService(mock_session_factory)
    service.initialized = True

    # Mock the client to raise an exception
    mock_client = AsyncMock()
    mock_client.execute_async.side_effect = Exception("Test exception")
    service.clients = {1: mock_client}
    service.schema_uids = {1: "test-schema-uid"}

    # Act
    result = await service.sync_attestations([1])

    # Assert - no exception should be raised, and the function should return normally
    assert result == {1: 0}
