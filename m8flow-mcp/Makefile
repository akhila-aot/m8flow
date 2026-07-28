# Makefile for m8flow-mcp

.PHONY: help install dev lint format type-check test test-cov clean docker-build docker-run docker-stop

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install --upgrade pip
	pip install -e .

dev: ## Install development dependencies
	pip install --upgrade pip
	pip install -e ".[dev]"

lint: ## Run linting (Ruff)
	ruff check .

format: ## Format code (Ruff)
	ruff format .

format-check: ## Check code formatting
	ruff format --check .

type-check: ## Run type checking (mypy)
	mypy src/

test: ## Run tests
	pytest tests/ -v

test-cov: ## Run tests with coverage
	pytest tests/ --cov=src --cov-report=term-missing --cov-report=html --cov-report=xml

clean: ## Clean generated files
	rm -rf build/ dist/ *.egg-info htmlcov/ .pytest_cache/ .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type f -name '*.pyd' -delete

# Docker targets
docker-build: ## Build Docker image (production)
	docker build -t m8flow/m8flow-mcp:latest .

docker-build-dev: ## Build Docker image (development)
	docker build -t m8flow/m8flow-mcp:dev .

docker-run: ## Run Docker container
	docker compose up -d

docker-stop: ## Stop Docker containers
	docker compose down

docker-logs: ## Show Docker logs
	docker compose logs -f

docker-shell: ## Open shell in running container
	docker compose exec m8flow-mcp /bin/sh

# CI/CD targets
ci-lint: lint format-check ## Run linting for CI

ci-test: ## Run tests for CI
	pytest tests/ --cov=src --cov-report=xml --junit-xml=test-results.xml

ci-build: ## Build for CI
	docker build -t m8flow/m8flow-mcp:ci .

# Local development
run: ## Run server locally (stdio mode)
	python -m src.main

run-http: ## Run server locally (HTTP mode)
	SERVER_TYPE=remote python -m src.main

run-dev: ## Run server locally with auto-reload
	DEBUG=true RELOAD=true python -m src.main

# Database/Migration (if needed in future)
# migrate: ## Run database migrations
# 	alembic upgrade head

# migrate-create: ## Create new migration
# 	alembic revision --autogenerate -m "$(message)"
