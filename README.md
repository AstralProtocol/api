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

## License

[License details to be added]
