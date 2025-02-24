# Astral API

A decentralized geospatial data API that integrates with Ethereum Attestation Service (EAS) to provide verifiable location proofs.

## Features

- EAS attestations as location proofs
- OGC API Features compliance
- PostGIS-powered spatial queries
- Web3 authentication
- GraphQL proxy layer

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

## Documentation

- [Project Requirements Document](docs/prd.md)
- [Technical Stack](docs/tech-stack.md)
- [Schema Design](docs/schema-design.md)
- [Implementation Plan](docs/implementation-plan.md)

## License

[License details to be added] 