# Astral API: Project Requirements Document
## 1. Overview

### 1.1. Project Objective
Develop a world-class web API for decentralized geospatial data artifacts that:
- **Integrates Seamlessly with EAS:** Uses Ethereum Attestation Service (EAS) such that each attestation issued against our defined schema directly serves as a location proof.
- **Fast Data Propagation:** Ensures that as soon as an attestation is detected, it appears in our API with a status indicator reflecting its state (e.g., onchain (pending), onchain (validated), onchain (invalidated), IPFS, off-chain).
- **Advanced Spatial Queries:** Provides robust geospatial queries (buffer, point-in-polygon, etc.) via a PostGIS-enabled PostgreSQL database.
- **OGC API Compliance:** Meets basic OGC API – Features compliance standards.
- **Modern Authentication:** Implements next-generation authentication via Web3 (e.g., “Sign in with Ethereum”) and supports role-based access for private data.
- **Industry Best Practices:** Follows CI/CD, testing with pytest, type-checking with mypy, containerization via Docker, and maintains a clean, scalable project structure.

### 1.2. Success Criteria
- **Rapid Availability:** Attestations appear in the API as soon as they are detected, with appropriate status updates.
- **Compliance:** The API passes OGC API – Features compliance tests.
- **Integration:** Full attestation data (including geospatial attributes, on-chain metadata like block number, and status) is stored and indexed locally for fast querying.
- **Security:** Robust Web3 authentication with role-based access controls is in place.
- **Quality:** Automated tests (using pytest) and strict type-checking (using mypy) ensure high-quality, maintainable code.
- **Deployment:** A reliable CI/CD pipeline automatically deploys changes on merging to the production branch.

---

## 2. Scope & Features

### 2.1. Functional Requirements

1. **OGC API – Features Compliance**
   - Endpoints to support basic OGC API – Features functionality:
     - `GET /collections`: List collections (each collection corresponds to a protocol version, e.g., `v0.1`).
     - `GET /collections/{collectionId}/items`: Retrieve location proofs (EAS attestations) for a specific protocol version.
     - Additional endpoints as needed to meet compliance.

2. **Attestation as Location Proof**
   - **Core Concept:**
     - Each EAS attestation serves as a location proof.
     - Our API will store the complete attestation data—including geospatial attributes—in a PostGIS-enabled PostgreSQL database.
   - **Data Storage & Status Tracking:**
     - Each record will include:
       - **Geospatial Data:** Stored using PostGIS geometry types.
       - **Metadata:** Timestamp, user identity (from Web3 sign-in), and protocol version.
       - **On-Chain Data:** Fields such as block number, transaction hash, and other relevant identifiers.
       - **Status Field:** A dynamic field indicating the current state of the attestation (e.g., onchain (pending), onchain (validated), IPFS, off-chain). This ensures that users can immediately see new attestations and their verification state.
     - The API will rapidly reflect new attestations as they are detected by monitoring EAS events.

3. **Authentication & Authorization**
   - **Public Access:**
     - Endpoints remain accessible without authentication. However, some entries are private and require authentication. Generally, attestations registered onchain and on IPFS are public, offchain are private.
   - **Private Access & Role-Based Control:**
     - Sensitive operations (submitting or accessing private location proofs) require secure authentication.
     - Users sign in using Web3 (e.g., “Sign in with Ethereum”), with support for role-based permissions to differentiate access levels.

4. **Spatial Queries**
   - Provide advanced spatial querying capabilities:
     - Buffer queries.
     - Point-in-polygon queries.
     - Additional spatial filters as needed for OGC API – Features compliance.

5. **CI/CD & Deployment**
   - **CI/CD Pipeline:**
     - Use GitHub Actions (or equivalent) to run automated tests with pytest, enforce type-checking with mypy, and deploy automatically upon merging to the production branch.
   - **Environments:**
     - Separate development, staging, and production environments.
     - Optionally, ephemeral preview environments for pull requests (depending on cloud provider capabilities).

6. **Containerization & Cloud Deployment**
   - **Containerization:**
     - Package the application using Docker.
   - **Cloud Infrastructure:**
     - Deploy using a cloud provider that supports managed PostGIS instances (e.g., AWS RDS, DigitalOcean Managed Databases) and container orchestration (e.g., AWS ECS/Fargate, Azure Container Instances).


7. GraphQL Proxy Service
- **Purpose:**
  - Provide a GraphQL endpoint that acts as a proxy to our underlying REST API and business logic, enabling flexible queries and mutations.
- **Implementation:**
  - Use a Python GraphQL framework (e.g., Ariadne or Graphene) to define the GraphQL schema, resolvers, and mutations corresponding to our core API functionality.
  - The resolvers will internally invoke the same service layer as the REST endpoints, ensuring consistency and reusability.
- **Benefits:**
  - Clients can request precisely the data they need.
  - It offers an alternative interface for developers familiar with GraphQL without duplicating business logic.
- **Integration:**
  - This service will be fully integrated with the CI/CD pipeline and tested alongside the REST API endpoints.


### 2.2. Non-Functional Requirements

- **Performance:**
  - Ensure reasonably low latency in propagating attestations to the API, so new attestations are visible almost immediately with accurate status.

- **Scalability:**
  - Designed for low-to-moderate loads initially, with a flexible architecture that can scale following industry-standard practices.

- **Security:**
  - Secure API endpoints with robust Web3 authentication and role-based access.
  - Manage secrets and configurations securely using environment variables or a dedicated secrets management service.

- **Code Quality & Testing:**
  - Implement comprehensive unit and integration tests using pytest.
  - Enforce static type-checking with mypy.
  - Use pre-commit hooks (Black, isort, Flake8) to maintain high code quality.

- **Maintainability:**
  - Maintain a clean project structure with thorough documentation to facilitate future development and enhancements.

---

## 3. User Stories & Use Cases

### 3.1. User Stories

- **As a Developer:**
  - I want a CI/CD pipeline that automatically tests, type-checks, and deploys my changes so that I can focus on development without manual overhead.
  - I need clear, maintainable, well-documented code with robust testing and quality standards.

- **As a Public User:**
  - I can query location proofs (EAS attestations) via standardized OGC API endpoints without requiring authentication.

- **As a Registered User (via Web3):**
  - I can sign in using my Ethereum wallet.
  - I can submit a location proof, where the EAS attestation is stored along with geospatial and on-chain metadata, and immediately see it appear in the API with its status (e.g., pending, validated).
  - I can access my private location proofs securely with role-based permissions.

- **As an Admin:**
  - I can manage user roles and oversee the performance and integrity of the API, ensuring that new attestations are accurately tracked and reflected in the system.

### 3.2. Use Cases

1. **Querying Public Location Proofs:**
   - A user sends a GET request to `/collections/v0.1/items` and retrieves public EAS attestations serving as location proofs that meet specified spatial criteria.

2. **Submitting and Tracking a Location Proof:**
   - An authenticated user signs in via Web3.
   - The user submits a location proof (which is an EAS attestation) containing geospatial data.
   - The API detects the new attestation, stores it in the PostGIS database along with on-chain data (e.g., block number, transaction hash) and sets an initial status (e.g., onchain (pending)).
   - As the attestation is validated or processed further, the status is updated (e.g., to onchain (validated) or IPFS).

3. **Securely Accessing Private Data:**
   - A registered user requests access to their private location proofs.
   - The API verifies authentication and role-based permissions before returning the data.


4. **Use Case: Querying via GraphQL**
    - A client sends a GraphQL query to the proxy endpoint requesting location proof data.
    - **Flow:**
    - The GraphQL layer receives the query.
    - Resolvers map the GraphQL query to the underlying REST service or directly to the business logic.
    - The response is returned in GraphQL format, offering clients flexible data selection.
    - **Outcome:**
    - Users can interact with the API using either REST or GraphQL based on their preference.

---

## 4. Constraints & Assumptions

- **Constraints:**
  - The API must meet basic OGC API – Features compliance with minimal endpoints initially.
  - The full attestation data, including on-chain metadata and status, will be stored locally for fast querying and indexing.

- **Assumptions:**
  - The initial load is low to medium; advanced scalability measures can be introduced later if needed.
  - Users will interact with the API via standard HTTP methods.
  - The chosen cloud provider will support both a managed PostGIS instance and containerized deployments.

---

## 5. Risks & Mitigations

- **Integration Risks:**
  - **Risk:** Challenges integrating with EAS or discrepancies between on-chain data and local storage.
  - **Mitigation:** Start with a mock integration during early development and validate with EAS test environments.

- **Security Risks:**
  - **Risk:** Vulnerabilities in the Web3 authentication flow.
  - **Mitigation:** Utilize well-established libraries and perform regular security audits.

- **Deployment Risks:**
  - **Risk:** CI/CD pipeline failures that could disrupt production.
  - **Mitigation:** Implement robust testing (pytest), enforce mypy type-checking, and design a reliable rollback strategy.

---

## 6. Success Metrics

- **Rapid Availability:**
  - New attestations appear in the API almost immediately upon detection, with accurate status updates reflecting their processing stage.

- **Compliance:**
  - The API passes OGC API – Features compliance tests.

- **Performance:**
  - The API responds to spatial queries with acceptable latency.

- **Security:**
  - Regular security audits reveal no critical vulnerabilities.

- **Developer Experience:**
  - CI/CD pipeline executes reliably, with automated tests and deployments triggered on production merges.

- **User Adoption:**
  - Users can seamlessly authenticate via Web3, submit location proofs, and query both public and private attestations as expected.

---

This revised PRD now includes requirements for rapid detection and propagation of attestations, complete with a status mechanism and on-chain metadata tracking. Let me know if any further adjustments are needed before moving on to the next steps (Tech Stack, Project Structure, Schema Design, User Flow, and Implementation Plan).
