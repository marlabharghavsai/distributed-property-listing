# Contributing Guide

Thank you for considering contributing to this project!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/marlabharghavsai/distributed-property-listing.git
   cd distributed-property-listing
   ```

2. Copy the environment file:
   ```bash
   cp .env.example .env
   ```

3. Start the stack:
   ```bash
   docker compose up -d --build
   ```

## Project Structure

```
.
├── backend/          # FastAPI application (shared for US and EU)
│   ├── app/
│   │   ├── db.py             # asyncpg database layer
│   │   ├── kafka_consumer.py # Cross-region replication consumer
│   │   ├── kafka_producer.py # Event publisher
│   │   ├── main.py           # FastAPI app entry point
│   │   └── routes.py         # API endpoints
│   ├── Dockerfile
│   └── requirements.txt
├── nginx/            # NGINX reverse proxy config
├── seeds/            # PostgreSQL seed data
└── tests/            # Integration tests and demo scripts
```

## Running Tests

```bash
# Full integration test suite
python tests/test_concurrent_updates.py

# NGINX failover demo (requires bash)
bash tests/demonstrate_failover.sh
```

## Code Style

- Python: Follow PEP 8 conventions
- Commit messages: Use conventional commits format (`feat:`, `fix:`, `chore:`, `docs:`, `test:`)

## Submitting Changes

1. Create a feature branch: `git checkout -b feat/your-feature`
2. Make your changes with clear, atomic commits
3. Push and open a pull request describing your changes
