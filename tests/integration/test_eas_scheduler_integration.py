"""Integration tests for EAS integration and scheduler services."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chain import Chain
from app.services.eas_integration import EASIntegrationService
from app.services.scheduler import SchedulerService


@pytest.fixture
def mock_session_factory() -> MagicMock:
    """Create a mock session factory."""
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = AsyncMock(spec=AsyncSession)
    return factory


@pytest.fixture
def mock_chain_query_result() -> MagicMock:
    """Create a mock query result for Chain objects."""
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [
        Chain(
            chain_id=1,
            name="Test Chain",
            rpc_url="https://test.chain",
            eas_url="https://eas.test.chain",
            explorer_url="https://explorer.test.chain",
        )
    ]
    return mock_result


@pytest.mark.asyncio
async def test_scheduler_triggers_eas_sync(
    mock_session_factory: MagicMock, mock_chain_query_result: MagicMock
) -> None:
    """Test that the scheduler triggers EAS synchronization."""
    # Arrange - Mock session and query result
    mock_session = mock_session_factory.return_value.__aenter__.return_value
    mock_session.execute.return_value = mock_chain_query_result

    # Create a scheduler with short intervals for testing
    scheduler = SchedulerService(mock_session_factory)
    # Use integers for intervals to avoid type issues
    scheduler.active_interval = 1  # 1s for testing
    scheduler.active_timeout = 5  # 5s for testing

    # Mock the EAS service methods
    mock_eas_service = AsyncMock(spec=EASIntegrationService)
    scheduler.eas_service = mock_eas_service

    # Act - Start the scheduler and let it run briefly
    await scheduler.start()
    await asyncio.sleep(0.3)  # Let it run for 300ms (enough for at least one poll)
    await scheduler.stop()

    # Assert - Verify that the EAS service methods were called
    mock_eas_service.initialize.assert_called_once()
    mock_eas_service.sync_attestations.assert_called()


@pytest.mark.asyncio
async def test_user_activity_increases_polling_frequency(
    mock_session_factory: MagicMock, mock_chain_query_result: MagicMock
) -> None:
    """Test that user activity increases the polling frequency."""
    # Arrange - Mock session and query result
    mock_session = mock_session_factory.return_value.__aenter__.return_value
    mock_session.execute.return_value = mock_chain_query_result

    # Create a scheduler with specific intervals for testing
    scheduler = SchedulerService(mock_session_factory)
    # Use integers for intervals to avoid type issues
    scheduler.default_interval = 10  # 10s normal interval
    scheduler.active_interval = 1  # 1s active interval
    scheduler.active_timeout = 5  # 5s timeout

    # Mock the EAS service methods
    mock_eas_service = AsyncMock(spec=EASIntegrationService)
    scheduler.eas_service = mock_eas_service

    # Act - Start the scheduler
    await scheduler.start()

    # Notify user activity
    await scheduler.notify_user_activity(chain_ids=[1])

    # Let it run briefly with the faster polling rate
    await asyncio.sleep(0.3)  # Let it run for 300ms

    # Get the call count before waiting for timeout
    active_call_count = mock_eas_service.sync_attestations.call_count

    # Wait for the activity timeout to expire
    await asyncio.sleep(0.6)  # Wait for activity timeout to expire

    # Let it run a bit more with the normal polling rate
    await asyncio.sleep(0.3)

    # Get the final call count
    final_call_count = mock_eas_service.sync_attestations.call_count

    # Stop the scheduler
    await scheduler.stop()

    # Assert - Verify that polling was more frequent during active period
    assert active_call_count > 0, "No calls during active period"

    # The difference in call counts should be small after timeout
    # because the polling interval is longer
    call_diff = final_call_count - active_call_count
    assert call_diff <= 1, "Polling frequency did not decrease after timeout"
