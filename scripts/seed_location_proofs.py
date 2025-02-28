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
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
import requests
from shapely import wkt
from shapely.geometry import shape

from app.services.schema_encoder import SchemaEncoder

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
    """Load EAS configuration from the config file.

    Returns:
        Dict containing the EAS configuration
    """
    try:
        with open(EAS_CONFIG_PATH, "r") as f:
            config = json.load(f)
            if not isinstance(config, dict):
                raise ValueError("EAS config must be a dictionary")
            return config
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error("Error loading EAS config: %s", e)
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

    result: Dict[str, Any] = dict(row)
    return result


def get_eas_endpoint(chain_info: Dict[str, Any]) -> Optional[str]:
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
            features_dict = json.loads(features)
            if not isinstance(features_dict, list):
                logger.error("Features must be a list")
                return None
            features = features_dict
        except json.JSONDecodeError:
            logger.error("Failed to parse features JSON: %s", features)
            return None

    # Look for EAS feature
    for feature in features:
        if isinstance(feature, dict) and feature.get("name") == "EAS":
            endpoint = feature.get("url")
            if isinstance(endpoint, str):
                return endpoint
            logger.error("EAS endpoint URL must be a string")
            return None

    # Fallback to standard EAS endpoints based on chain ID
    chain_id = chain_info.get("chain_id")
    if chain_id:
        # Map of chain IDs to EAS GraphQL endpoints
        eas_endpoints = {
            42220: "https://api.celo.easscan.org/graphql",  # Celo
            42161: "https://api.arbitrum.easscan.org/graphql",  # Arbitrum
            11155111: "https://api.sepolia.easscan.org/graphql",  # Sepolia
            8453: "https://api.base.easscan.org/graphql",  # Base
            1: "https://api.easscan.org/graphql",  # Ethereum Mainnet
        }

        if chain_id in eas_endpoints:
            logging.info(
                f"Using fallback EAS endpoint for chain {chain_id}: "
                f"{eas_endpoints[chain_id]}"
            )
            return eas_endpoints[chain_id]

    logging.warning(f"No EAS endpoint found for chain {chain_id}")
    return None


def get_schema_id(chain_id: int) -> str:
    """Get the schema ID for a chain.

    Args:
        chain_id: Chain ID to get schema for

    Returns:
        Schema ID string or empty string if not found
    """
    try:
        eas_config = load_eas_config()
        chain_config = eas_config.get("chains", {}).get(str(chain_id))
        if not chain_config:
            logging.warning("No EAS config found for chain %d", chain_id)
            return ""

        schema_id = chain_config.get("schemaUID", "")
        if not isinstance(schema_id, str):
            logging.warning("No schema UID found in EAS config for chain %d", chain_id)
            return ""

        return schema_id if schema_id else ""
    except Exception as e:
        logging.error("Error getting schema ID for chain %d: %s", chain_id, str(e))
        return ""


async def get_address_id(conn: asyncpg.Connection, address: str) -> int:
    """Get or create an address record in the database.

    Args:
        conn: Database connection
        address: Ethereum address

    Returns:
        Address ID from database
    """
    try:
        normalized_address = address.lower()
        row = await conn.fetchrow(
            "SELECT id FROM address WHERE address = $1", normalized_address
        )

        if row and row["id"] is not None:
            return int(row["id"])

        user_row = await conn.fetchrow('SELECT id FROM "user" WHERE id = 1')
        if not user_row:
            await conn.execute(
                """
                INSERT INTO "user" (id, name, role, created_at, updated_at)
                VALUES (1, 'Default User', 'user', NOW(), NOW())
                """
            )

        new_id = await conn.fetchval(
            """
            INSERT INTO address (
                user_id, address, label, is_verified, created_at, updated_at
            ) VALUES (1, $1, 'ETH Address', false, NOW(), NOW())
            RETURNING id
            """,
            normalized_address,
        )
        return int(new_id) if new_id is not None else 1
    except Exception as e:
        logging.error("Error getting/creating address: %s", str(e))
        return 1


def extract_location_data(attestation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract location data from an attestation.

    Args:
        attestation: Attestation data from EAS

    Returns:
        Dict containing the extracted location data or None if extraction fails
    """
    try:
        data = attestation.get("data", "")
        attestation_id = attestation.get("id", "unknown")

        print("=== PROCESSING ATTESTATION {} ===".format(attestation_id))
        print("Raw data type: {}".format(type(data)))
        data_preview = (
            data[:100] + "..." if isinstance(data, str) and len(data) > 100 else data
        )
        print("Raw data: {}".format(data_preview))

        if not data:
            print("No data in attestation")
            logging.warning("Attestation %s has no data", attestation_id)
            return None

        # Convert hex string to bytes
        if isinstance(data, str) and data.startswith("0x"):
            data = bytes.fromhex(data[2:])
        elif not isinstance(data, bytes):
            logging.error(f"Invalid data format: {type(data)}")
            return None

        # Use SchemaEncoder to decode the data
        try:
            decoded_data = SchemaEncoder.decode_data(data)
            SchemaEncoder.validate_decoded_data(decoded_data)
            print(f"Successfully decoded attestation data: {decoded_data}")
        except Exception as e:
            print(f"Failed to decode attestation data: {e}")
            logging.error(f"Failed to decode attestation data: {e}")
            return None

        # Process the location data based on its format
        location_data = decoded_data.get("location")
        if not location_data:
            print("No location field in attestation")
            logging.warning("No location field in attestation %s", attestation_id)
            return None

        print(f"Extracted location data: {location_data}")

        # Get location type from decoded data
        location_type = decoded_data.get("locationType", "point")
        print(f"Location type: {location_type}")

        # Process the location data to WKT format
        wkt_str, spatial_type = process_location_to_wkt(location_data, location_type)
        if not wkt_str:
            print("Could not process location data to WKT")
            msg = "Could not process location data in attestation"
            logging.warning(f"{msg} %s", attestation_id)
            return None

        print(f"Processed location to WKT: {wkt_str}, type: {spatial_type}")
        print(f"=== END PROCESSING ATTESTATION {attestation_id} ===\n")

        # Convert bytes to hex strings for JSON serialization
        recipe_payload = {}
        for rtype, payload in zip(
            decoded_data.get("recipeType", []),
            decoded_data.get("recipePayload", []),
        ):
            # Convert bytes to hex string if needed
            if isinstance(payload, bytes):
                payload = "0x" + payload.hex()
            recipe_payload[rtype] = payload

        # Return the extracted data
        return {
            "latitude": None,  # Will be set by caller if needed for legacy code
            "longitude": None,  # Will be set by caller if needed for legacy code
            "location_type": spatial_type,
            "location_wkt": wkt_str,
            "accuracy": 10.0,  # Default accuracy since it's not in our schema
            "source": "eas",
            "timestamp": int(
                decoded_data.get("eventTimestamp", attestation.get("time", time.time()))
            ),
            "memo": decoded_data.get("memo", ""),
            "media_type": decoded_data.get("mediaType", []),
            "media_data": decoded_data.get("mediaData", []),
            "recipe_type": decoded_data.get("recipeType", []),
            "recipe_payload": recipe_payload,
        }
    except Exception as e:
        print(f"Error extracting location data: {e}")
        logging.error(f"Error extracting location data: {e}")
        return None


def process_location_to_wkt(location_data: Any, location_type: str) -> Tuple[str, str]:
    """Process location data to WKT format.

    Args:
        location_data: Location data from attestation
        location_type: Location type hint

    Returns:
        Tuple of (WKT string, spatial type).
        If processing fails, returns ("", original type)
    """
    try:
        # Try to process as GeoJSON first if it's a dictionary
        if isinstance(location_data, dict):
            print(f"Processing as GeoJSON: {location_data}")
            return process_geojson_to_wkt(location_data)

        # Try to process as WKT string
        if isinstance(location_data, str):
            # More strict WKT detection - must start with a WKT type keyword
            wkt_types = [
                "POINT",
                "LINESTRING",
                "POLYGON",
                "MULTIPOINT",
                "MULTILINESTRING",
                "MULTIPOLYGON",
            ]
            is_wkt = any(location_data.upper().strip().startswith(x) for x in wkt_types)

            # Check for GeoJSON in string format
            try:
                if not is_wkt and (
                    location_data.strip().startswith("{")
                    and location_data.strip().endswith("}")
                ):
                    json_data = json.loads(location_data)
                    if isinstance(json_data, dict) and "type" in json_data:
                        print(f"Processing JSON string as GeoJSON: {json_data}")
                        return process_geojson_to_wkt(json_data)
            except json.JSONDecodeError:
                # Not valid JSON, continue with other checks
                pass

            if is_wkt:
                # It's already WKT, just validate it
                try:
                    geom = wkt.loads(str(location_data))
                    return str(location_data), str(geom.geom_type.lower())
                except Exception as e:
                    logging.error("Invalid WKT string: %s", str(e))
                    return "", location_type

            # Try to process as raw coordinates
            if "," in location_data:
                return process_raw_coordinates_to_wkt(location_data)

        # Try to process as coordinate array
        if isinstance(location_data, list) and len(location_data) >= 2:
            try:
                # Assume [lon, lat] format
                lon, lat = float(location_data[0]), float(location_data[1])
                if -180 <= lon <= 180 and -90 <= lat <= 90:
                    return f"POINT({lon} {lat})", "point"
                # Try [lat, lon] format
                lat, lon = float(location_data[0]), float(location_data[1])
                if -180 <= lon <= 180 and -90 <= lat <= 90:
                    return f"POINT({lon} {lat})", "point"
            except (ValueError, TypeError):
                pass

        # Fallback: couldn't process the location data
        msg = f"Unrecognized location data format: {str(location_data)}"
        logging.warning(msg)
        return "", location_type

    except Exception as e:
        msg = f"Error processing location to WKT: {str(e)}"
        logging.error(msg)
        return "", location_type


def process_geojson_to_wkt(geojson_data: Dict[str, Any]) -> Tuple[str, str]:
    """Convert GeoJSON to WKT.

    Args:
        geojson_data: GeoJSON data

    Returns:
        Tuple of (WKT string, spatial type).
        If processing fails, returns ("", "unknown")
    """
    try:
        # Handle different GeoJSON types
        if "type" not in geojson_data:
            logging.warning("GeoJSON missing 'type' field")
            return "", "unknown"

        geojson_type = str(geojson_data["type"])
        print(f"Processing GeoJSON with type: {geojson_type}")

        # Handle case-insensitive comparison for GeoJSON types
        geojson_type_lower = geojson_type.lower()

        # Handle Feature
        if geojson_type_lower == "feature":
            if "geometry" not in geojson_data:
                logging.warning("GeoJSON Feature missing 'geometry'")
                return "", "unknown"

            geometry = geojson_data["geometry"]
            geom = shape(geometry)
            return str(geom.wkt), str(geom.geom_type.lower())

        # Handle FeatureCollection
        elif geojson_type_lower == "featurecollection":
            features = geojson_data.get("features", [])
            if not features:
                logging.warning("Empty FeatureCollection")
                return "", "unknown"

            # Use the first feature for now
            first_feature = features[0]
            if "geometry" not in first_feature:
                logging.warning("First feature missing 'geometry'")
                return "", "unknown"

            geometry = first_feature["geometry"]
            geom = shape(geometry)
            return str(geom.wkt), f"collection_{str(geom.geom_type.lower())}"

        # Handle direct geometry
        elif geojson_type_lower in [
            "point",
            "linestring",
            "polygon",
            "multipoint",
            "multilinestring",
            "multipolygon",
        ]:
            try:
                geom = shape(geojson_data)
                return str(geom.wkt), str(geojson_type_lower)
            except Exception as e:
                logging.error(f"Error creating shape from GeoJSON: {e}")
                # Try to handle non-standard GeoJSON format
                if geojson_type_lower == "point" and "coordinates" in geojson_data:
                    coords = geojson_data["coordinates"]
                    if isinstance(coords, list) and len(coords) >= 2:
                        lon, lat = coords[0], coords[1]
                        return f"POINT({lon} {lat})", "point"
                return "", "unknown"
        else:
            logging.warning("Unsupported GeoJSON type: %s", geojson_type)
            return "", "unknown"

    except Exception as e:
        logging.error("Error processing GeoJSON: %s", str(e))
        return "", "unknown"


def process_raw_coordinates_to_wkt(coord_string: str) -> Tuple[str, str]:
    """Convert raw coordinate string to WKT.

    Args:
        coord_string: Coordinate string (e.g. "lat,lng" or "lng,lat")

    Returns:
        Tuple of (WKT string, spatial type). If processing fails, returns ("", "point")
    """
    try:
        # Split the string
        parts = coord_string.split(",", 1)
        if len(parts) != 2:
            logging.warning("Invalid coordinate format: %s", coord_string)
            return "", "point"

        # Try to parse as numbers
        try:
            a, b = float(parts[0].strip()), float(parts[1].strip())
        except ValueError:
            logging.warning("Could not parse coordinates as floats: %s", coord_string)
            return "", "point"

        # Try to determine if it's [lng,lat] or [lat,lng]
        # Assume [lng,lat] first (preferred)
        if -180 <= a <= 180 and -90 <= b <= 90:
            return f"POINT({a} {b})", "point"

        # Try [lat,lng]
        if -90 <= a <= 90 and -180 <= b <= 180:
            return f"POINT({b} {a})", "point"

        # Coordinates out of range
        logging.warning("Coordinates out of range: %s", coord_string)
        return "", "point"

    except Exception as e:
        logging.error("Error processing raw coordinates: %s", str(e))
        return "", "point"


async def create_location_proof(
    conn: asyncpg.Connection,
    chain_id: int,
    attestation: dict,
    location_data: dict,
) -> Optional[dict]:
    """Create a location proof record in the database."""
    try:
        # Check if the location_proof table exists and get its columns
        try:
            columns = await conn.fetch(
                """SELECT column_name FROM information_schema.columns
                WHERE table_name = 'location_proof';"""
            )
            column_names = [col["column_name"] for col in columns]
            if not column_names:
                logging.error("location_proof table not found")
                return None

            # Log if schema column is missing
            if "schema" not in column_names:
                logging.error("schema column not found in location_proof table")
                return None
        except Exception as e:
            logging.error(f"Error checking table structure: {e}")
            return None

        # Get the chain's ID from its chain_id
        chain_row = await conn.fetchrow(
            "SELECT id FROM chain WHERE chain_id = $1", chain_id
        )
        if not chain_row or chain_row["id"] is None:
            logging.error(f"Chain with chain_id {chain_id} not found")
            return None

        chain_id_pk = int(chain_row["id"])

        # Get or create attester and recipient addresses
        attester_id = await get_address_id(conn, attestation["attester"])
        recipient_id = await get_address_id(conn, attestation["recipient"])

        # Convert recipe_payload bytes to hex strings for JSON serialization
        recipe_payload = location_data.get("recipe_payload", {})
        if isinstance(recipe_payload, dict):
            for key, value in recipe_payload.items():
                if isinstance(value, bytes):
                    recipe_payload[key] = value.hex()

        # Insert the location proof
        try:
            location_proof_id = await conn.fetchval(
                """
                INSERT INTO location_proof (
                    uid, schema, event_timestamp, expiration_time, revoked,
                    revocation_time, ref_uid, revocable, srs, location_type,
                    location, recipe_type, recipe_payload, media_type,
                    media_data, memo, status, block_number, transaction_hash,
                    cid, chain_id, attester_id, recipient_id, extra
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19,
                    $20, $21, $22, $23, $24
                )
                RETURNING id
                """,
                attestation["id"],  # uid
                attestation["schemaId"],  # schema
                location_data["timestamp"],  # event_timestamp
                attestation.get("expirationTime", 0) or None,  # expiration_time
                attestation.get("revoked", False),  # revoked
                attestation.get("revocationTime", 0) or None,  # revocation_time
                attestation.get("refUID"),  # ref_uid
                attestation.get("revocable", True),  # revocable
                "EPSG:4326",  # srs
                location_data["location_type"],  # location_type
                location_data["location_wkt"],  # location
                json.dumps(location_data.get("recipeType", [])),  # recipe_type
                json.dumps(recipe_payload),  # recipe_payload
                json.dumps(location_data.get("mediaType", [])),  # media_type
                json.dumps(location_data.get("mediaData", [])),  # media_data
                location_data.get("memo"),  # memo
                "onchain (validated)",  # status
                attestation.get("blockNumber"),  # block_number
                attestation.get("txid"),  # transaction_hash
                None,  # cid
                chain_id_pk,  # chain_id (using the primary key)
                attester_id,  # attester_id
                recipient_id,  # recipient_id
                json.dumps({}),  # extra
            )

            if location_proof_id is not None:
                return {"id": location_proof_id}
            return None

        except Exception as e:
            logging.error(f"Error creating location proof: {e}")

            # Try with a different status if the first attempt failed
            try:
                location_proof_id = await conn.fetchval(
                    """
                    INSERT INTO location_proof (
                        uid, schema, event_timestamp, expiration_time, revoked,
                        revocation_time, ref_uid, revocable, srs, location_type,
                        location, recipe_type, recipe_payload, media_type,
                        media_data, memo, status, block_number, transaction_hash,
                        cid, chain_id, attester_id, recipient_id, extra
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18, $19,
                        $20, $21, $22, $23, $24
                    )
                    RETURNING id
                    """,
                    attestation["id"],  # uid
                    attestation["schemaId"],  # schema
                    location_data["timestamp"],  # event_timestamp
                    attestation.get("expirationTime", 0) or None,  # expiration_time
                    attestation.get("revoked", False),  # revoked
                    attestation.get("revocationTime", 0) or None,  # revocation_time
                    attestation.get("refUID"),  # ref_uid
                    attestation.get("revocable", True),  # revocable
                    "EPSG:4326",  # srs
                    location_data["location_type"],  # location_type
                    location_data["location_wkt"],  # location
                    json.dumps(location_data.get("recipeType", [])),  # recipe_type
                    json.dumps(recipe_payload),  # recipe_payload
                    json.dumps(location_data.get("mediaType", [])),  # media_type
                    json.dumps(location_data.get("mediaData", [])),  # media_data
                    location_data.get("memo"),  # memo
                    "IPFS",  # status
                    attestation.get("blockNumber"),  # block_number
                    attestation.get("txid"),  # transaction_hash
                    None,  # cid
                    chain_id_pk,  # chain_id (using the primary key)
                    attester_id,  # attester_id
                    recipient_id,  # recipient_id
                    json.dumps({}),  # extra
                )

                if location_proof_id is not None:
                    return {"id": location_proof_id}
                return None

            except Exception as e2:
                logging.error(
                    f"Error creating location proof with alternate status: {e2}"
                )
                return None
    except Exception as e:
        logging.error(f"Error creating location proof: {e}")
        return None


def fetch_attestations(
    endpoint: str, schema_id: str, limit: int = 100
) -> List[Dict[str, Any]]:
    """Fetch attestations from the EAS GraphQL endpoint.

    Args:
        endpoint: EAS GraphQL endpoint URL
        schema_id: Schema ID to fetch attestations for
        limit: Maximum number of attestations to fetch

    Returns:
        List of attestations
    """
    # Updated query to match EAS API requirements - removed blockNumber field
    query = """
    query GetAttestations($schemaId: String!, $take: Int!) {
      attestations(
        where: {schemaId: {equals: $schemaId}}
        take: $take
        orderBy: {time: desc}
      ) {
        id
        attester
        recipient
        refUID
        revocable
        revoked
        data
        time
        schemaId
        txid
      }
    }
    """

    variables = {"schemaId": schema_id, "take": limit}

    try:
        logging.debug(
            f"Sending GraphQL query to {endpoint} with variables: {variables}"
        )

        # Add proper headers and timeout
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        response = requests.post(
            endpoint,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30,
        )

        # Print response details for debugging
        logging.debug(f"Response status: {response.status_code}")
        logging.debug(f"Response headers: {response.headers}")

        if response.status_code != 200:
            logging.error(
                f"GraphQL request failed with status {response.status_code}: "
                f"{response.text}"
            )
            return []

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON response: {e}")
            logging.debug(f"Response text: {response.text[:500]}...")
            return []

        if "errors" in data:
            error_message = (
                data["errors"][0]["message"]
                if data["errors"]
                else "Unknown GraphQL error"
            )
            logging.error(f"GraphQL error: {error_message}")
            return []

        result: List[Dict[str, Any]] = data.get("data", {}).get("attestations", [])

        # Print the first attestation for debugging
        if result and len(result) > 0:
            logging.debug("\n=== ATTESTATION STRUCTURE ===")
            logging.debug(f"Keys in attestation: {list(result[0].keys())}")
            logging.debug(f"Data field type: {type(result[0].get('data', ''))}")
            data_preview = result[0].get("data", "")
            logging.debug(
                f"Data field value: {data_preview[:200]}..."
                if len(str(data_preview)) > 200
                else f"Data field value: {data_preview}"
            )
            logging.debug("=== END ATTESTATION STRUCTURE ===\n")

        return result
    except requests.RequestException as e:
        logging.error(
            f"Request error when fetching attestations from {endpoint}: {str(e)}"
        )
        return []
    except Exception as e:
        logging.error(f"Error fetching attestations from {endpoint}: {str(e)}")
        return []


async def process_chain(
    conn: asyncpg.Connection, chain_id: int, limit: int = DEFAULT_PROOF_LIMIT
) -> int:
    """Process attestations for a specific chain.

    Args:
        conn: Database connection
        chain_id: Chain ID to process
        limit: Maximum number of attestations to fetch

    Returns:
        Number of attestations processed
    """
    try:
        # Get chain information
        chain_info = await get_chain_info(conn, chain_id)
        if not chain_info:
            logging.warning("Chain %d not found in database", chain_id)
            return 0

        # Get EAS endpoint for this chain
        eas_endpoint = get_eas_endpoint(chain_info)
        if not eas_endpoint:
            logging.warning("No EAS endpoint found for chain %d", chain_id)
            return 0

        # Get the schema ID for this chain
        schema_id = get_schema_id(chain_id)
        if not schema_id:
            logging.warning("No schema ID found for chain %d", chain_id)
            return 0

        logging.info(
            "Fetching attestations for chain %d from %s", chain_id, eas_endpoint
        )

        # Fetch attestations from the EAS endpoint
        try:
            attestations = fetch_attestations(eas_endpoint, schema_id, limit)
            logging.info(
                "Fetched %d attestations from %s", len(attestations), eas_endpoint
            )
        except Exception as e:
            logging.error(
                "Failed to fetch attestations from %s: %s", eas_endpoint, str(e)
            )
            return 0

        processed_count = 0
        error_count = 0
        skipped_count = 0

        for attestation in attestations:
            try:
                # Extract location data from the attestation
                location_data = extract_location_data(attestation)
                if not location_data:
                    logging.debug(
                        "Skipping attestation %s: No valid location data",
                        attestation.get("id", "unknown"),
                    )
                    skipped_count += 1
                    continue

                # Create or update a location proof
                success = await create_location_proof(
                    conn, chain_id, attestation, location_data
                )

                if success:
                    processed_count += 1
                else:
                    skipped_count += 1

            except Exception as e:
                logging.error(
                    "Error processing attestation %s: %s",
                    attestation.get("id", "unknown"),
                    str(e),
                )
                error_count += 1
                continue

        logging.info(
            "Chain %d summary: "
            "Processed %d attestations, "
            "Skipped %d attestations, "
            "Errors %d attestations",
            chain_id,
            processed_count,
            skipped_count,
            error_count,
        )
        return processed_count
    except Exception as e:
        logging.error("Error processing chain %d: %s", chain_id, str(e))
        return 0


async def seed_location_proofs(
    chain_id: Optional[int] = None, limit: int = DEFAULT_PROOF_LIMIT
) -> None:
    """Seed the database with location proofs from EAS.

    Args:
        chain_id: Specific chain ID to process, or None for all chains
        limit: Maximum number of attestations to fetch per chain
    """
    start_time = time.time()
    logging.info(
        "Starting location proof seeding process at %s", datetime.now().isoformat()
    )

    # Load EAS configuration
    try:
        eas_config = load_eas_config()
    except Exception as e:
        logging.error("Failed to load EAS configuration: %s", str(e))
        return

    # Get database connection parameters from environment
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "astral")

    # Connect to the database
    try:
        conn = await asyncpg.connect(
            host=host, port=port, user=user, password=password, database=db
        )
    except Exception as e:
        logging.error("Failed to connect to database: %s", str(e))
        return

    try:
        # Determine which chains to process
        chain_ids = []
        if chain_id:
            # Process specific chain
            chain_ids = [chain_id]
            logging.info("Processing specific chain: %d", chain_id)
        else:
            # Process all chains in the EAS config
            chain_ids = [int(cid) for cid in eas_config.get("chains", {}).keys()]
            logging.info("Processing all chains: %s", chain_ids)

        total_processed = 0
        chain_results = {}

        # Process each chain
        for cid in chain_ids:
            # Process chain
            processed = await process_chain(conn, cid, limit)
            total_processed += processed
            chain_results[cid] = processed

        # Log detailed results
        for cid, count in chain_results.items():
            logger.info("Chain %d: Processed %d location proofs", cid, count)

        logger.info("Total location proofs processed: %d", total_processed)

        # Get total count of location proofs
        total_count = await conn.fetchval("SELECT COUNT(*) FROM location_proof")
        logger.info("Total location proofs in database: %d", total_count)

        # Log execution time
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info("Location proof seeding completed in %.2f seconds", execution_time)

    except Exception as e:
        logging.error("Error during location proof seeding: %s", str(e))
    finally:
        # Close the connection
        await conn.close()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Seed the database with location proofs from EAS."
    )
    parser.add_argument(
        "--chain_id",
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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()

    # Configure logging
    logging_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=logging_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run the seeding process
    asyncio.run(seed_location_proofs(args.chain_id, args.limit))
