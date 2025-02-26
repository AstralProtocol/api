#!/bin/bash
# Start script for the Astral API development environment

# Exit on error
set -e

# Print commands
set -x

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Docker is not running. Please start Docker and try again."
  exit 1
fi

# Build and start the containers
echo "Starting development environment..."
docker-compose up -d

# Wait for the database to be ready
echo "Waiting for database to be ready..."
docker-compose exec -T db pg_isready -U postgres -d astral -t 30

# Run migrations if needed
echo "Running database migrations..."
docker-compose exec -T api alembic upgrade head

# Seed the database with chains
echo "Seeding chains..."
docker-compose exec -T api python scripts/seed_chains.py

# Seed the database with location proofs (optional)
if [ "$1" == "--with-proofs" ]; then
  echo "Seeding location proofs..."
  docker-compose exec -T api python scripts/seed_location_proofs.py --limit 10
fi

echo "Development environment is ready!"
echo "API is available at http://localhost:8000"
echo "API documentation is available at http://localhost:8000/docs"

# Show logs
if [ "$1" == "--logs" ] || [ "$2" == "--logs" ]; then
  echo "Showing logs..."
  docker-compose logs -f api
fi
