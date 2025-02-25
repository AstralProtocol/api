# Implementation Plan

This document describes the phased implementation of the Astral API. Each numbered section corresponds to a logical step in development (i.e., a milestone). Tasks within each section are listed as checkboxes with bulleted requirements that detail what needs to be achieved.

## Task Completion Checklist

⚠️ IMPORTANT: Every task MUST be committed after completion! ⚠️

For each task, follow these steps in order:
1. Implement the required changes
2. Run tests if applicable
3. Fix any linting/type checking issues
4. Update this implementation plan to mark the task as complete
5. Create a commit with a descriptive message following conventional commits format:
   - feat: New features
   - fix: Bug fixes
   - refactor: Code changes that neither fix bugs nor add features
   - test: Adding or modifying tests
   - docs: Documentation only changes
   - chore: Changes to the build process, tools, etc.

DO NOT move on to the next task until you have committed the current one!

---

## 1. Initial Project Setup & Repository Bootstrap

- [x] **Task 1.1: Repository Initialization**
  - • Create a new Git repository with a clear commit history.
  - • Set up the basic project structure (based on .cursor/rules/project-structure.md) (e.g., app/, tests/, docs/, config/, etc.) following the established directory design.
  - • Add standard configuration files (.gitignore, README.md, etc.).
- [x] **Task 1.2: Environment & Dependency Setup**
  - • Configure the Python environment (.cursor/rules/python-environment.md) using Python 3.11.
  - • Define dependencies in `pyproject.toml` (include FastAPI, Uvicorn, SQLAlchemy, Alembic, Pydantic, pytest, etc.).
  - • Set up pre-commit hooks (Black, isort, Flake8, mypy).
- [x] **Task 1.3: CI/CD Pipeline Bootstrap**
  - • Create a basic GitHub Actions workflow that runs tests and linters on each push.
  - • Document CI/CD configuration in the repository.

---

## 2. Database Schema & Migrations

- [x] **Task 2.1: Define Database Models**
  - • Create Pydantic and SQLAlchemy models for Users, Addresses, Location Proofs (Attestations), and Chains based on the Schema Design Document.
  - • Ensure relationships (foreign keys) are defined correctly.
- [x] **Task 2.2: Set Up Database Migrations**
  - • Initialize Alembic for database migrations.
  - • Create an initial migration script to set up the database schema.
- [x] **Task 2.3: Integration Testing for Database**
  - • Write integration tests for database operations (CRUD, relationships, etc.).
  - • Ensure tests run successfully in the CI environment.

---

## 3. API Development (REST Endpoints)

- [x] **Task 3.1: Define API Routing Structure** (commit: 192d181)
  - • Create a modular FastAPI routing structure under `app/components/` for endpoints (e.g., location proofs, authentication, health-check).
  - • Document endpoint specifications in the code and README.
- [ ] **Task 3.2: Implement Core Endpoints**
- [x] **Task 3.2.1: Core OGC API Features Implementation**
  - • Implement landing page (/) with links and metadata
  - • Create API definition (/api) endpoint
  - • Add conformance declaration (/conformance)
  - • Develop collections listing (/collections)
  - • Implement single collection (/collections/{collectionId})
  - • Create features endpoint (/collections/{collectionId}/items)
  - • Add single feature by ID (/collections/{collectionId}/items/{featureId})
  - • Ensure proper GeoJSON responses for all endpoints
- [x] **Task 3.2.2: Advanced Query Capabilities**
  - • Implement spatial filters (bbox, intersects, within)
  - • Add temporal filters (instant and range queries)
  - • Create property filters (equals, greater/less than, LIKE)
  - • Implement complex geometry queries (polygon, buffer)
- [x] **Task 3.2.3: Metadata and Links Structure**
  - • Implement proper link relations between resources
  - • Add complete metadata for collections
  - • Support different response formats
  - • Implement proper error responses and status codes
  - • Write comprehensive tests for all implemented functionality
- [x] **Task 3.3: Error Handling & Validation**
  - • Implement error handling and input validation using Pydantic.
  - • Write unit tests for endpoint functionality.

---

## 4. Integration with EAS & Scheduler

- [x] **Task 4.1: EAS Integration**
  - • Implement service functions in `app/services/eas_integration.py` to interact with the EAS GraphQL endpoint.
    - Create a robust `EASIntegrationService` class with proper async/await handling
    - Implement methods to fetch unsynced attestations using GraphQL queries
    - Design a mechanism to track sync state (last synced block, timestamp, attestation ID)
    - Develop functions to parse attestation data and extract geospatial information
    - Ensure proper error handling for network issues, invalid responses, and schema mismatches
    - Implement proper SQLAlchemy session management with async patterns
    - Add comprehensive logging for debugging and monitoring
  - • Design these functions to parse and store attestations in the database.
    - Create a `SyncState` model to track synchronization state
    - Ensure proper relationship between attestations and chains
    - Implement efficient database operations with proper transaction handling
    - Add validation to ensure data integrity
  - • Write thorough unit tests with proper mocking of async dependencies
    - Test each component in isolation with appropriate mocks
    - Ensure proper handling of edge cases (empty responses, network errors, etc.)
    - Verify correct parsing of attestation data
    - Test database operations with in-memory SQLite for speed
- [x] **Task 4.2: Scheduler for Regular EAS Polling**
  - • Create a scheduler in `app/services/scheduler.py` to periodically poll the EAS GraphQL endpoint.
  - • Allow configuration for polling frequency (e.g., every minute by default, and more frequently if a user is online).
- [x] **Task 4.3: Integration Testing**
  - • Write integration tests for the EAS polling mechanism.
  - • Ensure that new attestations are detected and stored correctly with appropriate status updates.

---

## 5. Dockerization & Local Development Environment

- [ ] **Task 5.1: Docker Configuration for API**
  - • Create a `Dockerfile` for the FastAPI application with proper multi-stage build:
    - Use Python 3.11 as the base image
    - Install system dependencies (including PostGIS requirements)
    - Set up a non-root user for security
    - Install Python dependencies from pyproject.toml
    - Configure proper entry points and health checks
  - • Optimize the Docker image for size and security:
    - Use multi-stage builds to minimize image size
    - Include only necessary files and dependencies
    - Set appropriate permissions and user context
    - Configure proper environment variables

- [ ] **Task 5.2: Docker Compose Setup**
  - • Create a `docker-compose.yml` file that includes:
    - PostgreSQL with PostGIS extension
    - FastAPI application service
    - Volume configurations for data persistence
    - Network configuration for service communication
    - Environment variable configuration
  - • Configure environment-specific settings:
    - Development environment with debugging enabled
    - Test environment for running automated tests
    - Production-like environment for local testing
  - • Set up proper initialization scripts:
    - Database initialization and schema creation
    - Initial data seeding for testing
    - Alembic migration integration

- [ ] **Task 5.3: Development Workflow Integration**
  - • Create helper scripts for common development tasks:
    - Database reset and migration scripts
    - Test execution within containers
    - Log viewing and debugging utilities
  - • Document the Docker-based development workflow:
    - Setup instructions in README.md
    - Common commands and troubleshooting
    - Best practices for local development
  - • Implement hot-reload for local development:
    - Configure volume mounts for code changes
    - Set up Uvicorn with reload capabilities
    - Ensure proper handling of static files

- [ ] **Task 5.4: Testing & Validation**
  - • Test the complete Docker setup:
    - Verify all services start correctly
    - Ensure database migrations run properly
    - Validate API functionality end-to-end
    - Test scheduler and EAS integration
  - • Create integration tests specifically for the containerized environment:
    - Test database connectivity and migrations
    - Verify proper service communication
    - Ensure environment variables are properly used
  - • Document any environment-specific considerations:
    - Performance implications
    - Resource requirements
    - Network and security configurations

---

## 6. GraphQL Proxy Implementation

- [ ] **Task 6.1: Define GraphQL Schema & Resolvers**
  - • Use Ariadne or Graphene to create a GraphQL schema that mirrors the functionality of the REST API.
  - • Implement resolvers that proxy requests to the underlying REST endpoints or directly call service layer functions.
- [ ] **Task 6.2: Integration & Testing**
  - • Integrate the GraphQL endpoint into the FastAPI application.
  - • Write tests to verify GraphQL queries and mutations.
- [ ] **Task 6.3: Documentation**
  - • Update API documentation to include GraphQL usage instructions.

---

## 7. Authentication & Authorization

- [ ] **Task 7.1: Implement Web3 Sign-In**
  - • Integrate a Web3 sign-in mechanism (e.g., "Sign in with Ethereum") into the authentication flow.
  - • Ensure that authenticated users can securely access private endpoints.
- [ ] **Task 7.2: Role-Based Access Control**
  - • Implement role-based access controls to manage public vs. private proofs.
  - • Write tests to ensure proper enforcement of permissions.
- [ ] **Task 7.3: Documentation & API Security**
  - • Document the authentication and authorization flow in the README.
  - • Review security configurations and update the Implementation Plan accordingly.

---

## 8. Final Integration, Testing & Deployment

- [ ] **Task 8.1: End-to-End Testing**
  - • Write comprehensive end-to-end tests covering REST, GraphQL, and authentication flows.
  - • Ensure the system passes OGC API compliance tests.
- [ ] **Task 8.2: CI/CD Finalization**
  - • Refine the CI/CD pipeline to deploy to AWS (using ECS/Fargate, RDS, etc.) on merge to the production branch.
  - • Test the deployment process in a staging environment.
- [ ] **Task 8.3: Documentation & Rollback Plan**
  - • Finalize and update all documentation (README, API docs via MkDocs, etc.).
  - • Create a rollback plan in case of deployment issues.

---

## 9. Ongoing Maintenance & Future Enhancements

- [ ] **Task 9.1: Monitor & Log**
  - • Set up logging (integrate with AWS CloudWatch) to monitor API performance and errors.
- [ ] **Task 9.2: Scheduled Reviews**
  - • Plan periodic reviews of the codebase and database schema for potential improvements.
- [ ] **Task 9.3: Extend Features**
  - • Based on user feedback, plan future enhancements (e.g., geospatial analytics, new authentication methods, etc.).
