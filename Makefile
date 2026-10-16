# scanota Makefile
# Use tabs for recipe indentation (required by make).
# Run `make help` to list targets.

.PHONY: help up down logs build \
        test test-integration \
        lint format \
        synth demo-data \
        eval backtest

# ----------------------------------------------------------------
# Infrastructure
# ----------------------------------------------------------------

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

# ----------------------------------------------------------------
# Testing
# ----------------------------------------------------------------

test:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v -m integration

# ----------------------------------------------------------------
# Code quality
# ----------------------------------------------------------------

lint:
	ruff check app tests

format:
	ruff format app tests

# ----------------------------------------------------------------
# Data
# ----------------------------------------------------------------

synth:
	python -m app.synth.generate
	python -m app.synth.render_receipts

demo-data:
	docker compose exec api python -m app.db.seed

# ----------------------------------------------------------------
# Evaluation
# ----------------------------------------------------------------

eval:
	docker compose exec api python -m app.eval.ocr_eval

backtest:
	docker compose exec api python -m app.eval.backtest

# ----------------------------------------------------------------
# Help
# ----------------------------------------------------------------

help:
	@echo "Available targets:"
	@echo "  up              Build and start all services"
	@echo "  down            Stop all services"
	@echo "  logs            Follow service logs"
	@echo "  build           Build Docker images"
	@echo "  test            Run unit tests"
	@echo "  test-integration Run integration tests"
	@echo "  lint            Run ruff linter"
	@echo "  format          Run ruff formatter"
	@echo "  synth           Generate synthetic data locally"
	@echo "  demo-data       Load seed data into running API"
	@echo "  eval            Run OCR evaluation (needs endpoint)"
	@echo "  backtest        Run forecast backtest"
