"""Chain schemas for request/response validation."""

from typing import Dict, List

from pydantic import Field

from app.schemas.base import BaseSchema, TimestampedSchema


class ChainBase(BaseSchema):
    """Shared properties for chain schemas."""

    chain_id: int = Field(
        ...,
        description="Unique identifier for the blockchain network",
    )
    name: str = Field(
        ...,
        description='Full name of the blockchain network (e.g., "Ethereum Mainnet")',
    )
    chain: str = Field(..., description='Abbreviated chain symbol (e.g., "ETH")')
    rpc: List[str] = Field(
        default_factory=list,
        description="Array of RPC endpoint URLs",
    )
    faucets: List[str] = Field(
        default_factory=list,
        description="Array of faucet URLs (if any)",
    )
    native_currency: Dict[str, str | int] = Field(
        ...,
        description="JSON object containing native currency details",
        examples=[
            {
                "name": "Ether",
                "symbol": "ETH",
                "decimals": 18,
            }
        ],
    )
    features: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Array of feature objects",
        examples=[[{"name": "EIP155"}, {"name": "EIP1559"}]],
    )
    info_url: str | None = Field(
        None,
        description="URL for more information about the blockchain network",
    )
    short_name: str = Field(..., description="Short name for display purposes")
    network_id: int = Field(..., description="Network identifier")
    icon: str = Field(..., description="Identifier for an icon (useful for UI display)")
    explorers: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Array of blockchain explorer objects",
        examples=[
            [
                {
                    "name": "etherscan",
                    "url": "https://etherscan.io",
                    "icon": "etherscan",
                    "standard": "EIP3091",
                }
            ]
        ],
    )
    rpc_urls: list[str] = Field(
        default=[],
        description="List of RPC URLs for the chain",
        examples=["https://mainnet.infura.io/v3/YOUR-PROJECT-ID"],
    )
    explorer_urls: list[str] = Field(
        default=[],
        description="List of block explorer URLs for the chain",
        examples=["https://etherscan.io"],
    )
    contract_addresses: list[str] = Field(
        default=[],
        description="List of contract addresses for the chain",
        examples=["0x1234567890123456789012345678901234567890"],
    )


class ChainCreate(ChainBase):
    """Properties to receive on chain creation."""

    pass


class ChainUpdate(ChainBase):
    """Properties to receive on chain update."""

    pass


class Chain(ChainBase, TimestampedSchema):
    """Properties to return to client."""

    pass


class ChainInDB(Chain):
    """Additional properties stored in DB."""

    pass
