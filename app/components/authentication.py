"""Web3 authentication endpoints for the Astral API."""

from typing import Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)


class NonceRequest(BaseModel):
    """Request model for nonce generation."""

    address: str = Field(..., description="Ethereum address requesting the nonce")


class SignatureVerification(BaseModel):
    """Request model for signature verification."""

    address: str = Field(..., description="Ethereum address that signed the message")
    signature: str = Field(..., description="Signature of the nonce")
    nonce: str = Field(..., description="Nonce that was signed")


@router.post("/nonce", response_model=Dict[str, str])
async def get_nonce(request: NonceRequest) -> Dict[str, str]:
    """Get a nonce for Web3 sign-in.

    Args:
        request: The request containing the Ethereum address

    Returns:
        Dict[str, str]: A dictionary containing the nonce to be signed
    """
    # TODO: Generate and store nonce for the address
    return {"nonce": "Please sign this message to verify your identity"}


@router.post("/verify", response_model=Dict[str, str])
async def verify_signature(verification: SignatureVerification) -> Dict[str, str]:
    """Verify a signed message for Web3 authentication.

    Args:
        verification: The request data for signature verification

    Returns:
        Dict[str, str]: A dictionary containing the JWT token

    Raises:
        HTTPException: If the signature verification fails
    """
    # TODO: Implement signature verification and JWT token generation
    return {"token": "dummy_jwt_token"}
