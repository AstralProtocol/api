#!/usr/bin/env python
"""Seed script for populating the chain table with initial data.

Fetches data from ethereum-lists/chains repository.
"""

import asyncio
import os
from typing import Any, Dict, Optional

import aiohttp
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import the Chain model
from app.models.chain import Chain

# Get database URL from environment or use default
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/astral"
)

# Create async engine and session
engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False  # type: ignore
)

# Chain IDs we want to support
SUPPORTED_CHAIN_IDS = [
    1,  # Ethereum Mainnet
    11155111,  # Sepolia
    42220,  # Celo Mainnet
    8453,  # Base Mainnet
    42161,  # Arbitrum One
]

# Base URL for ethereum-lists/chains repository
BASE_URL = (
    "https://raw.githubusercontent.com/ethereum-lists/chains/master/"
    "_data/chains/eip155-{}.json"
)

# EAS GraphQL endpoints for each chain
EAS_ENDPOINTS = {
    1: "https://easscan.org/graphql",
    11155111: "https://sepolia.easscan.org/graphql",
    42220: "https://celo.easscan.org/graphql",
    8453: "https://base.easscan.org/graphql",
    42161: "https://arbitrum.easscan.org/graphql",
}


async def fetch_chain_data(
    session: aiohttp.ClientSession, chain_id: int
) -> Optional[Dict[str, Any]]:
    """Fetch chain data from ethereum-lists/chains repository."""
    url = BASE_URL.format(chain_id)
    async with session.get(url) as response:
        if response.status == 200:
            data_dict: Dict[str, Any] = await response.json()
            return data_dict
        else:
            print(f"Failed to fetch data for chain ID {chain_id}: {response.status}")
            return None


async def transform_chain_data(
    chain_data: Optional[Dict[str, Any]], chain_id: int
) -> Optional[Dict[str, Any]]:
    """Transform the raw chain data to match our Chain model structure."""
    if not chain_data:
        return None

    # Extract and transform the data
    features = []
    for feature in chain_data.get("features", []):
        if isinstance(feature, str):
            features.append({"name": feature})
        else:
            features.append(feature)

    # Add EAS feature if we have an endpoint for this chain
    if chain_id in EAS_ENDPOINTS:
        features.append({"name": "EAS", "url": EAS_ENDPOINTS[chain_id]})

    # Transform explorers
    explorers = []
    for explorer in chain_data.get("explorers", []):
        explorers.append(
            {
                "name": explorer.get("name", ""),
                "url": explorer.get("url", ""),
                "icon": explorer.get("name", "").lower(),
                "standard": explorer.get("standard", ""),
            }
        )

    # Create the transformed data
    transformed_data: Dict[str, Any] = {
        "chain_id": int(chain_data.get("chainId", chain_id)),
        "name": chain_data.get("name", ""),
        "chain": chain_data.get("shortName", "").upper(),
        "rpc": {"urls": chain_data.get("rpc", [])},
        "faucets": chain_data.get("faucets", []),
        "native_currency": chain_data.get("nativeCurrency", {}),
        "features": features,
        "info_url": chain_data.get("infoURL", ""),
        "short_name": chain_data.get("shortName", "").lower(),
        "network_id": int(chain_data.get("networkId", 0)),
        "icon": chain_data.get("shortName", "").lower(),
        "explorers": explorers,
    }

    return transformed_data


async def seed_chains() -> None:
    """Seed the database with chain data from ethereum-lists/chains."""
    async with engine.begin() as conn:
        # Check if chains already exist
        result = await conn.execute(text("SELECT COUNT(*) FROM chain"))
        count = result.scalar()

        if count is not None and count > 0:
            print(f"Database already has {count} chains. Skipping seed.")
            return

    # Fetch and transform chain data
    async with aiohttp.ClientSession() as http_session:
        tasks = [
            fetch_chain_data(http_session, chain_id) for chain_id in SUPPORTED_CHAIN_IDS
        ]
        chain_data_list = await asyncio.gather(*tasks)

    # Transform the data
    transformed_chains = []
    for i, chain_data in enumerate(chain_data_list):
        chain_id = SUPPORTED_CHAIN_IDS[i]
        transformed_data = await transform_chain_data(chain_data, chain_id)
        if transformed_data:
            transformed_chains.append(transformed_data)

    # Insert into database
    async with async_session() as session:
        for chain_data in transformed_chains:
            chain = Chain(**chain_data)
            session.add(chain)

        await session.commit()
        print(f"Successfully seeded {len(transformed_chains)} chains.")


if __name__ == "__main__":
    asyncio.run(seed_chains())
