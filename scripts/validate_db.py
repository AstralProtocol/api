#!/usr/bin/env python
"""Database Schema Validation Script.

This script validates that the database schema is properly set up by checking
that all expected tables exist and can be queried.
"""

import asyncio
import sys
from typing import List, Set

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# List of expected tables
EXPECTED_TABLES = [
    "user",
    "address",
    "chain",
    "location_proof",
    "alembic_version",
]


async def get_database_url() -> str:
    """Get the database URL from environment variables or use default."""
    import os

    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "astral")

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


async def get_tables(engine: AsyncEngine) -> Set[str]:
    """Get all tables in the database."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                """
            )
        )
        tables = {row[0] for row in result.fetchall()}
        return tables


async def check_table_query(engine: AsyncEngine, table: str) -> bool:
    """Check if a table can be queried."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            return True
    except Exception as e:
        print(f"Error querying table {table}: {e}")
        return False


async def validate_database(engine: AsyncEngine) -> List[str]:
    """Validate the database schema."""
    issues = []

    # Check if all expected tables exist
    tables = await get_tables(engine)
    for table in EXPECTED_TABLES:
        if table not in tables:
            issues.append(f"Missing table: {table}")
        else:
            # Check if the table can be queried
            if not await check_table_query(engine, table):
                issues.append(f"Table {table} exists but cannot be queried")

    return issues


async def main() -> int:
    """Main function to validate the database schema."""
    print("Validating database schema...")

    try:
        db_url = await get_database_url()
        engine = create_async_engine(db_url)

        issues = await validate_database(engine)

        if not issues:
            print("✅ Database schema validation successful!")
            print("\nAll expected tables exist and can be queried:")
            for table in EXPECTED_TABLES:
                print(f"  - {table}")
            return 0
        else:
            print("❌ Database schema validation failed!")
            print("\nIssues found:")
            for issue in issues:
                print(f"  - {issue}")
            return 1

    except Exception as e:
        print(f"Error validating database schema: {e}")
        return 1

    finally:
        if "engine" in locals():
            await engine.dispose()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
