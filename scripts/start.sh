#!/bin/bash
set -e

# Function to check if PostgreSQL is ready
function postgres_ready() {
  python << END
import sys
import asyncpg
import os
import asyncio

async def check_db():
    try:
        # Extract connection details from DATABASE_URL
        db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/astral")
        # Convert SQLAlchemy URL to asyncpg format
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

        conn = await asyncpg.connect(db_url)
        await conn.close()
        return True
    except Exception as e:
        print(f"Database connection error: {e}")
        return False

if asyncio.run(check_db()):
    sys.exit(0)
else:
    sys.exit(1)
END
}

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until postgres_ready; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done
echo "PostgreSQL is up - continuing..."

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the FastAPI application
echo "Starting FastAPI application..."
exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --reload
