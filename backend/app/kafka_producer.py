"""
Kafka producer — publishes property update events to 'property-updates' topic.
"""
import json
import os
import logging
from aiokafka import AIOKafkaProducer
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

TOPIC = "property-updates"

_producer: Optional[AIOKafkaProducer] = None


async def init_producer() -> AIOKafkaProducer:
    global _producer
    broker = os.environ.get("KAFKA_BROKER", "kafka:29092")
    _producer = AIOKafkaProducer(
        bootstrap_servers=broker,
        value_serializer=lambda v: json.dumps(v, default=_serializer).encode(),
    )
    await _producer.start()
    logger.info("Kafka producer started, broker=%s", broker)
    return _producer


async def close_producer() -> None:
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None


def get_producer() -> AIOKafkaProducer:
    if _producer is None:
        raise RuntimeError("Kafka producer is not initialised")
    return _producer


def _serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


async def publish_property_update(row: dict) -> None:
    producer = get_producer()
    payload = {
        "id": row["id"],
        "price": float(row["price"]),
        "bedrooms": row["bedrooms"],
        "bathrooms": row["bathrooms"],
        "region_origin": row["region_origin"],
        "version": row["version"],
        "updated_at": row["updated_at"].isoformat() if hasattr(row["updated_at"], "isoformat") else row["updated_at"],
    }
    await producer.send_and_wait(TOPIC, value=payload)
    logger.info("Published event to %s: property_id=%s", TOPIC, payload["id"])
