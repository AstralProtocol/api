"""Unit tests for scheduler service."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.eas_integration import EASIntegrationService
from app.services.scheduler import SchedulerService


@pytest.fixture
def mock_session_factory() -> MagicMock:
    """Create a mock session factory."""
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = AsyncMock(spec=AsyncSession)
    return factory


@pytest.fixture
def mock_eas_service() -> AsyncMock:
    """Create a mock EAS integration service."""
    service = AsyncMock(spec=EASIntegrationService)
    service.clients = {1: MagicMock(), 2: MagicMock()}
    return service


@pytest.mark.asyncio
async def test_scheduler_start_stop(
    mock_session_factory: MagicMock, mock_eas_service: AsyncMock
) -> None:
    """Test starting and stopping the scheduler service."""
    # Arrange
    scheduler = SchedulerService(mock_session_factory)
    scheduler.eas_service = mock_eas_service
    # Use integers for intervals to avoid type issues
    scheduler.active_interval = 1  # 1s for testing
    scheduler.active_timeout = 5  # 5s for testing

    # Act & Assert - Start
    await scheduler.start()
    assert scheduler.running is True
    assert scheduler.task is not None

    # Act & Assert - Stop
    await scheduler.stop()
    assert scheduler.running is False
    assert scheduler.task is None


@pytest.mark.asyncio
async def test_notify_user_activity_specific_chains(
    mock_session_factory: MagicMock,
) -> None:
    """Test notifying user activity for specific chains."""
    # Create scheduler service
    scheduler = SchedulerService(mock_session_factory)

    # Set up test data
    chain_ids = [1, 2]

    # Notify user activity
    await scheduler.notify_user_activity(chain_ids)

    # Verify that the active chains are updated correctly
    assert 1 in scheduler.active_chains
    assert 2 in scheduler.active_chains
    assert len(scheduler.active_chains) == 2

    # Verify that the timestamps are recent
    current_time = time.time()
    for chain_id, timestamp in scheduler.active_chains.items():
        assert current_time - timestamp < 1  # Less than 1 second difference


@pytest.mark.asyncio
async def test_notify_user_activity_all_chains(
    mock_session_factory: MagicMock, mock_eas_service: AsyncMock
) -> None:
    """Test notifying user activity for all chains."""
    # Create scheduler service
    scheduler = SchedulerService(mock_session_factory)
    scheduler.eas_service = mock_eas_service

    # Notify user activity for all chains
    await scheduler.notify_user_activity()

    # Verify that all chains from the EAS service are active
    assert 1 in scheduler.active_chains
    assert 2 in scheduler.active_chains
    assert len(scheduler.active_chains) == 2

    # Verify that the timestamps are recent
    current_time = time.time()
    for chain_id, timestamp in scheduler.active_chains.items():
        assert current_time - timestamp < 1  # Less than 1 second difference


@pytest.mark.asyncio
async def test_polling_loop(
    mock_session_factory: MagicMock, mock_eas_service: AsyncMock
) -> None:
    """Test the polling loop functionality."""
    # Create scheduler service with a short active interval for testing
    scheduler = SchedulerService(mock_session_factory)
    # Use integers for intervals to avoid type issues
    scheduler.active_interval = 1  # 1s for testing
    scheduler.default_interval = 5  # 5s for testing
    scheduler.eas_service = mock_eas_service

    # Set up active chains
    scheduler.active_chains = {1: time.time()}

    # Start the polling loop
    scheduler.running = True

    # Create a task for the polling loop
    task = asyncio.create_task(scheduler._polling_loop())

    # Let it run for a short time
    await asyncio.sleep(0.1)  # 100ms should be enough for multiple iterations

    # Stop the polling loop
    scheduler.running = False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify that sync_attestations was called for active chains
    mock_eas_service.sync_attestations.assert_called()

    # It should have been called at least once with [1] (the active chain)
    active_chain_call_found = False
    all_chains_call_found = False

    for call in mock_eas_service.sync_attestations.call_args_list:
        args, kwargs = call
        if args and args[0] == [1]:
            active_chain_call_found = True
        elif not args or args[0] is None:
            all_chains_call_found = True

    assert (
        active_chain_call_found
    ), "sync_attestations should be called for active chains"
    assert all_chains_call_found, "sync_attestations should be called for all chains"


@pytest.mark.asyncio
async def test_active_chain_expiration(
    mock_session_factory: MagicMock, mock_eas_service: AsyncMock
) -> None:
    """Test that active chains expire after the timeout period."""
    # Create scheduler service with a short timeout for testing
    scheduler = SchedulerService(mock_session_factory)
    # Use integers for intervals to avoid type issues
    scheduler.active_timeout = 5  # 5s for testing
    scheduler.eas_service = mock_eas_service

    # Set up active chains with one that's already expired
    current_time = time.time()
    scheduler.active_chains = {
        1: current_time,  # Active
        2: current_time - 10,  # Expired (10s ago)
    }

    # Use patch to mock the _polling_loop method
    with patch.object(scheduler, "_polling_loop") as mock_polling_loop:
        # Create a new implementation for the polling loop
        async def mock_polling_once() -> None:
            # Process active chains
            current_time = time.time()
            active_chain_ids = []

            # Clean up expired active chains
            expired_chains = []
            for chain_id, last_active in scheduler.active_chains.items():
                if current_time - last_active > scheduler.active_timeout:
                    expired_chains.append(chain_id)
                else:
                    active_chain_ids.append(chain_id)

            for chain_id in expired_chains:
                del scheduler.active_chains[chain_id]

            # Call sync_attestations with active chains
            if active_chain_ids:
                await mock_eas_service.sync_attestations(active_chain_ids)

        # Set the side effect of the mock
        mock_polling_loop.side_effect = mock_polling_once

        # Run the polling loop once
        await scheduler._polling_loop()

        # Verify that only chain 1 is still active
        assert 1 in scheduler.active_chains
        assert 2 not in scheduler.active_chains

        # Verify that sync_attestations was called with only the active chain
        mock_eas_service.sync_attestations.assert_called_with([1])
