"""Health check endpoints for the Astral API."""

from typing import Dict

from fastapi import APIRouter

router = APIRouter(
    prefix="/health",
    tags=["Health"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=Dict[str, str])
async def health_check() -> Dict[str, str]:
    """Health check endpoint to verify API status.

    Returns:
        Dict[str, str]: A dictionary containing the status of the API
    """
    return {"status": "healthy"}
