# Schema Design Document

## 1. Overview

This document describes the proposed database schema for storing EAS attestations as location proofs along with user and blockchain network metadata. The design targets a PostGIS-enabled PostgreSQL database and outlines four core tables: **Users**, **Addresses**, **Location Proofs (Attestations)**, and **Chains**. This specification covers default EAS attestation attributes, geospatial data, and additional metadata needed for our application.

---

## 2. Table Specifications

### 2.1. Users

| Field      | Type      | Description                                                       |
|------------|-----------|-------------------------------------------------------------------|
| **id**   | Integer (PK) | Unique identifier for each user.                                 |
| **name** | Text      | Optional display name for the user.                               |
| **role** | Text      | Role of the user (e.g., "admin", "user"). Defaults to "user".     |
| **created_at** | Timestamp | Timestamp for when the user was created.                        |
| **updated_at** | Timestamp | Timestamp for when the user was last updated.                   |

**Purpose:**
Stores user-level information independent of blockchain addresses.

---

### 2.2. Addresses

| Field           | Type         | Description                                                                                         |
|-----------------|--------------|-----------------------------------------------------------------------------------------------------|
| **id**          | Integer (PK) | Unique identifier for the address record.                                                         |
| **user_id**     | Integer (FK) | References the Users table to link an address to a user.                                           |
| **address**     | Text         | The blockchain address (e.g., Ethereum address). Must be unique.                                   |
| **label**       | Text         | Optional description or label for the address.                                                    |
| **is_verified** | Boolean      | Indicates if the user has proven ownership via a valid signature.                                   |
| **digital_signature** | Text (Optional) | The digital signature provided to verify address ownership. This field allows re-verification. |
| **created_at**  | Timestamp    | Timestamp for when the address record was created.                                                |
| **updated_at**  | Timestamp    | Timestamp for when the address record was last updated.                                           |

**Purpose:**
Holds blockchain addresses for each user. A single user may have multiple addresses. The **is_verified** flag, together with the stored **digital_signature**, enables re-verification of address ownership—critical for managing private proofs.

---

### 2.3. Location Proofs (Attestations)

| Field              | Type          | Description                                                                                                                       |
|--------------------|---------------|-----------------------------------------------------------------------------------------------------------------------------------|
| **id**           | Integer (PK)   | Unique identifier for the location proof record.                                                                                 |
| **uid**          | Text           | Unique identifier for the attestation (default EAS attribute).                                                                    |
| **schema**       | Text           | Identifier for the attestation schema.                                                                                           |
| **event_timestamp** | BigInt      | Unix timestamp when the event occurred.                                                                                           |
| **expiration_time** | BigInt (Optional) | Unix timestamp when the attestation expires, if applicable.                                                               |
| **revoked**      | Boolean        | Indicates whether the attestation has been revoked. Defaults to false.                                                            |
| **revocation_time** | BigInt (Optional) | Unix timestamp when revoked (if applicable).                                                                            |
| **ref_uid**      | Text (Optional)| Reference UID to another attestation, if applicable.                                                                              |
| **revocable**    | Boolean        | Indicates whether the attestation can be revoked. Defaults to true.                                                                 |

| **srs**          | Text           | Spatial Reference System (e.g., EPSG code).                                                                                        |
| **location_type**| Text           | Describes the type of spatial data (e.g., "point", "polygon", etc.).                                                               |
| **location**     | GEOMETRY       | Flexible geospatial column (supports POINT, LINESTRING, POLYGON, bbox, etc.). SRID should match the srs value.                        |

| **recipe_type**  | Text           | Recipe type stored as plain text.                                                                                                  |
| **recipe_payload** | JSONB        | Recipe payload stored as JSONB for flexibility.                                                                                    |
| **media_type**   | Text           | Media type stored as plain text.                                                                                                     |
| **media_data**   | Text           | Media data (e.g., IPFS CID).                                                                                                         |
| **memo**         | Text (Optional)| Optional memo or note for the attestation.                                                                                           |

| **status**       | Text           | Current status of the attestation (e.g., "onchain (pending)", "onchain (validated)", "IPFS", "off-chain").                             |
| **block_number** | BigInt (Optional)| Blockchain block number when the attestation was recorded, if available.                                                         |
| **transaction_hash** | Text (Optional)| Transaction hash linking to the on-chain attestation, if available.                                                            |
| **cid**          | Text (Optional)| IPFS CID if the attestation is stored on IPFS.                                                                                       |

| **chain_id**     | Integer (FK)   | References the Chains table to indicate which blockchain network the attestation is on.                                             |
| **attester_id**  | Integer (FK)   | References the Addresses table for the attester’s address.                                                                         |
| **recipient_id** | Integer (FK)   | References the Addresses table for the recipient’s address.                                                                        |
| **extra**        | JSONB          | Additional extensible data.                                                                                                          |

**Purpose:**
Stores full attestation data (as location proofs) with default EAS attributes, geospatial data, and on-chain metadata. It includes foreign key references to the **Chains** and **Addresses** tables for additional context.

---

### 2.4. Chains

| Field           | Type         | Description                                                                                                                      |
|-----------------|--------------|----------------------------------------------------------------------------------------------------------------------------------|
| **chain_id**  | Integer (PK)   | Unique identifier for the blockchain network (e.g., 1 for Ethereum Mainnet).                                                    |
| **name**       | Text           | Full name of the blockchain network (e.g., "Ethereum Mainnet").                                                                  |
| **chain**      | Text           | Abbreviated chain symbol (e.g., "ETH").                                                                                          |
| **rpc**        | JSONB          | Array of RPC endpoint URLs.                                                                                                      |
| **faucets**    | JSONB          | Array of faucet URLs (if any).                                                                                                   |
| **native_currency** | JSONB     | JSON object containing native currency details (e.g., { "name": "Ether", "symbol": "ETH", "decimals": 18 }).                        |
| **features**   | JSONB          | Array of feature objects (e.g., [{ "name": "EIP155" }, { "name": "EIP1559" }]).                                                 |
| **info_url**   | Text (Optional)| URL for more information about the blockchain network.                                                                           |
| **short_name** | Text           | Short name for display purposes.                                                                                                 |
| **network_id** | Integer        | Network identifier.                                                                                                              |
| **icon**       | Text           | Identifier for an icon (useful for UI display).                                                                                  |
| **explorers**  | JSONB          | Array of blockchain explorer objects (e.g., [{ "name": "etherscan", "url": "https://etherscan.io", "icon": "etherscan", "standard": "EIP3091" }]). |

**Purpose:**
Holds comprehensive metadata for each blockchain network. This supports linking to block explorers and supplying network-specific details in the API.

---

## 3. Design Considerations

- **Geospatial Flexibility:**
  The **location** field uses a flexible PostGIS GEOMETRY type to accommodate various spatial forms such as POINT, LINESTRING, POLYGON, and bounding boxes. The SRID must be aligned with the provided srs value.

- **Extensible Fields:**
  The **recipe_payload** and **extra** fields are stored as JSONB to handle dynamic and evolving data structures without frequent schema changes.

- **Default Attestation Attributes:**
  All standard EAS attestation fields are included (uid, schema, event_timestamp, expiration_time, revoked, revocation_time, ref_uid, revocable) to fully capture the attestation data.

- **User & Address Separation:**
  Users are managed in a separate table, and each user can have multiple addresses stored in the Addresses table. The **is_verified** flag in Addresses ensures that ownership has been proven via a valid signature, which is crucial for handling private proofs.

- **Foreign Key Relationships:**
  - **attester_id** and **recipient_id** in Location Proofs reference the Addresses table.
  - **chain_id** in Location Proofs references the Chains table.
  - **user_id** in Addresses references the Users table.

- **Chain Metadata:**
  The Chains table is designed to store rich network metadata, supporting features like RPC endpoints, native currency details, and explorer links.

---

## 4. Summary

This schema design document outlines a comprehensive and modular design for storing decentralized geospatial proofs:

- **Users:** Global user data independent of blockchain addresses.
- **Addresses:** Multiple blockchain addresses per user with a verification flag.
- **Location Proofs (Attestations):** Complete attestation data with geospatial, on-chain, and attestation-specific metadata.
- **Chains:** Detailed blockchain network metadata to support API features such as linking to block explorers.

This document should provide a clear blueprint for a database engineer to implement the required schema while ensuring the system is flexible, extensible, and adheres to industry best practices.
