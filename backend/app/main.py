"""
FastAPI application entry point.
Manages database pool and Kafka producer/consumer lifecycle.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import init_pool, close_pool
from .kafka_producer import init_producer, close_producer
from .kafka_consumer import start_consumer
from .routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

REGION = os.environ.get("REGION", "us")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    app.state.region = REGION
    logger.info("Starting backend service (region=%s)", REGION)

    await init_pool()
    logger.info("Database pool ready")

    await init_producer()
    logger.info("Kafka producer ready")

    # Start consumer as a background task
    consumer_task = asyncio.create_task(start_consumer(REGION))
    logger.info("Kafka consumer task launched")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass

    await close_producer()
    await close_pool()
    logger.info("Backend service shut down cleanly (region=%s)", REGION)


app = FastAPI(
    title=f"Property Listing Service ({REGION.upper()} Region)",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
