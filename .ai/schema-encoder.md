# EAS Schema Encoding Analysis

## Overview

This document outlines our findings regarding the Ethereum Attestation Service (EAS) data encoding format and our plan to implement a Python version of the SchemaEncoder to properly decode attestation data.

## Current Issue

Our seed script is currently unable to properly decode the attestation data from EAS. The data is stored in a binary format with a "0x" prefix, indicating it's hex-encoded data that follows the Ethereum ABI encoding format based on a specific schema.

## EAS SchemaEncoder Analysis

After examining the [EAS SDK's SchemaEncoder](https://github.com/ethereum-attestation-service/eas-sdk/blob/master/src/schema-encoder.ts), we've identified the following key components:

1. **Schema Parsing**: The SchemaEncoder parses a schema string (e.g., "uint256 eventId, uint8 voteIndex") into a structured format.
2. **Data Encoding**: It converts JavaScript values into ABI-encoded data for on-chain storage.
3. **Data Decoding**: It converts ABI-encoded data back into JavaScript objects.

The encoding/decoding process relies on the ethers.js AbiCoder, which follows the Ethereum Contract ABI specification.

## Implementation Plan

To properly decode the attestation data in our Python script, we need to:

1. Fetch the schema definition for each chain using the schema ID
2. Implement a Python version of the SchemaEncoder that mimics the functionality of the TypeScript version
3. Use the schema to decode the hex-encoded data properly
4. Extract the location data from the decoded attestation

## Technical Requirements

Our Python implementation will need:

1. **ABI Encoding/Decoding**: We'll use the `eth-abi` Python package to handle ABI encoding/decoding
2. **Schema Parsing**: We'll need to parse schema strings into a format compatible with `eth-abi`
3. **Special Type Handling**: Support for special types like IPFS hashes and bytes32 strings

## Next Steps

1. Add a new subtask to the implementation plan
2. Create a Python implementation of the SchemaEncoder
3. Integrate it into our seed script
4. Test with real attestation data from various chains
