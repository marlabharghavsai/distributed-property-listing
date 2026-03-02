"""
FastAPI route handlers.
NGINX strips the /us/ and /eu/ prefix before proxying, so the backend
receives paths like /health, /properties/{id}, /replication-lag directly.
Region is determined by the REGION environment variable set per container.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import db as database
from .kafka_producer import publish_property_update

logger = logging.getLogger(__name__)

router = APIRouter()

# Region is set via docker-compose environment variable — us or eu
REGION = os.environ.get("REGION", "us")


# ── Pydantic models ───────────────────────────────────────────────────────────

class PropertyUpdateRequest(BaseModel):
    price: float = Field(..., gt=0)
    version: int = Field(..., ge=1)


class PropertyUpdateResponse(BaseModel):
    id: int
    price: float
    version: int
    updated_at: str


class ReplicationLagResponse(BaseModel):
    lag_seconds: float


# ── Health endpoint ────────────────────────────────────────────────────────────
# NGINX strips /us/ prefix → backend receives GET /health

@router.get("/health")
async def health():
    return {"status": "ok", "region": REGION}


# ── PUT /properties/{property_id} ─────────────────────────────────────────────
# NGINX strips /us/ prefix → backend receives PUT /properties/{id}

@router.put("/properties/{property_id}")
async def update_property(
    property_id: int,
    body: PropertyUpdateRequest,
    x_request_id: str = Header(default=None, alias="X-Request-ID"),
):
    # ── Idempotency check ──────────────────────────────────────────────────────
    if x_request_id:
        existing = await database.fetch_request_response(x_request_id)
        if existing is not None:
            return JSONResponse(
                status_code=422,
                content={
                    "error": "Duplicate request",
                    "detail": f"Request ID '{x_request_id}' has already been processed.",
                    "previous_response": json.loads(existing),
                },
            )

    # ── Optimistic locking update ──────────────────────────────────────────────
    row = await database.update_property_optimistic(
        property_id=property_id,
        price=body.price,
        expected_version=body.version,
    )

    if row is None:
        existing_row = await database.fetch_property(property_id)
        if existing_row is None:
            raise HTTPException(status_code=404, detail=f"Property {property_id} not found")
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Version conflict",
                "message": (
                    f"Property {property_id} was updated concurrently. "
                    f"Current version is {existing_row['version']}, "
                    f"but you sent version {body.version}. "
                    "Re-fetch the resource and retry."
                ),
                "current_version": existing_row["version"],
            },
        )

    updated: dict[str, Any] = dict(row)

    # ── Publish Kafka event ────────────────────────────────────────────────────
    try:
        await publish_property_update(updated)
    except Exception as exc:
        logger.error("Failed to publish Kafka event for property %s: %s", property_id, exc)

    response_payload = {
        "id": updated["id"],
        "price": float(updated["price"]),
        "version": updated["version"],
        "updated_at": updated["updated_at"].isoformat()
        if hasattr(updated["updated_at"], "isoformat")
        else str(updated["updated_at"]),
    }

    if x_request_id:
        try:
            await database.save_request_id(x_request_id, json.dumps(response_payload))
        except Exception as exc:
            logger.warning("Could not save request_id %s: %s", x_request_id, exc)

    return response_payload


# ── GET /replication-lag ──────────────────────────────────────────────────────
# NGINX strips /us/ → backend receives GET /replication-lag

@router.get("/replication-lag")
async def replication_lag():
    from .kafka_consumer import get_last_consumed_ts

    last_ts = get_last_consumed_ts()
    if last_ts is None:
        return ReplicationLagResponse(lag_seconds=0.0)

    now = datetime.now(tz=timezone.utc)
    lag = (now - last_ts).total_seconds()
    return ReplicationLagResponse(lag_seconds=round(lag, 3))
