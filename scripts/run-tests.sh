#!/bin/bash
set -e

# Check if the container is running
if ! docker ps | grep -q astral-api; then
  echo "Error: astral-api container is not running"
  exit 1
fi

# Run tests
echo "Running tests..."
docker exec -it astral-api pytest "$@"

echo "Tests completed!"
