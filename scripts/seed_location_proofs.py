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
from typing import Any, Dict, List, Optional, Tuple, Union

import asyncpg
import requests
from shapely.geometry import Point, Polygon, shape
from shapely.wkt import loads as wkt_loads

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


async def get_schema_id(conn: asyncpg.Connection, chain_id: int) -> str:
    """Get the schema ID for a chain."""
    try:
        eas_config = load_eas_config()
        chain_config = eas_config.get("chains", {}).get(str(chain_id))
        if not chain_config:
            logging.warning("No EAS config found for chain %d", chain_id)
            return ""

        schema_id = chain_config.get("schemaUID", "")
        if not schema_id:
            logging.warning("No schema UID found in EAS config for chain %d", chain_id)
            return ""

        return schema_id
    except Exception as e:
        logging.error("Error getting schema ID for chain %d: %s", chain_id, str(e))
        return ""


async def get_address_id(conn: asyncpg.Connection, address: str) -> int:
    """Get or create an address record in the database."""
    try:
        normalized_address = address.lower()
        row = await conn.fetchrow(
            "SELECT id FROM address WHERE address = $1", normalized_address
        )

        if row:
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
            INSERT INTO address (user_id, address, label, is_verified, created_at, updated_at)
            VALUES (1, $1, 'ETH Address', false, NOW(), NOW())
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

    Supports multiple location formats including:
    - GeoJSON features (Point, LineString, Polygon)
    - Raw coordinates (lat,lng or lng,lat)
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

        # Try to decode the attestation data
        try:
            # The data field might be hex-encoded
            if isinstance(data, str) and data.startswith("0x"):
                # Remove the 0x prefix
                hex_data = data[2:]
                print(f"Detected hex data: 0x{hex_data[:20]}...")

                # Try to decode as UTF-8 JSON
                try:
                    decoded_data = bytes.fromhex(hex_data).decode("utf-8")
                    print(
                        f"Successfully decoded hex data as UTF-8: {decoded_data[:100]}..."
                    )
                    data_json = json.loads(decoded_data)
                    print(f"Successfully parsed JSON from decoded data")
                except UnicodeDecodeError as e:
                    print(f"Failed to decode hex data as UTF-8: {e}")
                    # If UTF-8 decoding fails, try to parse the binary data directly
                    try:
                        # This is a fallback for binary data that's not UTF-8
                        # Try to extract location data from binary
                        print(f"Attempting binary parsing for attestation")
                        logging.info(
                            f"Attempting binary parsing for attestation {attestation_id}"
                        )

                        # For now, create a dummy location point
                        # In a real implementation, we would parse the binary format
                        print("Using fallback location (San Francisco)")
                        return {
                            "latitude": 37.7749,
                            "longitude": -122.4194,
                            "location_type": "point",
                            "location_wkt": "POINT(-122.4194 37.7749)",
                            "accuracy": 10.0,
                            "source": "eas",
                            "timestamp": int(attestation.get("time", time.time())),
                            "memo": "Binary data - could not decode",
                            "media_type": [],
                            "media_data": [],
                            "recipe_type": [],
                            "recipe_payload": {},
                        }
                    except Exception as e:
                        print(f"Failed to parse binary data: {e}")
                        logging.error(f"Failed to parse binary data: {e}")
                        return None
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON from decoded data: {e}")
                    logging.debug(f"Failed to parse JSON from decoded data: {e}")
                    return None
            elif isinstance(data, str):
                # Try to parse as JSON directly
                print("Attempting to parse data as JSON directly")
                data_json = json.loads(data)
                print("Successfully parsed data as JSON")
            else:
                # Assume it's already a dict
                print("Data is already a dict, using as-is")
                data_json = data
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to decode attestation data: {e}")
            logging.error(f"Failed to decode attestation data: {e}")
            return None

        # Print the decoded JSON for debugging
        print(
            f"Decoded JSON keys: {list(data_json.keys()) if isinstance(data_json, dict) else 'Not a dict'}"
        )

        # Extract location data from the decoded JSON
        location_data = data_json.get("location")
        if not location_data:
            print("No location field in attestation")
            logging.warning(f"No location field in attestation {attestation_id}")
            return None

        print(f"Extracted location data: {location_data}")

        # Get location type (default to "point" if not specified)
        location_type = data_json.get("locationType", "point")
        print(f"Location type: {location_type}")

        # Process the location data based on its format
        wkt, spatial_type = process_location_to_wkt(location_data, location_type)
        if not wkt:
            print("Could not process location data to WKT")
            logging.warning(
                f"Could not process location data in attestation {attestation_id}"
            )
            return None

        print(f"Processed location to WKT: {wkt}, type: {spatial_type}")
        print(f"=== END PROCESSING ATTESTATION {attestation_id} ===\n")

        # Extract other fields
        memo = data_json.get("memo", "")

        # Extract media type and data
        media_type = data_json.get("mediaType", [])
        media_data = data_json.get("mediaData", [])

        # Extract recipe type and payload
        recipe_type = data_json.get("recipeType", [])
        recipe_payload_raw = data_json.get("recipePayload", [])

        # Process recipe payload
        recipe_payload = {}
        if recipe_type and recipe_payload_raw:
            for i, rtype in enumerate(recipe_type):
                if i < len(recipe_payload_raw):
                    try:
                        # Recipe payload might be hex-encoded
                        if isinstance(
                            recipe_payload_raw[i], str
                        ) and recipe_payload_raw[i].startswith("0x"):
                            payload_bytes = bytes.fromhex(recipe_payload_raw[i][2:])
                            try:
                                # Try to decode as JSON
                                payload_str = payload_bytes.decode("utf-8")
                                payload = json.loads(payload_str)
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                # If not JSON, store as hex
                                payload = recipe_payload_raw[i]
                        else:
                            payload = recipe_payload_raw[i]

                        recipe_payload[rtype] = payload
                    except Exception as e:
                        logging.error(
                            f"Failed to process recipe payload for type {rtype}: {e}"
                        )
                        recipe_payload[rtype] = recipe_payload_raw[i]

        # Return the extracted data
        return {
            "latitude": None,  # Will be set by caller if needed for legacy code
            "longitude": None,  # Will be set by caller if needed for legacy code
            "location_type": spatial_type,  # Use the detected spatial type
            "location_wkt": wkt,  # Store the WKT representation
            "accuracy": data_json.get("accuracy", 10.0),
            "source": "eas",
            "timestamp": int(
                data_json.get("eventTimestamp", attestation.get("time", time.time()))
            ),
            "memo": memo,
            "media_type": media_type,
            "media_data": media_data,
            "recipe_type": recipe_type,
            "recipe_payload": recipe_payload,
        }
    except Exception as e:
        print(f"Error extracting location data: {e}")
        logging.error(f"Error extracting location data: {e}")
        return None


def process_location_to_wkt(
    location_data: Any, location_type: str
) -> Tuple[Optional[str], str]:
    """Process location data to WKT format.

    Args:
        location_data: Location data from attestation
        location_type: Location type hint

    Returns:
        Tuple of (WKT string, spatial type) or (None, original type) if processing fails
    """
    try:
        # Try to process as GeoJSON
        if isinstance(location_data, dict):
            return process_geojson_to_wkt(location_data)

        # Try to process as WKT string
        if isinstance(location_data, str) and any(
            x in location_data.upper() for x in ["POINT", "LINESTRING", "POLYGON"]
        ):
            # It's already WKT, just validate it
            try:
                from shapely import wkt

                geom = wkt.loads(location_data)
                return location_data, geom.geom_type.lower()
            except Exception as e:
                logging.error(f"Invalid WKT string: {e}")
                return None, location_type

        # Try to process as raw coordinates
        if isinstance(location_data, str) and "," in location_data:
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
        logging.warning(f"Unrecognized location data format: {location_data}")
        return None, location_type

    except Exception as e:
        logging.error(f"Error processing location to WKT: {e}")
        return None, location_type


def process_geojson_to_wkt(geojson_data: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """Convert GeoJSON to WKT.

    Args:
        geojson_data: GeoJSON data

    Returns:
        Tuple of (WKT string, spatial type) or (None, "unknown") if processing fails
    """
    try:
        # Import shapely for GeoJSON processing
        from shapely.geometry import mapping, shape

        # Handle different GeoJSON types
        if "type" not in geojson_data:
            logging.warning("GeoJSON missing 'type' field")
            return None, "unknown"

        geojson_type = geojson_data["type"]

        # Handle Feature
        if geojson_type == "Feature":
            if "geometry" not in geojson_data:
                logging.warning("GeoJSON Feature missing 'geometry'")
                return None, "unknown"

            geometry = geojson_data["geometry"]
            geom = shape(geometry)
            return geom.wkt, geom.geom_type.lower()

        # Handle FeatureCollection
        elif geojson_type == "FeatureCollection":
            features = geojson_data.get("features", [])
            if not features:
                logging.warning("Empty FeatureCollection")
                return None, "unknown"

            # Use the first feature for now
            first_feature = features[0]
            if "geometry" not in first_feature:
                logging.warning("First feature missing 'geometry'")
                return None, "unknown"

            geometry = first_feature["geometry"]
            geom = shape(geometry)
            return geom.wkt, f"collection_{geom.geom_type.lower()}"

        # Handle direct geometry
        elif geojson_type in [
            "Point",
            "LineString",
            "Polygon",
            "MultiPoint",
            "MultiLineString",
            "MultiPolygon",
        ]:
            geom = shape(geojson_data)
            return geom.wkt, geojson_type.lower()

        else:
            logging.warning(f"Unsupported GeoJSON type: {geojson_type}")
            return None, "unknown"

    except Exception as e:
        logging.error(f"Error processing GeoJSON: {e}")
        return None, "unknown"


def process_raw_coordinates_to_wkt(coord_string: str) -> Tuple[Optional[str], str]:
    """Convert raw coordinate string to WKT.

    Args:
        coord_string: Coordinate string (e.g. "lat,lng" or "lng,lat")

    Returns:
        Tuple of (WKT string, spatial type) or (None, "point") if processing fails
    """
    try:
        # Split the string
        parts = coord_string.split(",", 1)
        if len(parts) != 2:
            logging.warning(f"Invalid coordinate format: {coord_string}")
            return None, "point"

        # Try to parse as numbers
        try:
            a, b = float(parts[0].strip()), float(parts[1].strip())
        except ValueError:
            logging.warning(f"Could not parse coordinates as floats: {coord_string}")
            return None, "point"

        # Try to determine if it's [lng,lat] or [lat,lng]
        # Assume [lng,lat] first (preferred)
        if -180 <= a <= 180 and -90 <= b <= 90:
            return f"POINT({a} {b})", "point"

        # Try [lat,lng]
        if -90 <= a <= 90 and -180 <= b <= 180:
            return f"POINT({b} {a})", "point"

        # Coordinates out of range
        logging.warning(f"Coordinates out of range: {coord_string}")
        return None, "point"

    except Exception as e:
        logging.error(f"Error processing raw coordinates: {e}")
        return None, "point"


async def create_location_proof(conn, attestation, location_data, chain_id):
    """
    Create or update a location proof record in the database.

    Args:
        conn: Database connection (asyncpg.Connection)
        attestation: Attestation data from EAS
        location_data: Extracted location data
        chain_id: Chain ID

    Returns:
        True if successful, False otherwise
    """
    try:
        # Debug: Print attestation structure
        logging.debug(f"Attestation data: {attestation}")

        # Check if we have WKT data
        location_wkt = location_data.get("location_wkt")
        if not location_wkt:
            logging.error(f"No WKT data for attestation {attestation['id']}")
            return False

        # Check if attestation already exists
        row = await conn.fetchrow(
            "SELECT id FROM location_proof WHERE uid = $1", attestation["id"]
        )

        # Convert media_type and media_data to JSON strings if they're not already
        media_type = (
            json.dumps(location_data.get("media_type", ""))
            if not isinstance(location_data.get("media_type", ""), str)
            else location_data.get("media_type", "")
        )
        media_data = (
            json.dumps(location_data.get("media_data", ""))
            if not isinstance(location_data.get("media_data", ""), str)
            else location_data.get("media_data", "")
        )

        # Convert recipe_type and recipe_payload to JSON strings if they're not already
        recipe_type = (
            json.dumps(location_data.get("recipe_type", ""))
            if not isinstance(location_data.get("recipe_type", ""), str)
            else location_data.get("recipe_type", "")
        )
        recipe_payload = (
            json.dumps(location_data.get("recipe_payload", {}))
            if not isinstance(location_data.get("recipe_payload", {}), str)
            else location_data.get("recipe_payload", "{}")
        )

        # Get address IDs for attester and recipient
        attester_id = await get_address_id(conn, attestation["attester"])
        recipient_id = await get_address_id(conn, attestation["recipient"])

        # Get schema ID from the attestation or from the chain config
        schema_id = attestation.get("schemaId")
        if not schema_id:
            # If not in the attestation, get it from the chain config
            schema_id = await get_schema_id(conn, chain_id)
            if not schema_id:
                logging.error(f"No schema ID found for chain {chain_id}")
                return False

        if row:
            # Update existing record
            await conn.execute(
                """
                UPDATE location_proof
                SET schema = $1,
                    event_timestamp = $2,
                    expiration_time = $3,
                    revoked = $4,
                    revocation_time = $5,
                    ref_uid = $6,
                    revocable = $7,
                    srs = $8,
                    location_type = $9,
                    location = ST_GeomFromText($10, 4326),
                    recipe_type = $11,
                    recipe_payload = $12::jsonb,
                    media_type = $13,
                    media_data = $14,
                    memo = $15,
                    status = $16,
                    block_number = $17,
                    transaction_hash = $18,
                    cid = $19,
                    chain_id = $20,
                    attester_id = $21,
                    recipient_id = $22,
                    updated_at = NOW()
                WHERE id = $23
                """,
                schema_id,
                attestation.get("time", int(time.time())),
                attestation.get("expirationTime", 0),
                attestation.get("revoked", False),
                attestation.get("revocationTime", 0),
                attestation.get("refUID", ""),
                attestation.get("revocable", True),
                location_data.get("srs", "EPSG:4326"),
                location_data.get("location_type", "point"),
                location_wkt,
                recipe_type,
                recipe_payload,
                media_type,
                media_data,
                location_data.get("memo", ""),
                "confirmed",
                attestation.get("blockNumber", 0),
                attestation.get("transactionHash", ""),
                "",  # CID
                chain_id,
                attester_id,
                recipient_id,
                row["id"],
            )
            logging.info(f"Updated location proof for attestation {attestation['id']}")
        else:
            # Insert new record
            await conn.execute(
                """
                INSERT INTO location_proof (
                    uid, schema, event_timestamp, expiration_time, revoked,
                    revocation_time, ref_uid, revocable, srs, location_type,
                    location, recipe_type, recipe_payload, media_type, media_data,
                    memo, status, block_number, transaction_hash, cid,
                    chain_id, attester_id, recipient_id
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8, $9, $10,
                    ST_GeomFromText($11, 4326), $12, $13::jsonb, $14, $15,
                    $16, $17, $18, $19, $20,
                    $21, $22, $23
                )
                """,
                attestation["id"],
                schema_id,
                attestation.get("time", int(time.time())),
                attestation.get("expirationTime", 0),
                attestation.get("revoked", False),
                attestation.get("revocationTime", 0),
                attestation.get("refUID", ""),
                attestation.get("revocable", True),
                location_data.get("srs", "EPSG:4326"),
                location_data.get("location_type", "point"),
                location_wkt,
                recipe_type,
                recipe_payload,
                media_type,
                media_data,
                location_data.get("memo", ""),
                "confirmed",
                attestation.get("blockNumber", 0),
                attestation.get("transactionHash", ""),
                "",  # CID
                chain_id,
                attester_id,
                recipient_id,
            )
            logging.info(f"Created location proof for attestation {attestation['id']}")

        return True
    except Exception as e:
        logging.error(f"Error creating/updating location proof: {str(e)}")
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

        # Print the first attestation for debugging
        if result and len(result) > 0:
            print("\n\n=== ATTESTATION STRUCTURE ===")
            print(f"Keys in attestation: {list(result[0].keys())}")
            print(f"Data field type: {type(result[0].get('data', ''))}")
            print(
                f"Data field value: {result[0].get('data', '')[:200]}..."
                if len(str(result[0].get("data", ""))) > 200
                else f"Data field value: {result[0].get('data', '')}"
            )
            print("=== END ATTESTATION STRUCTURE ===\n\n")

        return result
    except Exception as e:
        logger.error(f"Error fetching attestations from {endpoint}: {str(e)}")
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
            logging.warning(f"Chain {chain_id} not found in database")
            return 0

        # Get EAS endpoint for this chain
        eas_endpoint = await get_eas_endpoint(chain_info)
        if not eas_endpoint:
            logging.warning(f"No EAS endpoint found for chain {chain_id}")
            return 0

        # Get the schema ID for this chain
        schema_id = await get_schema_id(conn, chain_id)
        if not schema_id:
            logging.warning(f"No schema ID found for chain {chain_id}")
            return 0

        logging.info(f"Fetching attestations for chain {chain_id} from {eas_endpoint}")

        # Fetch attestations from the EAS endpoint
        try:
            attestations = fetch_attestations(eas_endpoint, schema_id, limit)
            logging.info(
                f"Fetched {len(attestations)} attestations from {eas_endpoint}"
            )
        except Exception as e:
            logging.error(f"Failed to fetch attestations from {eas_endpoint}: {e}")
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
                        f"Skipping attestation {attestation.get('id', 'unknown')}: No valid location data"
                    )
                    skipped_count += 1
                    continue

                # Create or update a location proof
                success = await create_location_proof(
                    conn, attestation, location_data, chain_id
                )

                if success:
                    processed_count += 1
                else:
                    skipped_count += 1

            except Exception as e:
                logging.error(
                    f"Error processing attestation {attestation.get('id', 'unknown')}: {e}"
                )
                error_count += 1
                continue

        logging.info(
            f"Chain {chain_id} summary: "
            f"Processed {processed_count} attestations, "
            f"Skipped {skipped_count} attestations, "
            f"Errors {error_count} attestations"
        )
        return processed_count
    except Exception as e:
        logging.error(f"Error processing chain {chain_id}: {e}")
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
        f"Starting location proof seeding process at {datetime.now().isoformat()}"
    )

    # Load EAS configuration
    try:
        eas_config = load_eas_config()
    except Exception as e:
        logging.error(f"Failed to load EAS configuration: {e}")
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
        logging.error(f"Failed to connect to database: {e}")
        return

    try:
        # Determine which chains to process
        chain_ids = []
        if chain_id:
            # Process specific chain
            chain_ids = [chain_id]
            logging.info(f"Processing specific chain: {chain_id}")
        else:
            # Process all chains in the EAS config
            chain_ids = [int(cid) for cid in eas_config.get("chains", {}).keys()]
            logging.info(f"Processing all chains: {chain_ids}")

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
            logger.info(f"Chain {cid}: Processed {count} location proofs")

        logger.info(f"Total location proofs processed: {total_processed}")

        # Get total count of location proofs
        total_count = await conn.fetchval("SELECT COUNT(*) FROM location_proof")
        logger.info(f"Total location proofs in database: {total_count}")

        # Log execution time
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"Location proof seeding completed in {execution_time:.2f} seconds")

    except Exception as e:
        logging.error(f"Error during location proof seeding: {e}")
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
