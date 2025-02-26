# Astral API

A decentralized geospatial data API that integrates with Ethereum Attestation Service (EAS) to provide verifiable location proofs.

## Features

- EAS attestations as location proofs
- OGC API Features compliance
- PostGIS-powered spatial queries
- Web3 authentication
- GraphQL proxy layer

## API Endpoints

### Health Check
- `GET /health`
  - Returns API health status
  - Response: `{"status": "healthy"}`

### Location Proofs (OGC API - Features)
- `GET /collections`
  - Lists available collections
  - Response: List of collections with metadata

- `GET /collections/{collection_id}/items`
  - Retrieves features from a specific collection
  - Query Parameters:
    - `bbox` (optional): Bounding box filter (minLon,minLat,maxLon,maxLat)
    - `limit` (optional): Maximum number of features to return (1-1000)
    - `offset` (optional): Starting offset for pagination
  - Response: GeoJSON FeatureCollection

### Authentication
- `POST /auth/nonce`
  - Request body: `{"address": "0x..."}`
  - Returns a nonce for Web3 sign-in

- `POST /auth/verify`
  - Request body:
    ```json
    {
      "address": "0x...",
      "signature": "0x...",
      "nonce": "..."
    }
    ```
  - Returns a JWT token upon successful verification

## Requirements

- Python 3.11+
- PostgreSQL with PostGIS extension
- Poetry for dependency management

## Quick Start

1. Clone the repository:
   ```bash
   git clone git@github.com:AstralProtocol/api.git
   cd astral-api
   ```

2. Install Poetry (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. Install dependencies:
   ```bash
   poetry install
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env.development
   # Edit .env.development with your configuration
   ```

5. Start the development server:
   ```bash
   poetry run uvicorn app.main:app --reload
   ```

The API will be available at `http://localhost:8000`. OpenAPI documentation can be accessed at `http://localhost:8000/docs`.

## Development

### Project Structure

```
project-root/
├── app/                           # Main application package
│   ├── components/                # API routes by resource
│   ├── models/                    # SQLAlchemy models
│   ├── schemas/                   # Pydantic models
│   ├── services/                  # Business logic
│   └── utils/                     # Utility functions
├── tests/                         # Test suite
├── alembic/                       # Database migrations
└── config/                        # Configuration
```

### Running Tests

```bash
poetry run pytest
```

### Code Quality

We use pre-commit hooks to maintain code quality:

```bash
poetry run pre-commit install
poetry run pre-commit run --all-files
```

### Continuous Integration

We use GitHub Actions for continuous integration. The CI pipeline:
- Runs on every push and pull request to the main branch
- Sets up Python 3.11 and Poetry
- Installs project dependencies
- Runs pre-commit hooks (black, isort, flake8, mypy)
- Executes test suite with pytest
- Reports test coverage to Codecov

Status badges:
[![CI](https://github.com/AstralProtocol/api/actions/workflows/ci.yml/badge.svg)](https://github.com/AstralProtocol/api/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/AstralProtocol/api/branch/main/graph/badge.svg)](https://codecov.io/gh/AstralProtocol/api)

## Documentation

- [Project Requirements Document](docs/prd.md)
- [Technical Stack](docs/tech-stack.md)
- [Schema Design](docs/schema-design.md)
- [Implementation Plan](docs/implementation-plan.md)

## Adding New Chains

The API supports multiple blockchain networks through the `chain` table in the database. To add new chains or update existing ones, use the `seed_chains.py` script:

### Basic Usage

```bash
# Add default supported chains (if they don't exist)
docker-compose exec api python scripts/seed_chains.py

# Add specific chain IDs
docker-compose exec api python scripts/seed_chains.py 137 56 43114

# Force update all default chains (overwrites existing entries)
docker-compose exec api python scripts/seed_chains.py --all

# Add chains with custom EAS endpoints
docker-compose exec api python scripts/seed_chains.py --eas-file=custom_eas_endpoints.json
```

### Custom EAS Endpoints

To add chains with custom EAS GraphQL endpoints, create a JSON file with the following format:

```json
{
    "1": "https://easscan.org/graphql",
    "137": "https://polygon.easscan.org/graphql",
    "43114": "https://avalanche.easscan.org/graphql"
}
```

Where the keys are chain IDs and the values are the GraphQL endpoints.

### Adding to Production

When adding chains to a production database:

1. Test the changes in a staging environment first
2. Back up the database before making changes
3. Run the script with specific chain IDs to minimize impact:
   ```bash
   docker-compose exec api python scripts/seed_chains.py 137 43114
   ```
4. Verify the changes by querying the database:
   ```bash
   docker-compose exec db psql -U postgres -d astral -c "SELECT chain_id, name, chain FROM chain"
   ```

## License

[License details to be added]
