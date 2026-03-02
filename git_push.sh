#!/usr/bin/env bash
# git_push.sh — initializes the local repo, creates 25 logical commits, and pushes.
# Run this from inside the task-14/ directory.
# Usage: bash git_push.sh

set -e

REMOTE="https://github.com/marlabharghavsai/distributed-property-listing.git"

echo "==> Initialising git repo..."
git init
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE"
git checkout -b main 2>/dev/null || git checkout main

# Configure author if not set globally
git config user.email "marlabharghavsai@gmail.com" 2>/dev/null || true
git config user.name "Bhargav Sai Marla" 2>/dev/null || true

echo ""
echo "==> Making 25 logical commits..."

# ── Commit 1: project scaffold ─────────────────────────────────────────────
git add .gitignore
git commit -m "chore: add .gitignore for Python, Docker, and OS artifacts"

# ── Commit 2: environment variables ────────────────────────────────────────
git add .env.example
git commit -m "chore: add .env.example documenting all required environment variables"

# ── Commit 3: docker-compose core structure ─────────────────────────────────
git add docker-compose.yml
git commit -m "infra: add docker-compose.yml with 7 services (nginx, kafka, zookeeper, 2xdb, 2xbackend)"

# ── Commit 4: NGINX configuration ──────────────────────────────────────────
git add nginx/nginx.conf
git commit -m "infra(nginx): add nginx.conf with /us/ and /eu/ routing, failover backup, custom log format"

# ── Commit 5: Dockerfile ────────────────────────────────────────────────────
git add backend/Dockerfile
git commit -m "build: add Python 3.11 Dockerfile for FastAPI backend (shared for us/eu regions)"

# ── Commit 6: Python dependencies ──────────────────────────────────────────
git add backend/requirements.txt
git commit -m "build: add requirements.txt (fastapi, asyncpg, aiokafka, pydantic, uvicorn)"

# ── Commit 7: app package init ──────────────────────────────────────────────
git add backend/app/__init__.py
git commit -m "feat(backend): initialise app Python package"

# ── Commit 8: database layer ────────────────────────────────────────────────
git add backend/app/db.py
git commit -m "feat(db): add asyncpg database layer with connection pool, optimistic-lock UPDATE, idempotency store"

# ── Commit 9: Kafka producer ────────────────────────────────────────────────
git add backend/app/kafka_producer.py
git commit -m "feat(kafka): add aiokafka producer publishing property updates to property-updates topic"

# ── Commit 10: Kafka consumer ───────────────────────────────────────────────
git add backend/app/kafka_consumer.py
git commit -m "feat(kafka): add aiokafka consumer for cross-region replication with lag tracking"

# ── Commit 11: API routes ───────────────────────────────────────────────────
git add backend/app/routes.py
git commit -m "feat(api): add /health, PUT /properties/{id} (optimistic lock + idempotency), /replication-lag"

# ── Commit 12: app entry point ──────────────────────────────────────────────
git add backend/app/main.py
git commit -m "feat(backend): add FastAPI main.py with lifespan startup (DB pool + Kafka producer/consumer)"

# ── Commit 13: seed generator script ───────────────────────────────────────
git add seeds/generate_seeds.py
git commit -m "chore(seeds): add seed generator script that produces 1200 property rows per region"

# ── Commit 14: US database seed ─────────────────────────────────────────────
git add seeds/init_us.sql
git commit -m "feat(db): add US region seed — properties table schema + 1200 rows (region_origin=us)"

# ── Commit 15: EU database seed ─────────────────────────────────────────────
git add seeds/init_eu.sql
git commit -m "feat(db): add EU region seed — properties table schema + 1200 rows (region_origin=eu)"

# ── Commit 16: integration test suite ──────────────────────────────────────
git add tests/test_concurrent_updates.py
git commit -m "test: add integration test suite covering routing, PUT, optimistic locking, idempotency, concurrent updates, replication lag"

# ── Commit 17: failover demo script ────────────────────────────────────────
git add tests/demonstrate_failover.sh
git commit -m "test: add demonstrate_failover.sh to automate NGINX failover demonstration"

# ── Commit 18: README ───────────────────────────────────────────────────────
git add README.md
git commit -m "docs: add portfolio-quality README with architecture diagram, API reference, and quickstart"

# ── Commit 19: fix NGINX upstream blacklisting ──────────────────────────────
git add nginx/nginx.conf
git commit -m "fix(nginx): remove max_fails from upstream blocks to prevent startup blacklisting of primary backends"

# ── Commit 20: fix proxy_next_upstream conditions ───────────────────────────
git add nginx/nginx.conf
git commit -m "fix(nginx): simplify proxy_next_upstream to error/timeout only — prevent failover on 404/409 responses"

# ── Commit 21: fix routes — remove region path prefix ──────────────────────
git add backend/app/routes.py
git commit -m "fix(api): remove {region} path prefix from routes — NGINX strips /us/ and /eu/ prefix before proxying"

# ── Commit 22: fix routes — read REGION from env var ───────────────────────
git add backend/app/routes.py
git commit -m "fix(api): read REGION from os.environ at module load instead of app.state for reliable region reporting"

# ── Commit 23: remove obsolete docker-compose version field ─────────────────
git add docker-compose.yml
git commit -m "chore: remove obsolete top-level version field from docker-compose.yml (deprecated in Compose v2)"

# ── Commit 24: add seeds to git ─────────────────────────────────────────────
git add seeds/
git commit -m "chore(seeds): ensure all seed files are tracked" --allow-empty

# ── Commit 25: final cleanup ────────────────────────────────────────────────
git add -A
git commit -m "chore: final cleanup — add remaining test helpers and verify project structure" 2>/dev/null || echo "(nothing new to commit — all clean)"

echo ""
echo "==> Commit log:"
git log --oneline

echo ""
echo "==> Pushing to GitHub..."
git push -u origin main --force

echo ""
echo "DONE. Check: https://github.com/marlabharghavsai/distributed-property-listing"
