#!/bin/bash
# Start script for the Astral API container

# Exit on error
set -e

# Print commands
set -x

# Wait for the database to be ready
echo "Waiting for database to be ready..."
python -c "
import time
import psycopg2

def wait_for_db():
    while True:
        try:
            conn = psycopg2.connect(
                dbname='astral',
                user='postgres',
                password='postgres',
                host='db',
                port='5432'
            )
            conn.close()
            return
        except psycopg2.OperationalError:
            print('Database not ready yet. Waiting...')
            time.sleep(1)

wait_for_db()
print('Database is ready!')
"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Seed the database with chains
echo "Seeding chains..."
python scripts/seed_chains.py

# Seed the database with location proofs
echo "Seeding location proofs..."
python scripts/seed_location_proofs.py --limit 10

# Start the API server
echo "Starting API server..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
