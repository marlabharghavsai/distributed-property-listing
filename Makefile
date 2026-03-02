.DEFAULT_GOAL := help

.PHONY: help up down logs ps test failover rebuild clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Start all services (detached)
	docker compose up -d

build: ## Build and start all services
	docker compose up -d --build

down: ## Stop and remove all containers
	docker compose down

logs: ## Tail logs for all services
	docker compose logs -f

ps: ## Show service status and health
	docker compose ps

test: ## Run integration tests (stack must be running)
	python tests/test_concurrent_updates.py

failover: ## Run the NGINX failover demonstration
	bash tests/demonstrate_failover.sh

health: ## Check health of both regions via NGINX
	@echo "--- US Region ---"
	@curl -s http://localhost:8080/us/health | python -m json.tool
	@echo "--- EU Region ---"
	@curl -s http://localhost:8080/eu/health | python -m json.tool

lag: ## Check replication lag for both regions
	@echo "--- US Replication Lag ---"
	@curl -s http://localhost:8080/us/replication-lag | python -m json.tool
	@echo "--- EU Replication Lag ---"
	@curl -s http://localhost:8080/eu/replication-lag | python -m json.tool

rebuild: ## Rebuild only the backend services (no cache)
	docker compose build --no-cache backend-us backend-eu
	docker compose up -d --no-deps backend-us backend-eu

clean: ## Stop containers and remove volumes (WARNING: deletes DB data)
	docker compose down -v
