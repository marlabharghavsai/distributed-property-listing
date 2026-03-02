# 🌍 Distributed Property Listing Backend

A production-grade simulation of a **multi-region property listing system** built with FastAPI, PostgreSQL, Apache Kafka, and NGINX. Deployable with a single command.

[![Docker](https://img.shields.io/badge/Docker-compose-blue)](https://docs.docker.com/compose/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green)](https://fastapi.tiangolo.com)
[![Kafka](https://img.shields.io/badge/Kafka-7.0.1-orange)](https://kafka.apache.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14-blue)](https://www.postgresql.org)

---

## 📐 Architecture

```
                        ┌─────────────────────────────────────────┐
                        │          Client (curl / tests)          │
                        └──────────────────┬──────────────────────┘
                                           │ :8080
                        ┌──────────────────▼──────────────────────┐
                        │           NGINX Reverse Proxy           │
                        │   /us/* → backend-us (fallback: eu)     │
                        │   /eu/* → backend-eu (fallback: us)     │
                        └──────┬───────────────────────┬──────────┘
                               │                       │
              ┌────────────────▼──────┐   ┌────────────▼────────────────┐
              │   backend-us (FastAPI) │   │   backend-eu (FastAPI)      │
              │   region = us          │   │   region = eu               │
              │   port 8000            │   │   port 8000                 │
              └────────────┬──────────┘   └──────────┬─────────────────┘
                           │                         │
              ┌────────────▼──────────┐   ┌──────────▼─────────────────┐
              │   db-us (PostgreSQL)  │   │   db-eu (PostgreSQL)        │
              │   1200 US properties  │   │   1200 EU properties        │
              └───────────────────────┘   └────────────────────────────┘
                           │                         │
                           └──────────┬──────────────┘
                                      │
                        ┌─────────────▼───────────────────────────┐
                        │       Apache Kafka (property-updates)   │
                        │   US publishes → EU consumes (& vice v.) │
                        └─────────────────────────────────────────┘
```

### Key Design Decisions

| Concern | Approach |
|---|---|
| **Stateless backends** | All state in PostgreSQL; Kafka consumer tracks lag in-memory |
| **Optimistic locking** | `version` column; `UPDATE … WHERE version = $expected` |
| **Idempotency** | `processed_requests` table keyed by `X-Request-ID` |
| **Async replication** | aiokafka producer/consumer; consumer skips own-region messages |
| **Failover** | NGINX `backup` directive; primary fails → backup answers automatically |
| **Secrets** | All credentials via environment variables; no hard-coded values |

---

## 🚀 Quick Start

### Prerequisites

- Docker Engine ≥ 20.10
- Docker Compose plugin (v2)

### 1 · Clone / enter the project directory

```bash
cd task-14
```

### 2 · Create your `.env` file

```bash
cp .env.example .env
# Edit .env if you want custom passwords (defaults work fine for local dev)
```

### 3 · Start everything

```bash
docker compose up -d
```

All 7 services start and become healthy automatically (≈ 60–90 s on first run while images download).

```bash
# Watch service health states
docker compose ps
```

---

## 🧪 Verification Cheatsheet

### NGINX Routing

```bash
curl -I http://localhost:8080/us/health   # → 200, backend-us responds
curl -I http://localhost:8080/eu/health   # → 200, backend-eu responds
```

### PUT Endpoint (optimistic locking)

```bash
# First update — succeeds, version becomes 2
curl -X PUT http://localhost:8080/us/properties/1 \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: $(uuidgen)" \
  -d '{"price": 500000.00, "version": 1}'

# Same stale version — 409 Conflict
curl -X PUT http://localhost:8080/us/properties/1 \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: $(uuidgen)" \
  -d '{"price": 600000.00, "version": 1}'
```

### Idempotency

```bash
RID=$(uuidgen)

curl -X PUT http://localhost:8080/us/properties/4 \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: $RID" \
  -d '{"price": 350000.00, "version": 1}'   # → 200

curl -X PUT http://localhost:8080/us/properties/4 \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: $RID" \
  -d '{"price": 350000.00, "version": 1}'   # → 422 Duplicate request
```

### Replication Lag

```bash
curl http://localhost:8080/eu/replication-lag
# {"lag_seconds": 1.234}
```

### NGINX Access Log (upstream response time)

```bash
docker logs nginx_proxy 2>&1 | tail -5
# ... upstream_response_time=0.003
```

### Database Verification

```bash
# Check US DB row count
docker exec db_us psql -U postgres -d properties_us -c "SELECT count(*) FROM properties;"

# Check EU DB after US update (replication)
docker exec db_eu psql -U postgres -d properties_eu -c \
  "SELECT id, price, version, updated_at FROM properties WHERE id = 2;"
```

---

## 🔬 Running Tests

### Integration tests (requires running stack)

```bash
cd tests
python test_concurrent_updates.py
```

Tests covered:
- ✅ NGINX routing for US and EU
- ✅ Successful PUT with version increment
- ✅ Optimistic locking (stale version → 409)
- ✅ Concurrent updates race condition (4 threads, same version → 1 winner)
- ✅ Idempotency (duplicate X-Request-ID → 422)
- ✅ Replication lag endpoint

### Failover demonstration

```bash
bash tests/demonstrate_failover.sh
```

Script steps:
1. Asserts `/us/health` returns 200 with backend-us running
2. Stops `backend-us` container
3. Asserts `/us/health` still returns 200 (EU is now serving US traffic)
4. Restarts `backend-us`

---

## 📡 API Reference

### `GET /{region}/health`
Returns `{"status": "ok", "region": "<region>"}` — used by NGINX and Docker healthchecks.

### `PUT /{region}/properties/{id}`

| Header | Required | Description |
|---|---|---|
| `Content-Type` | Yes | `application/json` |
| `X-Request-ID` | Recommended | UUID for idempotency |

**Request body:**
```json
{ "price": 500000.00, "version": 1 }
```

**Success (200):**
```json
{ "id": 1, "price": 500000.00, "version": 2, "updated_at": "..." }
```

**409 Conflict** — version mismatch (optimistic locking failure):
```json
{
  "error": "Version conflict",
  "message": "Current version is 3, but you sent version 1. Re-fetch and retry.",
  "current_version": 3
}
```

**422 Unprocessable Entity** — duplicate `X-Request-ID`:
```json
{
  "error": "Duplicate request",
  "detail": "Request ID 'abc-...' has already been processed.",
  "previous_response": { ... }
}
```

### `GET /{region}/replication-lag`
```json
{ "lag_seconds": 2.5 }
```

---

## ⚠️ Conflict Resolution Strategy

When a PUT returns **409 Conflict**, the client should:

1. **Re-fetch** the current state of the property (use the `current_version` in the error body)
2. **Merge** the intended change onto the fresh data
3. **Retry** the PUT with the updated version number

This is an optimistic concurrency control pattern. The system guarantees that only one writer wins per version increment, preventing "last writer wins" scenarios in concurrent updates.

---

## 📁 Project Structure

```
task-14/
├── docker-compose.yml          # Orchestrates all 7 services
├── .env.example                # Environment variable documentation
├── nginx/
│   └── nginx.conf              # Routing, failover, custom log format
├── backend/
│   ├── Dockerfile              # Python 3.11 + FastAPI image
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI app + lifespan hooks
│       ├── routes.py           # HTTP endpoints
│       ├── db.py               # asyncpg + optimistic locking queries
│       ├── kafka_producer.py   # aiokafka producer
│       └── kafka_consumer.py   # aiokafka consumer (cross-region replication)
├── seeds/
│   ├── init_us.sql             # Schema + 1200 US property rows
│   ├── init_eu.sql             # Schema + 1200 EU property rows
│   └── generate_seeds.py      # Seed generator script
└── tests/
    ├── test_concurrent_updates.py  # Integration tests (optimistic locking, etc.)
    └── demonstrate_failover.sh     # Automated failover demo
```

---

## 🔧 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_US_USER` | `postgres` | US DB username |
| `POSTGRES_US_PASSWORD` | *(set in .env)* | US DB password |
| `POSTGRES_US_DB` | `properties_us` | US database name |
| `POSTGRES_EU_USER` | `postgres` | EU DB username |
| `POSTGRES_EU_PASSWORD` | *(set in .env)* | EU DB password |
| `POSTGRES_EU_DB` | `properties_eu` | EU database name |
| `KAFKA_BROKER` | `kafka:29092` | Internal Kafka broker address |
| `DATABASE_URL` | *(computed)* | Full asyncpg DSN |
| `REGION` | `us` or `eu` | Controls consumer filter and logging |

---

## 🛑 Stopping the Stack

```bash
docker compose down            # Stop containers, preserve volumes
docker compose down -v         # Stop containers AND wipe all data volumes
```

## 🎥 Demo Video

https://drive.google.com/file/d/12Q9Sl8wbyeRYUKv38V-IdeSOEOF6hNgw/view?usp=sharing
