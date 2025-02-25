"""Main application module for Astral API."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.components.authentication import router as authentication_router
from app.components.health import router as health_router
from app.components.location_proofs import router as location_proofs_router
from app.database import get_session
from app.services.scheduler import SchedulerService

# Global scheduler instance
scheduler: Optional[SchedulerService] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan events.

    This function handles startup and shutdown events for the FastAPI application.
    It initializes and starts the scheduler service on startup,
    and stops it on shutdown.
    """
    # Initialize and start the scheduler on startup
    global scheduler
    scheduler = SchedulerService(get_session)
    await scheduler.start()

    yield

    # Stop the scheduler on shutdown
    if scheduler:
        await scheduler.stop()


app = FastAPI(
    title="Astral API",
    description="A decentralized geospatial data API with EAS integration",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(
    location_proofs_router, prefix=""
)  # Mount at root for OGC API compliance
app.include_router(authentication_router)


# Dependency to get the scheduler instance
def get_scheduler() -> SchedulerService:
    """Get the global scheduler instance."""
    if scheduler is None:
        raise RuntimeError("Scheduler not initialized")
    return scheduler


# Endpoint to notify user activity
@app.post("/internal/notify-user-activity")
async def notify_user_activity(
    chain_ids: Optional[List[int]] = None,
    scheduler: SchedulerService = Depends(get_scheduler),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, str]:
    """Notify the scheduler of user activity to increase polling frequency.

    Args:
        chain_ids: List of chain IDs to increase polling frequency for,
                  or None for all chains
        scheduler: The scheduler service instance
        session: SQLAlchemy async session

    Returns:
        A message indicating success
    """
    await scheduler.notify_user_activity(chain_ids)
    return {"message": "Polling frequency increased due to user activity"}
