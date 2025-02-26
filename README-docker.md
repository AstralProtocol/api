# Docker Setup for Astral API

This document provides instructions for setting up and running the Astral API using Docker.

## Prerequisites

- Docker and Docker Compose installed on your system
- Git (to clone the repository)

## Quick Start

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd api-cursor
   ```

2. Build and start the containers:
   ```bash
   docker-compose up -d
   ```

3. The API will be available at http://localhost:8000

## Configuration

The application is configured using environment variables. You can:

1. Modify the `.env` file in the project root
2. Pass environment variables directly to the `docker-compose up` command
3. Create a `.env.local` file (which is git-ignored) for local overrides

Key environment variables:

- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: Secret key for cryptographic operations
- `DEBUG`: Enable/disable debug mode
- `EAS_SCHEMA_UID`: The schema UID for EAS integration
- `INFURA_API_KEY`: API key for Infura (for blockchain interactions)

## Development Workflow

### Running the API

```bash
# Start the containers in the background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the containers
docker-compose down
```

### Database Management

```bash
# Reset the database and run migrations
./scripts/reset-db.sh

# Connect to the database
docker exec -it astral-db psql -U postgres -d astral
```

### Running Tests

```bash
# Run all tests
./scripts/run-tests.sh

# Run specific tests
./scripts/run-tests.sh -k test_name
```

## Container Structure

- **db**: PostgreSQL with PostGIS extensions
  - Ports: 5432:5432
  - Data: Stored in a Docker volume for persistence

- **api**: FastAPI application
  - Ports: 8000:8000
  - Volumes: App code is mounted for hot-reloading during development

## Troubleshooting

### Database Connection Issues

If the API can't connect to the database:

1. Check if the database container is running:
   ```bash
   docker ps | grep astral-db
   ```

2. Verify the database is healthy:
   ```bash
   docker exec -it astral-db pg_isready -U postgres
   ```

3. Check the database logs:
   ```bash
   docker-compose logs db
   ```

### API Issues

1. Check the API logs:
   ```bash
   docker-compose logs api
   ```

2. Verify the API container is running:
   ```bash
   docker ps | grep astral-api
   ```

3. Check the API health endpoint:
   ```bash
   curl http://localhost:8000/health
   ```

## Production Deployment

For production deployment:

1. Set `DEBUG=False` in the environment
2. Use a strong, unique `SECRET_KEY`
3. Configure proper CORS settings
4. Consider using a reverse proxy (like Nginx) in front of the API
5. Set up proper logging and monitoring
