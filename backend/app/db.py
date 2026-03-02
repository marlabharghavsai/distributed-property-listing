"""
Database connection pool and query helpers.
"""
import asyncpg
import os
from typing import Optional

_pool: Optional[asyncpg.Pool] = None


async def init_pool() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=os.environ["DATABASE_URL"],
        min_size=2,
        max_size=10,
    )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    return _pool


# ── Property queries ─────────────────────────────────────────────────────────

async def fetch_property(property_id: int) -> Optional[asyncpg.Record]:
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT id, price, bedrooms, bathrooms, region_origin, version, updated_at "
        "FROM properties WHERE id = $1",
        property_id,
    )
    return row


async def update_property_optimistic(
    property_id: int,
    price: float,
    expected_version: int,
) -> Optional[asyncpg.Record]:
    """
    Update price if version matches (optimistic locking).
    Returns the updated row or None if version conflict.
    """
    pool = get_pool()
    row = await pool.fetchrow(
        """
        UPDATE properties
           SET price      = $1,
               version    = version + 1,
               updated_at = NOW()
         WHERE id = $2
           AND version = $3
        RETURNING id, price, bedrooms, bathrooms, region_origin, version, updated_at
        """,
        price,
        property_id,
        expected_version,
    )
    return row


async def upsert_property_from_replication(record: dict) -> None:
    """
    Apply a replicated update from another region.
    Uses version check to avoid applying stale data.
    """
    pool = get_pool()
    await pool.execute(
        """
        UPDATE properties
           SET price      = $1,
               version    = $2,
               updated_at = $3
         WHERE id = $4
           AND version < $2
        """,
        record["price"],
        record["version"],
        record["updated_at"],
        record["id"],
    )


# ── Idempotency queries ───────────────────────────────────────────────────────

async def check_request_id(request_id: str) -> bool:
    """Return True if already processed."""
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT 1 FROM processed_requests WHERE request_id = $1",
        request_id,
    )
    return row is not None


async def save_request_id(request_id: str, response_body: str) -> None:
    pool = get_pool()
    await pool.execute(
        """
        INSERT INTO processed_requests (request_id, response_body)
        VALUES ($1, $2)
        ON CONFLICT (request_id) DO NOTHING
        """,
        request_id,
        response_body,
    )


async def fetch_request_response(request_id: str) -> Optional[str]:
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT response_body FROM processed_requests WHERE request_id = $1",
        request_id,
    )
    return row["response_body"] if row else None
