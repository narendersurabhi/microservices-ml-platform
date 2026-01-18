.PHONY: up down test lint format typecheck e2e

up:
	docker compose up -d --build

down:
	docker compose down -v

test:
	pytest

lint:
	ruff check .

format:
	black .

typecheck:
	mypy .

e2e:
	docker compose up -d --build
