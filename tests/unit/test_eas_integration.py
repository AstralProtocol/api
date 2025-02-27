"""Unit tests for EAS integration service."""

from typing import Any, AsyncGenerator, Optional, Sequence
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from eth_abi import encode
from gql import Client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chain import Chain
from app.models.sync_state import SyncState
from app.services.eas_integration import EASIntegrationService
from app.services.schema_encoder import SchemaEncoder


@pytest.fixture
async def mock_session() -> AsyncMock:
    """Create a mock async session for testing.

    Returns:
        AsyncMock: A mock async session for testing
    """
    return AsyncMock(spec=AsyncSession)


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
async def test_fetch_chains(mock_session_factory: MagicMock) -> None:
    """Test that chains can be fetched from the database."""
    # Create service
    service = EASIntegrationService(mock_session_factory)

    # Create a simple mock chain
    chain = Chain(
        chain_id=1,
        name="Test Chain",
        features={
            "features": [{"name": "EAS", "graphql": "https://eas.test.chain/graphql"}]
        },
    )

    # Set up simple session mock that returns our chain
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = [chain]
    mock_session.execute.return_value = mock_result

    # Set up session factory to yield our session
    async def mock_factory() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    mock_session_factory.return_value = mock_factory()

    # Call the private method directly to test chain fetching
    async for session in service.get_session():
        query = select(Chain)
        result = await session.execute(query)
        result_scalar = result.scalars()
        chains: Sequence[Chain] = result_scalar.all()

        # Verify we got our chain
        assert len(chains) == 1
        assert chains[0].chain_id == 1
        assert chains[0].name == "Test Chain"


@pytest.mark.asyncio
async def test_create_graphql_client(
    mock_session_factory: MagicMock, mock_chain: Chain
) -> Client:
    """Test that GraphQL clients are created correctly.

    Args:
        mock_session_factory: Mock session factory
        mock_chain: Mock chain object

    Returns:
        Client: The created GraphQL client
    """
    service = EASIntegrationService(mock_session_factory)

    # Mock the client
    mock_client = MagicMock(
        spec=Client
    )  # Changed to MagicMock since we don't need async

    with (
        patch(
            "app.services.eas_integration.AIOHTTPTransport", autospec=True
        ) as mock_transport_class,
        patch("app.services.eas_integration.Client", return_value=mock_client),
    ):

        # Test client creation directly
        endpoint = "https://eas.test.chain/graphql"
        result = service._create_graphql_client(endpoint)

        # Verify transport and client were created correctly
        assert result == mock_client
        # Verify transport was created with correct URL
        mock_transport_class.assert_called_once_with(url=endpoint)

        return result


@pytest.mark.asyncio
async def test_get_schema_uid(mock_session_factory: MagicMock) -> Optional[str]:
    """Test fetching schema UID.

    Args:
        mock_session_factory: Mock session factory

    Returns:
        Optional[str]: The fetched schema UID
    """
    service = EASIntegrationService(mock_session_factory)

    # Create mock client
    mock_client = AsyncMock()
    schema_uid = "0x1234567890123456789012345678901234567890123456789012345678901234"
    mock_client.execute_async.return_value = {"schemas": [{"uid": schema_uid}]}

    # Add mock client to service
    service.clients[1] = mock_client

    # Test schema UID fetching
    result: Optional[str] = await service._get_schema_uid(1)
    assert result == schema_uid
    mock_client.execute_async.assert_called_once()

    return result


@pytest.mark.asyncio
async def test_full_initialization(
    mock_session_factory: MagicMock, caplog: Any
) -> None:
    """Test the full initialization process with minimal mocking.

    Args:
        mock_session_factory: Mock session factory
        caplog: Pytest fixture for capturing log output
    """
    import logging

    caplog.set_level(logging.INFO)

    # Create service
    service = EASIntegrationService(mock_session_factory)

    # Create minimal chain
    chain = Chain(
        chain_id=1,
        name="Test Chain",
        features={
            "features": [{"name": "EAS", "graphql": "https://eas.test.chain/graphql"}]
        },
    )

    # Simple session mock
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [chain]
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    async def mock_factory() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    mock_session_factory.return_value = mock_factory()

    # Mock GraphQL client and transport
    mock_client = AsyncMock()
    mock_client.execute_async.return_value = {"schemas": [{"uid": "0x1234"}]}

    with (
        patch("app.services.eas_integration.Client", return_value=mock_client),
        patch("app.services.eas_integration.AIOHTTPTransport"),
    ):

        # Run initialization
        await service.initialize()

        # Verify service state
        assert service.initialized
        assert 1 in service.clients
        assert 1 in service.schema_uids
        assert service.schema_uids[1] == "0x1234"


@pytest.mark.asyncio
async def test_get_or_create_sync_state_existing(
    mock_session_factory: MagicMock, mock_session: AsyncMock, mock_sync_state: MagicMock
) -> None:
    """Test getting an existing sync state.

    Args:
        mock_session_factory: Mock session factory
        mock_session: Mock async session
        mock_sync_state: Mock sync state object
    """
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

    # Create mock result
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

    # Create mock client with async execute method
    mock_client = AsyncMock()
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

    # Verify that execute_async was called with the correct parameters
    mock_client.execute_async.assert_called_once()
    call_args = mock_client.execute_async.call_args
    assert len(call_args[0]) == 1  # First argument should be the query
    assert call_args[1]["variable_values"] == {
        "where": {
            "schemaId": {"equals": schema_uid},
            "time": {"gt": str(last_timestamp)},
            "blockNumber": {"gt": str(last_block)},
        }
    }


@pytest.mark.asyncio
async def test_parse_attestation_data(mock_session_factory: MagicMock) -> None:
    """Test parsing attestation data."""
    # Create service with mocked session factory
    service = EASIntegrationService(mock_session_factory)

    # Create test data matching our schema
    test_data = (
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
    encoded_bytes = encode(SchemaEncoder.SCHEMA_TYPES, test_data)
    encoded_hex = "0x" + encoded_bytes.hex()

    # Create a mock attestation with the encoded data
    attestation = {
        "id": "0xabc123",
        "data": encoded_hex,
    }

    # Parse the attestation data
    result = service._parse_attestation_data(attestation)

    # Verify that the result is correct
    assert result is not None
    assert result["eventTimestamp"] == 1234567890
    assert result["srs"] == "EPSG:4326"
    assert result["locationType"] == "Point"
    assert result["location"] == "40.7128,-74.0060"
    assert result["recipeType"] == ["recipe1"]
    assert result["recipePayload"] == [b"payload1"]
    assert result["mediaType"] == ["image/jpeg"]
    assert result["mediaData"] == ["data1"]
    assert result["memo"] == "Test memo"


@pytest.mark.asyncio
async def test_parse_attestation_data_invalid(mock_session_factory: MagicMock) -> None:
    """Test parsing invalid attestation data."""
    service = EASIntegrationService(mock_session_factory)

    # Test with missing data field
    attestation_no_data = {"id": "0xabc123"}
    result = service._parse_attestation_data(attestation_no_data)
    assert result is None

    # Test with invalid hex string
    attestation_invalid_hex = {"id": "0xabc123", "data": "0xNOTHEX"}
    result = service._parse_attestation_data(attestation_invalid_hex)
    assert result is None

    # Test with invalid data format
    attestation_invalid_format = {
        "id": "0xabc123",
        "data": 12345,  # Not a string or bytes
    }
    result = service._parse_attestation_data(attestation_invalid_format)
    assert result is None


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


@pytest.mark.asyncio
async def test_initialize_no_chains(mock_session: AsyncMock) -> None:
    """Test initialization with no chains in database."""
    # Setup mock session to return empty result
    mock_session.execute.return_value.scalars.return_value.all.return_value = []

    # Create service
    service = EASIntegrationService(lambda: mock_session)
    await service.initialize()

    # Verify no clients were created
    assert len(service.clients) == 0
    assert len(service.schema_uids) == 0


@pytest.mark.asyncio
async def test_initialize_with_chains(mock_session: AsyncMock) -> None:
    """Test initialization with chains in database."""
    # Setup mock chain data
    mock_chain = Chain(
        chain_id=1,
        name="Test Chain",
        features=[{"name": "EAS", "url": "http://test.com/graphql"}],
    )
    mock_session.execute.return_value.scalars.return_value.all.return_value = [
        mock_chain
    ]

    # Mock GQL client creation
    mock_client = MagicMock(spec=Client)
    mock_client.execute_async.return_value = {"schemas": [{"uid": "test-schema"}]}

    with patch("app.services.eas_integration.Client", return_value=mock_client):
        # Create service
        service = EASIntegrationService(lambda: mock_session)
        await service.initialize()

        # Verify client was created
        assert len(service.clients) == 1
        assert 1 in service.clients
        assert service.schema_uids[1] == "test-schema"


@pytest.mark.asyncio
async def test_sync_attestations_new_chain(mock_session: AsyncMock) -> None:
    """Test syncing attestations for a new chain."""
    # Setup mock chain data
    mock_chain = Chain(
        chain_id=1,
        name="Test Chain",
        features=[{"name": "EAS", "url": "http://test.com/graphql"}],
    )
    mock_session.execute.return_value.scalars.return_value.all.return_value = [
        mock_chain
    ]

    # Mock GQL client
    mock_client = MagicMock(spec=Client)
    mock_client.execute_async.side_effect = [
        {"schemas": [{"uid": "test-schema"}]},  # First call for schema UID
        {  # Second call for attestations
            "attestations": [
                {
                    "id": "test-id",
                    "attester": "0x123",
                    "recipient": "0x456",
                    "time": "1234567890",
                    "blockNumber": "100",
                    "data": "0x0",
                }
            ]
        },
    ]

    # Mock sync state query to return None (new chain)
    mock_session.execute.return_value.scalars.return_value.first.return_value = None

    with patch("app.services.eas_integration.Client", return_value=mock_client):
        # Create service
        service = EASIntegrationService(lambda: mock_session)
        await service.initialize()

        # Sync attestations
        result = await service.sync_attestations([1])

        # Verify sync state was created
        sync_state_query = select(SyncState).where(
            SyncState.chain_id == 1, SyncState.schema_uid == "test-schema"
        )
        mock_session.execute.assert_called_with(sync_state_query)

        # Verify result
        assert result == {1: 1}


@pytest.mark.asyncio
async def test_sync_attestations_existing_chain(mock_session: AsyncMock) -> None:
    """Test syncing attestations for an existing chain."""
    # Setup mock chain data
    mock_chain = Chain(
        chain_id=1,
        name="Test Chain",
        features=[{"name": "EAS", "url": "http://test.com/graphql"}],
    )
    mock_session.execute.return_value.scalars.return_value.all.return_value = [
        mock_chain
    ]

    # Mock existing sync state
    mock_sync_state = SyncState(
        chain_id=1,
        schema_uid="test-schema",
        last_block_number=50,
        last_timestamp=1234567800,
        last_attestation_uid="prev-id",
    )
    mock_session.execute.return_value.scalars.return_value.first.return_value = (
        mock_sync_state
    )

    # Mock GQL client
    mock_client = MagicMock(spec=Client)
    mock_client.execute_async.side_effect = [
        {"schemas": [{"uid": "test-schema"}]},  # First call for schema UID
        {  # Second call for attestations
            "attestations": [
                {
                    "id": "test-id-2",
                    "attester": "0x789",
                    "recipient": "0xabc",
                    "time": "1234567890",
                    "blockNumber": "100",
                    "data": "0x0",
                }
            ]
        },
    ]

    with patch("app.services.eas_integration.Client", return_value=mock_client):
        # Create service
        service = EASIntegrationService(lambda: mock_session)
        await service.initialize()

        # Sync attestations
        result = await service.sync_attestations([1])

        # Verify sync state was updated
        assert mock_sync_state.last_block_number == 100
        assert mock_sync_state.last_timestamp == 1234567890
        assert mock_sync_state.last_attestation_uid == "test-id-2"

        # Verify result
        assert result == {1: 1}


@pytest.mark.asyncio
async def test_initialize_empty_features(mock_session: AsyncMock) -> None:
    """Test initialization with chain that has empty features."""
    # Setup mock chain with empty features
    mock_chain = Chain(chain_id=1, name="Test Chain", features=[])
    mock_session.execute.return_value.scalars.return_value.all.return_value = [
        mock_chain
    ]

    # Create service
    service = EASIntegrationService(lambda: mock_session)
    await service.initialize()

    # Verify no clients were created
    assert len(service.clients) == 0
    assert len(service.schema_uids) == 0


@pytest.mark.asyncio
async def test_initialize_no_eas_feature(mock_session: AsyncMock) -> None:
    """Test initialization with chain that has no EAS feature."""
    # Setup mock chain with non-EAS feature
    mock_chain = Chain(
        chain_id=1,
        name="Test Chain",
        features=[{"name": "Other", "url": "http://test.com"}],
    )
    mock_session.execute.return_value.scalars.return_value.all.return_value = [
        mock_chain
    ]

    # Create service
    service = EASIntegrationService(lambda: mock_session)
    await service.initialize()

    # Verify no clients were created
    assert len(service.clients) == 0
    assert len(service.schema_uids) == 0


@pytest.mark.asyncio
async def test_initialize_no_schema_uid(mock_session: AsyncMock) -> None:
    """Test initialization when no schema UID is found."""
    # Setup mock chain data
    mock_chain = Chain(
        chain_id=1,
        name="Test Chain",
        features=[{"name": "EAS", "url": "http://test.com/graphql"}],
    )
    mock_session.execute.return_value.scalars.return_value.all.return_value = [
        mock_chain
    ]

    # Mock GQL client to return no schemas
    mock_client = MagicMock(spec=Client)
    mock_client.execute_async.return_value = {"schemas": []}

    with patch("app.services.eas_integration.Client", return_value=mock_client):
        # Create service
        service = EASIntegrationService(lambda: mock_session)
        await service.initialize()

        # Verify no clients were created (should be removed when no schema found)
        assert len(service.clients) == 0
        assert len(service.schema_uids) == 0


@pytest.mark.asyncio
async def test_sync_attestations_no_clients(mock_session: AsyncMock) -> None:
    """Test syncing attestations when no clients are initialized."""
    # Create service without initializing
    service = EASIntegrationService(lambda: mock_session)

    # Attempt to sync attestations
    result = await service.sync_attestations([1])

    # Assert - no exception should be raised, and the function should return normally
    assert result == {1: 0}
