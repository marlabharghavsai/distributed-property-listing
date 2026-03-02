"""
Kafka consumer — listens for property updates from the other region and replicates them locally.
Tracks the latest consumed message timestamp for replication-lag reporting.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from aiokafka import AIOKafkaConsumer

from . import db as database

logger = logging.getLogger(__name__)

TOPIC = "property-updates"
GROUP_ID_PREFIX = "property-replication"

# Shared state for replication lag
_last_consumed_ts: Optional[datetime] = None


def get_last_consumed_ts() -> Optional[datetime]:
    return _last_consumed_ts


async def start_consumer(region: str) -> None:
    """
    Start the Kafka consumer loop. Runs forever as a background task.
    Only processes messages NOT originating from this region.
    """
    broker = os.environ.get("KAFKA_BROKER", "kafka:29092")
    group_id = f"{GROUP_ID_PREFIX}-{region}"

    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=broker,
        group_id=group_id,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    # Retry loop in case Kafka is not yet ready
    for attempt in range(10):
        try:
            await consumer.start()
            logger.info("Kafka consumer started (region=%s, group=%s)", region, group_id)
            break
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning("Consumer start attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
            await asyncio.sleep(wait)
    else:
        logger.error("Failed to start Kafka consumer after 10 attempts")
        return

    global _last_consumed_ts
    try:
        async for msg in consumer:
            try:
                record = msg.value
                msg_region = record.get("region_origin", "")

                # Skip messages originating from our own region
                if msg_region == region:
                    continue

                logger.info(
                    "Replicating property %s from region=%s to region=%s",
                    record.get("id"),
                    msg_region,
                    region,
                )

                # Parse updated_at
                updated_at_raw = record.get("updated_at")
                if isinstance(updated_at_raw, str):
                    try:
                        record["updated_at"] = datetime.fromisoformat(updated_at_raw)
                    except ValueError:
                        record["updated_at"] = datetime.now(tz=timezone.utc)
                elif updated_at_raw is None:
                    record["updated_at"] = datetime.now(tz=timezone.utc)

                await database.upsert_property_from_replication(record)
                _last_consumed_ts = datetime.now(tz=timezone.utc)

            except Exception as inner_exc:
                logger.error("Error processing Kafka message: %s", inner_exc, exc_info=True)
    finally:
        await consumer.stop()
        logger.info("Kafka consumer stopped (region=%s)", region)
