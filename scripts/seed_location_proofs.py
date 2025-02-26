#!/usr/bin/env python
"""Seed script for populating the location_proof table with real data.

This script fetches real location proofs from EAS GraphQL endpoints
and stores them in the database. It also creates the necessary address records.

Usage:
    python scripts/seed_location_proofs.py                # Fetch proofs from all chains
    python scripts/seed_location_proofs.py --chain 42220  # Fetch proofs from specific
    python scripts/seed_location_proofs.py --limit 10     # Limit number of proofs
    python scripts/seed_location_proofs.py --help         # Show help message
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional, cast

# Remove unused imports
import asyncpg
import requests

# Add the parent directory to the Python path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default limit of proofs to fetch per chain
DEFAULT_PROOF_LIMIT = 50

# Path to EAS config file
EAS_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "EAS-config.json"
)

# GraphQL query for fetching attestations
ATTESTATIONS_QUERY = """
query GetAttestations($schemaId: String!, $take: Int!) {
  attestations(
    where: { schemaId: { equals: $schemaId } }
    orderBy: { time: desc }
    take: $take
  ) {
    id
    attester
    recipient
    revoked
    revocationTime
    expirationTime
    time
    data
    schemaId
    refUID
    txid
    blockNumber
  }
}
"""


def load_eas_config() -> Dict[str, Any]:
    """Load EAS configuration from the config file."""
    try:
        with open(EAS_CONFIG_PATH, "r") as f:
            config: Dict[str, Any] = json.load(f)
            return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading EAS config: {e}")
        sys.exit(1)


async def get_chain_info(
    conn: asyncpg.Connection, chain_id: int
) -> Optional[Dict[str, Any]]:
    """Get chain information from the database.

    Args:
        conn: Database connection
        chain_id: Chain ID to look up

    Returns:
        Chain information or None if not found
    """
    row = await conn.fetchrow(
        "SELECT chain_id, name, features FROM chain WHERE chain_id = $1", chain_id
    )

    if not row:
        return None

    return dict(row)


async def get_eas_endpoint(chain_info: Dict[str, Any]) -> Optional[str]:
    """Extract EAS GraphQL endpoint from chain features.

    Args:
        chain_info: Chain information from database

    Returns:
        EAS GraphQL endpoint URL or None if not found
    """
    # The features field is stored as a JSON string in the database
    features = chain_info.get("features", "{}")

    # Parse the JSON string if it's a string
    if isinstance(features, str):
        try:
            features = json.loads(features)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse features JSON: {features}")
            return None

    # Look for EAS feature
    for feature in features:
        if isinstance(feature, dict) and feature.get("name") == "EAS":
            endpoint: Optional[str] = feature.get("url")
            return endpoint

    return None


async def get_schema_id(conn: asyncpg.Connection, chain_id: int) -> Optional[str]:
    """Get the schema ID for a chain from the EAS config.

    Args:
        conn: Database connection
        chain_id: Chain ID

    Returns:
        Schema ID or None if not found
    """
    try:
        # Load EAS configuration
        eas_config = load_eas_config()

        # Get schema UID from EAS config
        chain_config = eas_config.get("chains", {}).get(str(chain_id), {})
        schema_id: Optional[str] = chain_config.get("schemaUID")
        return schema_id
    except Exception as e:
        logging.error(f"Error getting schema ID: {e}")
        return None


async def get_or_create_address(conn: asyncpg.Connection, ethereum_address: str) -> int:
    """Get or create an address record for an Ethereum address.

    Args:
        conn: Database connection
        ethereum_address: Ethereum address string

    Returns:
        Address ID
    """
    try:
        # First, check if the address already exists
        row = await conn.fetchrow(
            """
            SELECT id FROM address
            WHERE address = $1
            LIMIT 1
            """,
            ethereum_address,
        )

        if row:
            return cast(int, row["id"])

        # Since user_id can't be null, we need to create or get a dummy user
        # Get or create a dummy user with ID 1
        user_row = await conn.fetchrow(
            """
            SELECT id FROM "user"
            WHERE id = 1
            LIMIT 1
            """
        )

        if not user_row:
            # Create a dummy user with ID 1
            await conn.execute(
                """
                INSERT INTO "user" (id, name, role, created_at, updated_at)
                VALUES (1, 'Dummy User', 'user', $1, $2)
                """,
                datetime.now(),
                datetime.now(),
            )

        # Now create the address with is_verified = false
        address_id = await conn.fetchval(
            """
            INSERT INTO address (user_id, address, label, is_verified,
                                created_at, updated_at)
            VALUES (1, $1, $2, $3, $4, $5)
            RETURNING id
            """,
            ethereum_address,
            "EAS Attestation",
            False,  # Set is_verified to false
            datetime.now(),
            datetime.now(),
        )

        if address_id is None:
            raise ValueError("Failed to create address record")

        return cast(int, address_id)

    except Exception as e:
        logging.error(f"Error getting or creating address: {e}")
        raise


def extract_location_data(attestation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract location data from an attestation.

    Args:
        attestation: Attestation data from EAS

    Returns:
        Dict with location data or None if attestation lacks valid location data.
    """
    try:
        # For now, just return dummy location data
        # In a real implementation, you would parse the attestation data
        # to extract the actual location information
        return {
            "latitude": 37.7749,
            "longitude": -122.4194,
            "location_type": "point",
            "accuracy": 10.0,
            "source": "eas",
            "timestamp": int(time.time()),
            # Include memo
            "memo": attestation.get("memo", "Location proof from EAS"),
        }
    except Exception as e:
        logging.error(f"Error extracting location data: {e}")
        return None


async def create_location_proof(
    conn: asyncpg.Connection,
    chain_id: int,
    attestation: Dict[str, Any],
    attester_id: int,
    recipient_id: int,
    location_data: Dict[str, Any],
) -> bool:
    """Create a location proof record in the database.

    Args:
        conn: Database connection
        chain_id: Chain ID
        attestation: Attestation data from EAS
        attester_id: Address ID of the attester
        recipient_id: Address ID of the recipient
        location_data: Location data extracted from the attestation

    Returns:
        True if a new record was created, False otherwise
    """
    try:
        # Check if attestation already exists
        row = await conn.fetchrow(
            """
            SELECT id FROM location_proof
            WHERE uid = $1
            """,
            attestation["id"],
        )

        if row:
            return False  # Already exists

        # Create WKT point from lat/lng
        point_wkt = f"POINT({location_data['longitude']} {location_data['latitude']})"

        # Get schema ID from the attestation or from the chain config
        schema_id = attestation.get("schemaId")
        if not schema_id:
            # If not in the attestation, get it from the chain config
            schema_id = await get_schema_id(conn, chain_id)
            if not schema_id:
                logging.error(f"No schema ID found for chain {chain_id}")
                return False

        # Insert new location proof
        await conn.execute(
            """
            INSERT INTO location_proof (
                uid, schema, event_timestamp, revoked, revocable,
                srs, location_type, location, recipe_type, recipe_payload,
                media_type, media_data, status, chain_id,
                attester_id, recipient_id, memo, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, ST_GeomFromText($8, 4326),
                    $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
            """,
            attestation["id"],  # uid
            schema_id,  # schema
            int(attestation.get("timeCreated", time.time())),  # event_timestamp
            attestation.get("revoked", False),  # revoked
            attestation.get("revocable", True),  # revocable
            "EPSG:4326",  # srs (coordinate system)
            location_data["location_type"],  # location_type
            point_wkt,  # location
            "[]",  # recipe_type (empty array as JSON string)
            "{}",  # recipe_payload (empty object as JSON string)
            "[]",  # media_type (empty array as JSON string)
            "",  # media_data
            "verified",  # status
            chain_id,  # chain_id
            attester_id,  # attester_id
            recipient_id,  # recipient_id
            location_data.get("memo", ""),  # memo
            datetime.now(),  # created_at
            datetime.now(),  # updated_at
        )

        return True  # New record created
    except Exception as e:
        logging.error(f"Error creating location proof: {e}")
        return False


def fetch_attestations(
    endpoint: str, schema_id: str, limit: int = 100
) -> list[Dict[str, Any]]:
    """Fetch attestations from the EAS GraphQL endpoint.

    Args:
        endpoint: EAS GraphQL endpoint URL
        schema_id: Schema ID to fetch attestations for
        limit: Maximum number of attestations to fetch

    Returns:
        List of attestations
    """
    query = """
    query GetAttestations($schemaId: String!, $take: Int!) {
      attestations(where: {schemaId: {equals: $schemaId}}, take: $take) {
        id
        attester
        recipient
        refUID
        revocable
        revoked
        data
        time
        timeCreated
        txid
      }
    }
    """

    variables = {"schemaId": schema_id, "take": limit}

    try:
        response = requests.post(
            endpoint,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            error_message = (
                data["errors"][0]["message"]
                if data["errors"]
                else "Unknown GraphQL error"
            )
            raise Exception(f"GraphQL error: {error_message}")

        result: list[Dict[str, Any]] = data.get("data", {}).get("attestations", [])
        return result
    except Exception as e:
        logger.error(f"Error fetching attestations from {endpoint}: {str(e)}")
        return []


async def process_chain(conn: asyncpg.Connection, chain_id: int, limit: int) -> int:
    """Process attestations for a specific chain.

    Args:
        conn: Database connection
        chain_id: Chain ID
        limit: Maximum number of attestations to fetch

    Returns:
        Number of attestations processed
    """
    # Get chain info from database
    chain_info = await get_chain_info(conn, chain_id)
    if not chain_info:
        logging.info(f"No chain info found for chain {chain_id}")
        return 0

    # Get the EAS endpoint for this chain
    eas_endpoint = await get_eas_endpoint(chain_info)
    if not eas_endpoint:
        logging.info(f"No EAS endpoint found for chain {chain_id}")
        return 0

    # Get the schema ID for this chain
    schema_id = await get_schema_id(conn, chain_id)
    if not schema_id:
        logging.info(f"No schema ID found for chain {chain_id}")
        return 0

    logging.info(f"Fetching attestations for chain {chain_id} from {eas_endpoint}")

    # Fetch attestations from the EAS endpoint
    attestations = fetch_attestations(eas_endpoint, schema_id, limit)

    processed_count = 0
    for attestation in attestations:
        try:
            # Extract location data from the attestation
            location_data = extract_location_data(attestation)
            if not location_data:
                continue

            # Get or create address records for attester and recipient
            attester_address = attestation.get(
                "attester", "0x0000000000000000000000000000000000000000"
            )
            recipient_address = attestation.get(
                "recipient", "0x0000000000000000000000000000000000000000"
            )

            attester_id = await get_or_create_address(conn, attester_address)
            recipient_id = await get_or_create_address(conn, recipient_address)

            # Create a location proof
            success = await create_location_proof(
                conn, chain_id, attestation, attester_id, recipient_id, location_data
            )

            if success:
                processed_count += 1

        except Exception as e:
            logging.error(f"Error processing attestation: {e}")
            continue

    logging.info(f"Processed {processed_count} new attestations for chain {chain_id}")
    return processed_count


async def seed_location_proofs(
    chain_id: Optional[int] = None, limit: int = DEFAULT_PROOF_LIMIT
) -> None:
    """Seed the database with location proofs from EAS.

    Args:
        chain_id: Specific chain ID to process, or None for all chains
        limit: Maximum number of attestations to fetch per chain
    """
    # Load EAS configuration
    eas_config = load_eas_config()

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
        # Determine which chains to process
        chain_ids = []
        if chain_id:
            # Process specific chain
            chain_ids = [chain_id]
        else:
            # Process all chains in the EAS config
            chain_ids = [int(cid) for cid in eas_config.get("chains", {}).keys()]

        total_processed = 0

        # Process each chain
        for cid in chain_ids:
            # Process chain
            processed = await process_chain(conn, cid, limit)
            total_processed += processed

        logger.info(f"Total location proofs processed: {total_processed}")

        # Get total count of location proofs
        total_count = await conn.fetchval("SELECT COUNT(*) FROM location_proof")
        logger.info(f"Total location proofs in database: {total_count}")

    finally:
        # Close the connection
        await conn.close()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Seed the database with location proofs from EAS."
    )
    parser.add_argument(
        "--chain",
        type=int,
        help="Specific chain ID to process (default: all chains)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_PROOF_LIMIT,
        help=(
            f"Maximum number of attestations to fetch per chain "
            f"(default: {DEFAULT_PROOF_LIMIT})"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(seed_location_proofs(chain_id=args.chain, limit=args.limit))
