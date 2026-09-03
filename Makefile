.PHONY: help install dev migrate seed test lint format clean build up down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

dev: ## Start development environment
	docker-compose up -d postgres redis rabbitmq qdrant elasticsearch minio
	cd backend && uvicorn app.main:app --reload --port 8000
	cd frontend && npm run dev

migrate: ## Run database migrations
	cd backend && alembic upgrade head

seed: ## Seed initial data
	cd backend && python scripts/seed.py

test: ## Run all tests
	cd backend && pytest
	cd frontend && npm test

lint: ## Run linters
	cd backend && ruff check . && ruff format --check .
	cd frontend && npm run lint

format: ## Format code
	cd backend && ruff format .
	cd frontend && npm run format

clean: ## Clean build artifacts
	rm -rf backend/__pycache__ backend/.pytest_cache
	rm -rf frontend/.next frontend/node_modules
	rm -rf *.egg-info dist build

build: ## Build Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d

down: ## Stop all services
	docker-compose down

logs: ## View logs
	docker-compose logs -f
