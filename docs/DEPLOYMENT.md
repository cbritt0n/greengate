# Deployment Guide

GreenGate can run anywhere Python 3.11 is supported. Pick the target that matches your environment.

## 1. Local development

```bash
cp .env.example .env
make install
make run
```

The API listens on `http://localhost:8000`. Cached embeddings + the SQLite ledger are stored beneath `data/` (overridable via `.env`).

## 2. Docker / Compose

Build and run the containerized stack (includes a persistent volume for `/app/data`).

```bash
make docker-up
# or manually
docker compose up --build
```

This uses the repo `Dockerfile` and `compose.yaml` to expose port 8000. Update `.env` before running.

Stop everything with `make docker-down`.

## 3. GitHub Codespaces / Dev Containers

VS Code and Codespaces pick up `.devcontainer/devcontainer.json`. Open the folder with **Dev Containers: Reopen in Container**, then run `pip install -r requirements.txt` (executed automatically post-create).

For development (lint/tests/load testing), install:

```bash
pip install -r requirements-dev.txt
```

For a minimal runtime install, use:

```bash
pip install -r requirements.txt
```

## 4. Production

- Run `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers <n>` behind a reverse proxy (nginx, Azure App Gateway, Cloud Run, etc.).
- Mount a persistent volume for `CACHE_PERSIST_PATH` and `LEDGER_DB_PATH`.
- Set `PROMETHEUS_METRICS_ENABLED=false` if exposing `/metrics` externally is undesirable.
- Flip `OTEL_ENABLED=true` and configure OTLP endpoint/headers if you want distributed traces alongside metrics.
- Use your platform's secret manager (GitHub Actions, AWS SSM, Azure Key Vault) to inject provider keys.
- Make sure `.env` contains at least one provider API key (OpenAI, Anthropic, or Cohere) before launching.
- Wire Prometheus scraping via `/metrics` (or have an agent sidecar).
## 5. Health & Observability

| Endpoint | Purpose |
| --- | --- |
| `/healthz` | Container/ingress readiness probe |
| `/metrics` | Prometheus exposition (enable/disable via env) |
| `/` | JSON snapshot of the energy ledger |

All responses include `X-Request-Id` and `X-GreenGate-*` headers for debugging. See `docs/OPERATIONS.md` for deeper metrics guidance.
