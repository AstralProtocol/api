#!/bin/bash
set -e

# Check if the container is running
if ! docker ps | grep -q astral-db; then
  echo "Error: astral-db container is not running"
  exit 1
fi

# Drop and recreate the database
echo "Dropping and recreating the database..."
docker exec -it astral-db psql -U postgres -c "DROP DATABASE IF EXISTS astral;"
docker exec -it astral-db psql -U postgres -c "CREATE DATABASE astral;"

# Enable PostGIS extension
echo "Enabling PostGIS extension..."
docker exec -it astral-db psql -U postgres -d astral -c "CREATE EXTENSION IF NOT EXISTS postgis;"
docker exec -it astral-db psql -U postgres -d astral -c "CREATE EXTENSION IF NOT EXISTS postgis_topology;"

# Run migrations
echo "Running migrations..."
docker exec -it astral-api alembic upgrade head

echo "Database reset and migrations completed successfully!"
