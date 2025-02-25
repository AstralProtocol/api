"""Scheduler Service for the Astral API.

This module provides a scheduler service that periodically polls the EAS GraphQL
endpoint for new attestations and updates the database accordingly.
"""

import asyncio
import time
from logging import getLogger
from typing import Dict, List, Optional

from app.database import SessionFactory
from app.services.eas_integration import EASIntegrationService

# Configure logging
logger = getLogger(__name__)


class SchedulerService:
    """Service for scheduling periodic tasks.

    This service manages periodic polling of EAS GraphQL endpoints for new
    attestations, with configurable polling frequencies.
    """

    def __init__(self, get_session: SessionFactory):
        """Initialize the scheduler service.

        Args:
            get_session: Function that returns an AsyncSession
        """
        self.get_session = get_session
        self.eas_service = EASIntegrationService(get_session)
        self.running = False
        self.task: Optional[asyncio.Task] = None

        # Default polling intervals (in seconds)
        self.default_interval = 60  # 1 minute
        self.active_interval = 10  # 10 seconds

        # Track active chains (with increased polling frequency)
        self.active_chains: Dict[int, float] = {}
        self.active_timeout = 300  # 5 minutes

    async def start(self) -> None:
        """Start the scheduler service."""
        if self.running:
            return

        self.running = True

        # Initialize EAS service
        await self.eas_service.initialize()

        # Start polling task
        self.task = asyncio.create_task(self._polling_loop())
        logger.info("Scheduler service started")

    async def stop(self) -> None:
        """Stop the scheduler service."""
        if not self.running:
            return

        self.running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

        logger.info("Scheduler service stopped")

    async def notify_user_activity(self, chain_ids: Optional[List[int]] = None) -> None:
        """Notify the scheduler of user activity to increase polling frequency.

        Args:
            chain_ids: List of chain IDs to increase polling frequency for,
                      or None for all chains
        """
        current_time = time.time()

        if chain_ids:
            # Update specific chains
            for chain_id in chain_ids:
                self.active_chains[chain_id] = current_time
        else:
            # Get all chain IDs from EAS service
            all_chains = set(self.eas_service.clients.keys())
            for chain_id in all_chains:
                self.active_chains[chain_id] = current_time

        logger.info(
            f"Polling frequency increased for chains: {list(self.active_chains.keys())}"
        )

    async def _polling_loop(self) -> None:
        """Main polling loop that runs periodically."""
        while self.running:
            try:
                # Determine which chains to poll with higher frequency
                current_time = time.time()
                active_chain_ids = []

                # Clean up expired active chains
                expired_chains = []
                for chain_id, last_active in self.active_chains.items():
                    if current_time - last_active > self.active_timeout:
                        expired_chains.append(chain_id)
                    else:
                        active_chain_ids.append(chain_id)

                for chain_id in expired_chains:
                    del self.active_chains[chain_id]

                # Poll active chains first (higher frequency)
                if active_chain_ids:
                    logger.info(f"Polling active chains: {active_chain_ids}")
                    await self.eas_service.sync_attestations(active_chain_ids)

                # Poll all chains periodically (lower frequency)
                # We use a counter to avoid polling all chains too frequently
                if not hasattr(self, "_poll_counter"):
                    self._poll_counter = 0

                self._poll_counter += 1
                if self._poll_counter >= (
                    self.default_interval // self.active_interval
                ):
                    logger.info("Polling all chains")
                    await self.eas_service.sync_attestations()
                    self._poll_counter = 0

                # Sleep until next poll
                await asyncio.sleep(self.active_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                # Sleep a bit longer on error to avoid rapid retries
                await asyncio.sleep(self.active_interval * 2)
