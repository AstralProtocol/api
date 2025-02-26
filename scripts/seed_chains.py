#!/usr/bin/env python
"""Seed script for populating the chain table with initial data.

Fetches data from ethereum-lists/chains repository.
Can be run multiple times to add new chains to an existing database.

Usage:
    python scripts/seed_chains.py                # Add default supported chains
    python scripts/seed_chains.py 100 137 10     # Add specific chain IDs
    python scripts/seed_chains.py --all          # Add all default chains
    python scripts/seed_chains.py --eas-file=f   # Use custom EAS endpoints
    python scripts/seed_chains.py --help         # Show help message

The EAS endpoints JSON file should have the following format:
{
    "1": "https://easscan.org/graphql",
    "137": "https://polygon.easscan.org/graphql"
}
Where the keys are chain IDs and the values are the GraphQL endpoints.
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

import aiohttp
import asyncpg

# Add the parent directory to the Python path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Chain IDs we want to support by default
DEFAULT_CHAIN_IDS = [
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

# Default EAS GraphQL endpoints for each chain
DEFAULT_EAS_ENDPOINTS = {
    1: "https://easscan.org/graphql",
    11155111: "https://sepolia.easscan.org/graphql",
    42220: "https://celo.easscan.org/graphql",
    8453: "https://base.easscan.org/graphql",
    42161: "https://arbitrum.easscan.org/graphql",
}


def load_eas_endpoints(file_path: Optional[str] = None) -> Dict[int, str]:
    """Load EAS endpoints from a JSON file if provided, otherwise use defaults."""
    if not file_path:
        return DEFAULT_EAS_ENDPOINTS

    try:
        with open(file_path, "r") as f:
            # Load the JSON file and convert string keys to integers
            custom_endpoints = json.load(f)
            return {int(k): v for k, v in custom_endpoints.items()}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading EAS endpoints file: {e}")
        print("Using default EAS endpoints instead.")
        return DEFAULT_EAS_ENDPOINTS


async def fetch_chain_data(
    session: aiohttp.ClientSession, chain_id: int
) -> Optional[Dict[str, Any]]:
    """Fetch chain data from ethereum-lists/chains repository."""
    url = BASE_URL.format(chain_id)
    async with session.get(url) as response:
        if response.status == 200:
            # Handle text/plain content type by parsing the text as JSON
            text = await response.text()
            try:
                data_dict: Dict[str, Any] = json.loads(text)
                return data_dict
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON for chain ID {chain_id}: {e}")
                return None
        else:
            print(f"Failed to fetch data for chain ID {chain_id}: {response.status}")
            return None


async def transform_chain_data(
    chain_data: Optional[Dict[str, Any]], chain_id: int, eas_endpoints: Dict[int, str]
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
    if chain_id in eas_endpoints:
        features.append({"name": "EAS", "url": eas_endpoints[chain_id]})

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


async def seed_chains(
    chain_ids: Optional[List[int]] = None,
    force_all: bool = False,
    eas_file: Optional[str] = None,
) -> None:
    """Seed the database with chain data from ethereum-lists/chains.

    This function is idempotent and can be run multiple times to add new chains.
    It will only add chains that don't already exist in the database.

    Args:
        chain_ids: List of chain IDs to add. If None, uses DEFAULT_CHAIN_IDS.
        force_all: If True, adds all specified chains even if they already exist.
        eas_file: Path to a JSON file containing custom EAS endpoints.
    """
    # Use default chain IDs if none provided
    chains_to_process = chain_ids if chain_ids is not None else DEFAULT_CHAIN_IDS

    # Load EAS endpoints
    eas_endpoints = load_eas_endpoints(eas_file)

    # Get database connection parameters from environment
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "astral")

    # Connect to the database
    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=db
    )

    try:
        # If force_all is True, we'll add all chains regardless of what exists
        if not force_all:
            # Check which chains already exist in the database
            existing_chains = await conn.fetch("SELECT chain_id FROM chain")
            existing_chain_ids = {row["chain_id"] for row in existing_chains}

            # Determine which chains need to be added
            chains_to_add = [
                chain_id
                for chain_id in chains_to_process
                if chain_id not in existing_chain_ids
            ]

            if not chains_to_add:
                print(
                    "All specified chains are already in the database. Nothing to add."
                )
                return

            print(
                f"Found {len(existing_chain_ids)} existing chains. "
                f"Adding {len(chains_to_add)} new chains."
            )
        else:
            # When force_all is True, add all specified chains
            chains_to_add = chains_to_process
            print(
                f"Force adding {len(chains_to_add)} chains "
                f"(will overwrite if they exist)."
            )

            # Delete existing chains that we're going to re-add
            for chain_id in chains_to_add:
                await conn.execute("DELETE FROM chain WHERE chain_id = $1", chain_id)

        # Fetch and transform chain data for chains that need to be added
        async with aiohttp.ClientSession() as http_session:
            tasks = [
                fetch_chain_data(http_session, chain_id) for chain_id in chains_to_add
            ]
            chain_data_list = await asyncio.gather(*tasks)

        # Transform the data
        transformed_chains = []
        for i, chain_data in enumerate(chain_data_list):
            chain_id = chains_to_add[i]
            transformed_data = await transform_chain_data(
                chain_data, chain_id, eas_endpoints
            )
            if transformed_data:
                transformed_chains.append(transformed_data)

        # Insert the chains
        for chain_data in transformed_chains:
            # Convert Python dictionaries to JSON strings for PostgreSQL
            rpc_json = json.dumps(chain_data["rpc"])
            faucets_json = json.dumps(chain_data["faucets"])
            native_currency_json = json.dumps(chain_data["native_currency"])
            features_json = json.dumps(chain_data["features"])
            explorers_json = json.dumps(chain_data["explorers"])

            # Insert using raw SQL
            await conn.execute(
                """
                INSERT INTO chain (
                    chain_id, name, chain, rpc, faucets, native_currency,
                    features, info_url, short_name, network_id, icon, explorers
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                chain_data["chain_id"],
                chain_data["name"],
                chain_data["chain"],
                rpc_json,
                faucets_json,
                native_currency_json,
                features_json,
                chain_data["info_url"],
                chain_data["short_name"],
                chain_data["network_id"],
                chain_data["icon"],
                explorers_json,
            )

        print(f"Successfully seeded {len(transformed_chains)} new chains.")

    finally:
        # Close the connection
        await conn.close()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Seed the database with chain data from ethereum-lists/chains."
    )
    parser.add_argument(
        "chain_ids",
        nargs="*",
        type=int,
        help="Chain IDs to add. If not provided, uses default supported chains.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Add all specified chains even if they already exist (will overwrite).",
    )
    parser.add_argument(
        "--eas-file",
        type=str,
        help="Path to a JSON file containing custom EAS endpoints.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    chain_ids = args.chain_ids if args.chain_ids else None
    asyncio.run(
        seed_chains(chain_ids=chain_ids, force_all=args.all, eas_file=args.eas_file)
    )
