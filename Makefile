.PHONY: help up down migrate test lint format typecheck export-openapi clean

help:
	@echo "ThinkBuddy Task Runner"
	@echo "======================"
	@echo "up              - Start services using Docker Compose"
	@echo "down            - Stop and remove Docker Compose services"
	@echo "migrate         - Run Alembic database migrations"
	@echo "test            - Run pytest suite"
	@echo "lint            - Run ruff linter and format check"
	@echo "format          - Format code using ruff"
	@echo "typecheck       - Run static type checking with mypy"
	@echo "export-openapi  - Export OpenAPI JSON to docs-generated/openapi.json"

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	alembic upgrade head

test:
	pytest -v tests/

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

typecheck:
	mypy core gateway workers

export-openapi:
	python scripts/export_openapi.py

clean:
	docker compose down -v --remove-orphans
