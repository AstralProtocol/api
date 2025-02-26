# Composer Notes

## Checkpoint: Task 3.3 Completion - Error Handling & Validation (2024-07-10)

### Overall Assessment

We're on the right track with the Astral API implementation, but there are some areas where we could improve:

#### Strengths

1. **OGC API Features Compliance**: We've successfully implemented a robust API that follows the OGC API Features specification, including proper endpoint structure, response formats, and error handling.

2. **Validation Logic**: The validation models for parameters like bbox, datetime, and GeoJSON are thorough and well-tested, providing clear error messages.

3. **Test Coverage**: We have comprehensive tests covering various aspects of the API, including error handling, metadata/links, and advanced queries.

4. **Code Organization**: The codebase is well-structured with clear separation of concerns between routers, models, and validation logic.

#### Areas for Improvement

1. **Mock Data vs. Real Implementation**: We've built a solid framework, but many endpoints return mock data or empty collections. The actual database integration and EAS attestation handling still need to be implemented.

2. **Error Message Consistency**: We had to fix some error message formats to match test expectations, which suggests we could have been more consistent from the start.

3. **Code Duplication**: There's some repetition in the validation logic and error response creation that could be refactored into helper functions.

4. **Documentation**: While we have docstrings, we could improve the API documentation with more examples and usage scenarios.

### Progress on Implementation Plan

Looking at our implementation plan, we've completed:
- Initial project setup
- Database schema & migrations
- Core OGC API Features implementation
- Advanced query capabilities
- Metadata and links structure
- Error handling & validation

We're now ready to move on to Task 4.1: EAS Integration, which is where the real value of the API will start to emerge. This is a critical part of the project as it connects our API to the blockchain attestations.

### Code Volume Considerations

We have written a lot of code, particularly in the `location_proofs.py` file. This is partly due to the comprehensive nature of the OGC API Features specification, which requires many endpoints and detailed response structures.

However, we should be cautious about the file size growing too large. As we move forward with EAS integration, we might want to consider:

1. Breaking down `location_proofs.py` into smaller modules (e.g., separating models, validation, and routes)
2. Creating more reusable components to reduce duplication
3. Implementing a service layer to handle business logic separately from the API routes

### Next Steps

The EAS integration will be crucial. We need to:
1. Implement the service functions to interact with the EAS GraphQL endpoint
2. Design a robust scheduler for polling new attestations
3. Ensure proper storage and status tracking of attestations

This will transform our API from a well-structured but mostly empty shell into a functional system that provides real value by making attestations available through a standardized geospatial API.

## Feature PRD: Automated Chain Integration System

### Overview

The Astral API needs a robust, automated system for managing blockchain network integrations. Currently, chain data is seeded manually using the `seed_chains.py` script, but this process should be automated and centralized around the `config/EAS-config.json` file, which serves as the source of truth for supported chains and their EAS schema deployments.

### Goals

1. Create a single source of truth for supported chains in `config/EAS-config.json`
2. Automate the process of adding new chains to the database when the configuration is updated
3. Ensure the EAS synchronization system automatically recognizes and begins syncing new chains
4. Provide a seamless developer experience for adding support for new blockchain networks

### Technical Requirements

#### 1. Configuration Management

- **Source of Truth**: The `config/EAS-config.json` file will be the definitive source for all supported chains
- **Schema**: Standardize the JSON schema for chain configurations to include:
  ```json
  {
    "chains": {
      "<chainId>": {
        "chain": "<chain-identifier>",
        "deploymentBlock": <block-number>,
        "rpcUrl": "<rpc-endpoint>",
        "easContractAddress": "<contract-address>",
        "schemaUID": "<schema-uid>",
        "graphqlEndpoint": "<eas-graphql-endpoint>"
      }
    }
  }
  ```
- **Validation**: Implement JSON schema validation to ensure all required fields are present and correctly formatted

#### 2. Configuration Watcher

- **Startup Detection**: When the API starts, it should compare the chains in `EAS-config.json` with those in the database
- **Change Detection**: Implement a mechanism to detect when `EAS-config.json` is updated (either through file watching or a dedicated endpoint)
- **Versioning**: Add a version field to the config file to track changes and avoid unnecessary processing

#### 3. Database Integration

- **Chain Seeding**: Enhance the existing `seed_chains.py` script to:
  - Accept the path to `EAS-config.json` as an input
  - Extract chain IDs and GraphQL endpoints from the config
  - Fetch additional chain metadata from ethereum-lists/chains
  - Merge this data and update the database
- **Idempotent Operations**: Ensure all database operations are idempotent to prevent duplicates or data corruption
- **Transaction Safety**: Use database transactions to ensure atomic updates

#### 4. EAS Synchronization Integration

- **Dynamic Chain Registration**: Modify the EAS sync service to dynamically register chains from the database
- **Sync State Management**: Create or update `SyncState` records for new chains automatically
- **Backfill Logic**: Implement logic to backfill attestations from the `deploymentBlock` specified in the config

#### 5. API Updates

- **Chain Endpoints**: Ensure the API exposes endpoints to:
  - List all supported chains
  - Get details about a specific chain
  - Check the sync status for each chain
- **Documentation**: Update OpenAPI documentation to reflect these endpoints

### Implementation Plan

1. **Phase 1: Configuration Management**
   - Update `EAS-config.json` schema to include all necessary fields
   - Create a configuration loader service that validates and parses the config
   - Add unit tests for the configuration loader

2. **Phase 2: Enhanced Chain Seeding**
   - Refactor `seed_chains.py` to use the configuration loader
   - Add functionality to merge EAS-specific data with ethereum-lists data
   - Implement database update logic with proper error handling

3. **Phase 3: Startup Integration**
   - Modify the API startup sequence to check for new chains
   - Create a service to compare config chains with database chains
   - Implement the automatic seeding process on startup

4. **Phase 4: EAS Sync Integration**
   - Update the EAS sync service to dynamically load chains from the database
   - Implement logic to create sync states for new chains
   - Add monitoring for sync progress across all chains

5. **Phase 5: Testing & Documentation**
   - Create end-to-end tests for the entire chain addition process
   - Update API documentation to reflect the new functionality
   - Create developer documentation for adding new chains

### Technical Considerations

#### Database Impact

- Adding new chains should not disrupt existing data
- Foreign key relationships must be maintained (e.g., location_proof to chain)
- Consider the impact on query performance as the number of chains grows

#### Error Handling

- Implement robust error handling for network issues when fetching chain data
- Create a mechanism to retry failed operations
- Log detailed error information for debugging

#### Security

- Validate all external data before inserting into the database
- Ensure RPC URLs and contract addresses are properly sanitized
- Consider rate limiting for chain data fetching to prevent abuse

#### Performance

- Optimize database queries to handle multiple chains efficiently
- Consider caching chain data to reduce database load
- Implement batched processing for large numbers of chains

### Success Metrics

1. **Reliability**: 100% success rate when adding new chains
2. **Speed**: Complete chain addition process in under 30 seconds
3. **Automation**: Zero manual steps required to add a new chain
4. **Consistency**: Chain data in the database matches `EAS-config.json` exactly

### Future Enhancements

1. **Admin Interface**: Create a web interface for managing chains
2. **Chain Health Monitoring**: Add monitoring for chain RPC endpoints and EAS services
3. **Chain Deprecation**: Implement a process for gracefully deprecating chains
4. **Multi-Environment Support**: Support different chain configurations for development, staging, and production

This system will significantly improve the developer experience by centralizing chain configuration and automating the process of adding new blockchain networks to the Astral API.

## TODO: Attestation Revocation Handling

We need to revisit the handling of attestation revocations in our ETL process. Currently, we check for the `revoked` flag in attestations, but we should also:

1. Implement a mechanism to detect revocation events from EAS contracts
2. Create a process to update existing location proofs when their attestations are revoked
3. Emit appropriate events or notifications when revocations occur
4. Consider how revocations affect the status of location proofs in our API responses
5. Add tests specifically for the revocation flow

This is important for maintaining data integrity, as revoked attestations should not be treated as valid location proofs. We should prioritize this in our next iteration of the ETL process improvements.

## Location Data Processing Strategy

The core value proposition of the Astral API is its ability to handle heterogeneous location data formats from blockchain attestations and serve them as standardized geospatial data. Our approach to location data processing includes:

### Short-term Focus (Current Implementation)
For the initial implementation, we're focusing on handling:
1. Well-formed GeoJSON (Points, LineStrings, Polygons, and single Features)
2. Raw coordinates in both [lon, lat] and [lat, lon] formats

### Data Quality Assessment
We'll implement a basic quality assessment system:
- High quality: Standard format, parsed correctly
- Medium quality: Required interpretation but likely correct
- Low quality: Significantly malformed but best effort made

### Storage Strategy
1. Store original location data exactly as received (for reference and future reprocessing)
2. Convert all geometries to WGS84 (EPSG:4326) for storage in PostGIS
3. Use SRID (integer) instead of SRS (string) for better PostGIS compatibility
4. Track whether data is a collection and how many features it contains

### Complex Geometry Handling
For FeatureCollections and multi-geometries:
1. Store the primary geometry in the PostGIS column for efficient spatial queries
2. Keep the complete original GeoJSON in a JSONB column
3. Flag collections for special handling in API responses

### Future Enhancements
In future iterations, we plan to support:
1. More location types (geohash, h3, w3w, etc.)
2. More sophisticated coordinate order detection
3. Better handling of malformed data
4. Improved API responses for complex geometries

This approach balances immediate needs with future extensibility, allowing us to start with the most common use cases while building a foundation for more complex scenarios.



# Composer Notes: EAS Data Decoding Implementation

## Progress Summary

We've been working on the seed script for location proofs, which fetches attestations from the Ethereum Attestation Service (EAS) and stores them in our database. We've successfully implemented the basic functionality, but we're encountering an issue with decoding the attestation data.

The attestation data is stored in a binary format with a "0x" prefix, indicating it's hex-encoded data that follows the Ethereum ABI encoding format. Our current implementation attempts to decode this as UTF-8, which fails because it's not valid UTF-8 data.

## Current Approach

Our current approach in `extract_location_data` function:

1. Detects hex-encoded data (strings starting with "0x")
2. Attempts to decode it as UTF-8 (which fails)
3. Falls back to a default location (San Francisco coordinates)

This approach works for testing but doesn't extract the actual location data from the attestations.

## Proposed Solution

After analyzing the EAS SDK's SchemaEncoder class, we understand that we need to:

1. Fetch the schema definition for each attestation
2. Use the schema to properly decode the hex-encoded data
3. Extract the location data from the decoded attestation

We'll implement a Python version of the SchemaEncoder that mimics the functionality of the TypeScript version in the EAS SDK.

## Implementation Plan

1. Create a new Python module `app/services/schema_encoder.py` that implements the SchemaEncoder
2. Add a function to fetch schema definitions from the EAS GraphQL endpoint
3. Modify the `extract_location_data` function to use the SchemaEncoder
4. Test with real attestation data from various chains

## Dependencies

We'll need to add the following dependencies to our project:
- `eth-abi`: For ABI encoding/decoding
- `eth-utils`: For Ethereum-specific utilities

## Timeline

- Day 1: Implement the basic SchemaEncoder functionality
- Day 2: Integrate with the seed script and test with real data
- Day 3: Refine and optimize the implementation

## Risks and Mitigations

- **Risk**: Schema definitions might not be easily accessible
  - **Mitigation**: Cache schema definitions locally or hardcode common schemas

- **Risk**: ABI decoding might be complex for certain types
  - **Mitigation**: Start with basic types and add support for complex types incrementally
