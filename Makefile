PYTHON ?= python3
VENV ?= .venv
ACTIVATE = . $(VENV)/bin/activate
SMOKE_ARGS ?=

.PHONY: help install lint test run dev docker-build docker-up docker-down clean smoke loadtest warm-cache

help:
	@echo "Common targets:"
	@echo "  make install     # create venv + install deps"
	@echo "  make lint        # run Ruff"
	@echo "  make test        # run pytest"
	@echo "  make run         # uvicorn in reload mode"
	@echo "  make docker-up   # run via docker compose"

install:
	python3 -m venv $(VENV)
	$(ACTIVATE) && pip install --upgrade pip && pip install -r requirements-dev.txt

lint:
	$(ACTIVATE) && ruff check .

test:
	$(ACTIVATE) && pytest

run:
	$(ACTIVATE) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

smoke:
	$(ACTIVATE) && python scripts/smoke_test.py $(SMOKE_ARGS)

loadtest:
	$(ACTIVATE) && locust -f loadtests/locustfile.py --headless -u 10 -r 2 --run-time 1m $(LOCUST_ARGS)

warm-cache:
	$(ACTIVATE) && python scripts/cache_warm.py $(WARM_ARGS)

clean:
	rm -rf $(VENV) .pytest_cache

docker-build:
	docker build -t greengate:latest .

docker-up:
	docker compose up --build

docker-down:
	docker compose down
