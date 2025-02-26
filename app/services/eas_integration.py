"""EAS Integration Service for the Astral API.

This module provides functionality to interact with the Ethereum Attestation Service
via its GraphQL API, fetching and processing attestations for location proofs.
"""

import logging
from typing import Any, Dict, List, Optional, cast

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionFactory
from app.models.address import Address
from app.models.chain import Chain
from app.models.location_proof import LocationProof
from app.models.sync_state import SyncState

# Configure logging
logger = logging.getLogger(__name__)


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
            # Explicitly select only the columns we need, excluding 'id'
            query = select(
                Chain.chain_id,
                Chain.name,
                Chain.chain,
                Chain.rpc,
                Chain.faucets,
                Chain.native_currency,
                Chain.features,
                Chain.info_url,
                Chain.short_name,
                Chain.network_id,
                Chain.icon,
                Chain.explorers,
                Chain.created_at,
                Chain.updated_at,
            )
            chains_result = await session.execute(query)
            chains_data = chains_result.all()

            for chain_data in chains_data:
                # Create a Chain object from the result
                chain = Chain(
                    chain_id=chain_data.chain_id,
                    name=chain_data.name,
                    chain=chain_data.chain,
                    rpc=chain_data.rpc,
                    faucets=chain_data.faucets,
                    native_currency=chain_data.native_currency,
                    features=chain_data.features,
                    info_url=chain_data.info_url,
                    short_name=chain_data.short_name,
                    network_id=chain_data.network_id,
                    icon=chain_data.icon,
                    explorers=chain_data.explorers,
                )

                # Check if chain has EAS endpoint in its features
                eas_endpoint = self._get_eas_endpoint(chain)
                if not eas_endpoint:
                    logger.warning(f"Chain {chain.name} has no EAS endpoint configured")
                    continue

                # Create GraphQL client for this chain
                transport = AIOHTTPTransport(url=eas_endpoint)
                self.clients[chain.chain_id] = Client(
                    transport=transport,
                    fetch_schema_from_transport=True,
                )

                # Get schema UID for this chain
                schema_uid = await self._get_schema_uid(chain.chain_id)
                if not schema_uid:
                    logger.warning(f"No schema UID configured for chain {chain.name}")
                    continue

                self.schema_uids[chain.chain_id] = schema_uid

                logger.info(
                    f"Initialized EAS client for chain {chain.name} "
                    f"with schema {schema_uid}"
                )

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
            last_block: Last synced block number
            last_timestamp: Last synced timestamp
            last_uid: UID of the last synced attestation

        Returns:
            List of attestation data dictionaries
        """
        # Define GraphQL query
        query = gql(
            """
        query GetAttestations($schemaId: String!, $where: AttestationWhereInput) {
          attestations(
            where: $where
            orderBy: { time: asc }
            first: 100
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
        )

        # Build where clause
        where = {
            "schemaId": {"equals": schema_uid},
        }

        # Add time filter if we have a last timestamp
        if last_timestamp > 0:
            where["time"] = {"gt": str(last_timestamp)}

        # Add block filter if we have a last block
        if last_block > 0:
            where["blockNumber"] = {"gt": str(last_block)}

        # Execute query
        try:
            result = await client.execute_async(
                query, variable_values={"schemaId": schema_uid, "where": where}
            )
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
                    schema_uid=attestation["schemaId"],
                    attestation_uid=attestation["id"],
                    event_timestamp=int(attestation["time"]),
                    expiration_time=(
                        int(attestation["expirationTime"])
                        if attestation["expirationTime"]
                        else None
                    ),
                    revoked=attestation["revoked"],
                    revocation_time=(
                        int(attestation["revocationTime"])
                        if attestation["revocationTime"]
                        else None
                    ),
                    ref_uid=attestation["refUID"],
                    revocable=True,  # Assuming all attestations are revocable
                    # Geospatial fields from parsed data
                    srs=parsed_data["srs"],
                    spatial_type=parsed_data["spatial_type"],
                    location_wkt=parsed_data["location_wkt"],
                    # Recipe and media fields from parsed data
                    recipe_type=parsed_data["recipe_type"],
                    recipe_payload=parsed_data["recipe_payload"],
                    media_type=parsed_data["media_type"],
                    media_data=parsed_data["media_data"],
                    memo=parsed_data.get("memo"),
                    # Status and blockchain fields
                    status="onchain (validated)",
                    block_number=int(attestation["blockNumber"]),
                    transaction_hash=attestation["txid"],
                    cid=None,  # No IPFS CID for on-chain attestations
                    # Foreign keys
                    chain_id=chain_id,
                    attester_id=attester_address.id,
                    recipient_id=recipient_address.id,
                    # Additional data
                    extra={"raw_attestation": attestation},
                )

                session.add(location_proof)
                count += 1

            except Exception as e:
                logger.error(f"Error processing attestation {attestation['id']}: {e}")
                continue

        # Commit all changes
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
            # For now, return a mock parsed data structure
            # In a real implementation, this would parse the actual data
            return {
                "srs": "EPSG:4326",
                "spatial_type": "Point",
                "location_wkt": "POINT(0 0)",
                "recipe_type": "mock",
                "recipe_payload": "{}",
                "media_type": "none",
                "media_data": "",
                "memo": "Test attestation",
            }
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

    async def _get_schema_uid(self, chain_id: int) -> Optional[str]:
        """Get the schema UID for a specific chain.

        Args:
            chain_id: The ID of the chain to get the schema UID for.

        Returns:
            The schema UID if found, None otherwise.
        """
        try:
            query = gql(
                """
                query GetSchemas {
                    schemas(where: {
                        name: "AstralAttestation"
                    }) {
                        uid
                    }
                }
                """
            )

            result = await self.clients[chain_id].execute_async(query)
            schemas = result.get("schemas", [])

            if schemas and len(schemas) > 0:
                uid = schemas[0].get("uid")
                return cast(Optional[str], uid)
            return None
        except Exception as e:
            logger.error(f"Error getting schema UID for chain {chain_id}: {e}")
            return None

    def _get_eas_endpoint(self, chain: Chain) -> Optional[str]:
        """Get the EAS GraphQL endpoint for a chain.

        Args:
            chain: Chain object

        Returns:
            EAS endpoint URL or None if not configured
        """
        # Check if chain has EAS endpoint in its features
        features = chain.features or {}
        eas_feature = next(
            (f for f in features.get("features", []) if f.get("name") == "eas"), None
        )

        if not eas_feature:
            return None

        endpoint = eas_feature.get("graphql")
        return cast(Optional[str], endpoint)
