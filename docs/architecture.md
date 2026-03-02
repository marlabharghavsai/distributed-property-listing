# Architecture Overview

## System Design

```
                        ┌─────────────────────────────────────────┐
                        │      Client (Browser / curl / API)      │
                        └──────────────┬──────────────────────────┘
                                       │ HTTP :8080
                        ┌──────────────▼──────────────────────────┐
                        │            NGINX (Reverse Proxy)         │
                        │  /us/* ──► us_backend  (backup: eu)      │
                        │  /eu/* ──► eu_backend  (backup: us)      │
                        │  logs: upstream_response_time            │
                        └──────┬───────────────────┬──────────────┘
                               │                   │
               ┌───────────────▼──┐           ┌────▼────────────────┐
               │  backend-us      │           │  backend-eu          │
               │  FastAPI         │           │  FastAPI             │
               │  REGION=us       │           │  REGION=eu           │
               │  :8000           │           │  :8000               │
               └──────┬───────────┘           └──────┬──────────────┘
                      │                              │
         ┌────────────▼──────────┐      ┌────────────▼──────────┐
         │  PostgreSQL (db-us)   │      │  PostgreSQL (db-eu)   │
         │  properties (1200)    │      │  properties (1200)    │
         │  processed_requests   │      │  processed_requests   │
         └───────────────────────┘      └───────────────────────┘
                      │                              │
                      └──────────┬───────────────────┘
                                 │
                    ┌────────────▼──────────────────┐
                    │   Apache Kafka + Zookeeper     │
                    │   topic: property-updates      │
                    │   Producers: both backends     │
                    │   Consumers: opposite region   │
                    └────────────────────────────────┘
```

## Data Flow

### Write Path (PUT /us/properties/{id})
1. Client sends PUT with `X-Request-ID` header and `version` field
2. NGINX routes `/us/*` → `backend-us`
3. Backend checks idempotency store (`processed_requests` table)
   - If duplicate `X-Request-ID` → return **422** immediately
4. Backend performs optimistic locking UPDATE:
   - SQL: `UPDATE properties SET price=?, version=version+1, ... WHERE id=? AND version=?`
   - If 0 rows affected → fetch current version → return **409 Conflict**
   - If 1 row affected → success → return **200**
5. On success: publish event to Kafka `property-updates` topic
6. Save `X-Request-ID` + response to `processed_requests`

### Replication Path (Kafka Consumer)
1. Each backend subscribes to `property-updates` topic
2. Filters out messages where `region_origin == own REGION`
3. Applies the update to the local DB using an upsert
4. Records `last_consumed_ts` for lag calculation

### Failover Path (NGINX)
1. If primary backend is unreachable (connection error / timeout)
2. NGINX automatically retries on the `backup` server
3. No change in client-facing URL — transparent failover

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Optimistic locking (not pessimistic) | Higher throughput; conflicts are rare in typical workloads |
| Kafka for replication (not sync RPC) | Decoupled; EU can lag but won't block US writes |
| Idempotency via DB table | Survives restarts; no in-memory state needed |
| Shared backend image | Single codebase, differentiated by `REGION` env var |
| NGINX `backup` directive | Simple, zero-config failover without external health check service |

## Database Schema

```sql
CREATE TABLE properties (
    id             SERIAL PRIMARY KEY,
    price          NUMERIC(12,2) NOT NULL,
    bedrooms       INT NOT NULL,
    bathrooms      INT NOT NULL,
    region_origin  VARCHAR(10) NOT NULL,
    version        INT NOT NULL DEFAULT 1,
    updated_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE processed_requests (
    request_id     VARCHAR(128) PRIMARY KEY,
    response_body  TEXT NOT NULL,
    created_at     TIMESTAMP DEFAULT NOW()
);
```
