"""EAS Integration Service for the Astral API.

This module provides functionality to interact with the Ethereum Attestation Service
via its GraphQL API, fetching and processing attestations for location proofs.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from sqlalchemy import select
from sqlalchemy.engine.result import ScalarResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionFactory
from app.models.address import Address
from app.models.chain import Chain
from app.models.location_proof import LocationProof
from app.models.sync_state import SyncState
from app.services.schema_encoder import SchemaEncoder

# Configure logging
logger = logging.getLogger(__name__)

# Load EAS config
config_path = Path(__file__).parent.parent.parent / "config" / "EAS-config.json"
with open(config_path) as f:
    EAS_CONFIG = json.load(f)


class EASIntegrationService:
    """Service for integrating with Ethereum Attestation Service (EAS).

    This service handles fetching attestations from EAS GraphQL endpoints,
    processing them, and storing them in the database as location proofs.
    """

    def __init__(self, get_session: SessionFactory):
        """Initialize the EAS integration service.

        Args:
            get_session: Function that returns an AsyncSession
        """
        self.get_session = get_session
        self.clients: Dict[int, Client] = {}
        self.schema_uids: Dict[int, str] = {}
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize the service by setting up GraphQL clients for each chain.

        This method fetches all chains from the database and creates a GraphQL client
        for each one that has an EAS endpoint configured.
        """
        if self.initialized:
            return

        async for session in self.get_session():
            # Get all chains with EAS endpoints
            query = select(Chain)
            chains_result = await session.execute(query)
            chains: ScalarResult[Chain] = chains_result.scalars()
            chains_list = [chain for chain in chains]

            logger.info(f"Found {len(chains_list)} chains")

            for chain in chains_list:
                logger.info(f"Processing chain {chain.chain_id}: {chain.name}")
                logger.info(f"Chain features: {chain.features}")

                # Check if chain has EAS endpoint in its features
                eas_endpoint = self._get_eas_endpoint(chain)
                logger.info(f"EAS endpoint: {eas_endpoint}")

                if not eas_endpoint:
                    logger.warning(f"Chain {chain.name} has no EAS endpoint configured")
                    continue

                try:
                    # Create GraphQL client for this chain
                    transport = AIOHTTPTransport(url=eas_endpoint)
                    client = Client(
                        transport=transport,
                        fetch_schema_from_transport=True,
                    )
                    self.clients[chain.chain_id] = client
                    logger.info(f"Created client for chain {chain.chain_id}")

                    # Get schema UID from config
                    schema_uid = self._get_schema_uid_from_config(chain.chain_id)
                    logger.info(f"Got schema UID from config: {schema_uid}")

                    if not schema_uid:
                        logger.warning(
                            f"No schema UID configured for chain {chain.name}"
                        )
                        # Remove the client if we couldn't get the schema UID
                        self.clients.pop(chain.chain_id, None)
                        continue

                    self.schema_uids[chain.chain_id] = schema_uid

                    logger.info(
                        f"Initialized EAS client for chain {chain.name} "
                        f"with schema {schema_uid}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error initializing client for chain {chain.name}: {e}"
                    )
                    # Clean up if there was an error
                    self.clients.pop(chain.chain_id, None)
                    continue

        self.initialized = True
        logger.info("EAS Integration Service initialized")

    async def sync_attestations(
        self, chain_ids: Optional[List[int]] = None
    ) -> Dict[int, int]:
        """Synchronize attestations from EAS for specified chains.

        Args:
            chain_ids: List of chain IDs to sync, or None for all chains

        Returns:
            Dict mapping chain IDs to the number of new attestations synced
        """
        if not self.initialized:
            await self.initialize()

        results: Dict[int, int] = {}

        # If no chain IDs specified, sync all chains
        if chain_ids is None:
            chain_ids = list(self.clients.keys())

        # Process each chain
        for chain_id in chain_ids:
            if chain_id not in self.clients:
                logger.warning(f"No EAS client for chain ID {chain_id}")
                continue

            count = await self._sync_chain_attestations(chain_id)
            results[chain_id] = count

        return results

    async def _sync_chain_attestations(self, chain_id: int) -> int:
        """Synchronize attestations for a specific chain.

        Args:
            chain_id: Chain ID to sync

        Returns:
            Number of new attestations synced
        """
        if chain_id not in self.clients or chain_id not in self.schema_uids:
            logger.warning(f"Chain ID {chain_id} not properly initialized")
            return 0

        client = self.clients[chain_id]
        schema_uid = self.schema_uids[chain_id]

        # Get sync state for this chain and schema
        async for session in self.get_session():
            sync_state = await self._get_or_create_sync_state(
                session, chain_id, schema_uid
            )

            # Query for new attestations
            attestations = await self._query_attestations(
                client,
                schema_uid,
                sync_state.last_block_number,
                sync_state.last_timestamp,
                sync_state.last_attestation_uid,
            )

            if not attestations:
                logger.info(f"No new attestations for chain {chain_id}")
                return 0

            # Process and store attestations
            count = await self._process_attestations(session, chain_id, attestations)

            # Update sync state
            if count > 0 and attestations:
                last_attestation = attestations[-1]
                sync_state.last_block_number = int(last_attestation["blockNumber"])
                sync_state.last_timestamp = int(last_attestation["time"])
                sync_state.last_attestation_uid = last_attestation["id"]
                await session.commit()

            logger.info(f"Synced {count} attestations for chain {chain_id}")
            return count

        # This return is needed to satisfy mypy
        return 0

    async def _get_or_create_sync_state(
        self, session: AsyncSession, chain_id: int, schema_uid: str
    ) -> SyncState:
        """Get or create a sync state record for the given chain and schema.

        Args:
            session: Database session
            chain_id: Chain ID
            schema_uid: Schema UID

        Returns:
            SyncState object
        """
        # Query for existing sync state
        result = await session.execute(
            select(SyncState).where(
                SyncState.chain_id == chain_id, SyncState.schema_uid == schema_uid
            )
        )
        sync_state = result.scalars().first()

        # Create new sync state if none exists
        if not sync_state:
            sync_state = SyncState(
                chain_id=chain_id,
                schema_uid=schema_uid,
                last_block_number=0,
                last_timestamp=0,
                last_attestation_uid=None,
            )
            session.add(sync_state)
            await session.commit()

        return sync_state

    async def _query_attestations(
        self,
        client: Client,
        schema_uid: str,
        last_block: int,
        last_timestamp: int,
        last_uid: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Query EAS GraphQL API for new attestations.

        Args:
            client: GraphQL client
            schema_uid: Schema UID to query
            last_block: Last processed block number
            last_timestamp: Last processed timestamp
            last_uid: Last processed attestation UID

        Returns:
            List of attestation data dictionaries
        """
        try:
            # Build the query
            query = gql(
                """
                query GetAttestations($where: AttestationWhereInput!) {
                    attestations(where: $where, orderBy: {time: asc}, first: 100) {
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
            )

            # Build the where clause
            where = {
                "schemaId": {"equals": schema_uid},
                "time": {"gt": str(last_timestamp)},
                "blockNumber": {"gt": str(last_block)},
            }

            if last_uid:
                where["id"] = {"gt": last_uid}

            # Execute the query
            result = await client.execute_async(query, variable_values={"where": where})

            return cast(List[Dict[str, Any]], result.get("attestations", []))

        except Exception as e:
            logger.error(f"Error querying EAS API: {e}")
            return []

    async def _process_attestations(
        self, session: AsyncSession, chain_id: int, attestations: List[Dict[str, Any]]
    ) -> int:
        """Process and store attestations in the database.

        Args:
            session: Database session
            chain_id: Chain ID
            attestations: List of attestation data from EAS API

        Returns:
            Number of attestations successfully processed
        """
        count = 0

        # Get the chain's ID from its chain_id
        chain_result = await session.execute(
            select(Chain).where(Chain.chain_id == chain_id)
        )
        chain = chain_result.scalars().first()
        if not chain:
            logger.error(f"Chain with chain_id {chain_id} not found")
            return 0

        for attestation in attestations:
            try:
                # Parse attestation data
                parsed_data = self._parse_attestation_data(attestation)
                if not parsed_data:
                    logger.warning(
                        f"Failed to parse attestation data for {attestation['id']}"
                    )
                    continue

                # Get or create addresses
                attester_address = await self._get_or_create_address(
                    session, attestation["attester"]
                )
                recipient_address = await self._get_or_create_address(
                    session, attestation["recipient"]
                )

                # Create location proof
                location_proof = LocationProof(
                    chain_id=chain.id,  # Use chain.id instead of chain_id
                    attester=attester_address,
                    recipient=recipient_address,
                    **parsed_data,
                )
                session.add(location_proof)
                await session.flush()  # Get ID without committing
                count += 1

            except Exception as e:
                logger.error(f"Error processing attestation: {e}")
                continue

        if count > 0:
            await session.commit()

        return count

    def _parse_attestation_data(
        self, attestation: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Parse the attestation data to extract the relevant information.

        Args:
            attestation: The attestation data to parse.

        Returns:
            The parsed attestation data as a dictionary, or None if parsing fails.
        """
        try:
            # Get the encoded data from the attestation
            encoded_data = attestation.get("data")
            if not encoded_data:
                logger.error("No data field in attestation")
                return None

            # Convert hex string to bytes if necessary
            if isinstance(encoded_data, str) and encoded_data.startswith("0x"):
                encoded_data = bytes.fromhex(encoded_data[2:])
            elif not isinstance(encoded_data, bytes):
                logger.error(f"Invalid data format: {type(encoded_data)}")
                return None

            # Decode the data using our SchemaEncoder
            decoded_data = SchemaEncoder.decode_data(encoded_data)

            # Validate the decoded data
            SchemaEncoder.validate_decoded_data(decoded_data)

            return decoded_data

        except Exception as e:
            logger.error(f"Error parsing attestation data: {e}")
            return None

    async def _get_or_create_address(
        self, session: AsyncSession, address: str
    ) -> Address:
        """Get or create an address record.

        Args:
            session: Database session
            address: Ethereum address

        Returns:
            Address object
        """
        # Normalize address
        normalized_address = address.lower()

        # Query for existing address
        result = await session.execute(
            select(Address).where(Address.address == normalized_address)
        )
        addr = result.scalars().first()

        # Create new address if none exists
        if not addr:
            addr = Address(address=normalized_address, ens_name=None, display_name=None)
            session.add(addr)
            await session.flush()  # Get ID without committing

        return addr

    def _get_schema_uid_from_config(self, chain_id: int) -> Optional[str]:
        """Get the schema UID for a chain from the EAS config file.

        Args:
            chain_id: Chain ID to get schema UID for

        Returns:
            Schema UID if found in config, None otherwise
        """
        chain_config = EAS_CONFIG.get("chains", {}).get(str(chain_id))
        if not chain_config:
            return None
        schema_uid = chain_config.get("schemaUID")
        if not isinstance(schema_uid, str):
            return None
        return schema_uid if schema_uid else None

    def _get_eas_endpoint(self, chain: Chain) -> Optional[str]:
        """Get the EAS GraphQL endpoint for a chain.

        Args:
            chain: Chain model instance

        Returns:
            EAS endpoint URL or None if not configured
        """
        # Check if chain has EAS endpoint in its features
        features = chain.features
        logger.info(f"Getting EAS endpoint from features: {features}")

        # Handle the case where features is already a list
        if isinstance(features, list):
            logger.info("Features is a list")
            eas_feature = next(
                (f for f in features if isinstance(f, dict) and f.get("name") == "EAS"),
                None,
            )
        else:
            # Handle the case where features is a dictionary
            logger.info("Features is a dictionary")
            features_dict = features or {}
            eas_feature = next(
                (
                    f
                    for f in features_dict.get("features", [])
                    if f.get("name") == "EAS"
                ),
                None,
            )

        logger.info(f"Found EAS feature: {eas_feature}")

        if not eas_feature:
            return None

        endpoint = eas_feature.get("url") or eas_feature.get("graphql")
        if not isinstance(endpoint, str):
            return None
        return endpoint if endpoint else None

    def _create_graphql_client(self, endpoint: str) -> Client:
        """Create a GraphQL client for the given endpoint.

        Args:
            endpoint: GraphQL endpoint URL

        Returns:
            Configured GraphQL client
        """
        transport = AIOHTTPTransport(url=endpoint)
        client = Client(
            transport=transport,
            fetch_schema_from_transport=True,
        )
        return client
