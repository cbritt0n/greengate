# GreenGate 🌿

Energy-aware AI Gateway + Semantic Cache for every LLM provider you care about. GreenGate proxies chat completions, ranks providers with an eco-conscious router, streams responses end-to-end, and tracks joules spent/saved in a persistent ledger with Prometheus metrics.

## Highlights

- **ECO Router (WPM algorithm)** – Multi-criteria scorer (cost, latency, reliability, energy) picks the best configured provider (OpenAI, Anthropic, Cohere, Azure OpenAI today, pluggable tomorrow) per request.
- **Streaming + non-streaming** – Streams vendor SSE directly to clients, while non-streaming responses flow through a ChromaDB semantic cache with similarity gating and token-aware metadata.
- **Persistent energy ledger** – Every joule spent/saved is logged into SQLite for audits, surfaced at `/` and `/metrics`.
- **Observability ready** – `X-GreenGate-*` headers, Prometheus counters/histograms, OpenTelemetry tracing (optional), `/healthz`, structured logging, GitHub Actions CI, Ruff + pytest automation.
- **Security & resilience** – Token buckets per user, configurable retries/backoff, async HTTPX client reuse, telemetry opt-outs, `.env`-driven provider catalog.

## Quickstart

### Local (venv)

```bash
git clone https://github.com/cbritt0n/greengate.git
cd greengate
cp .env.example .env           # add your provider keys
make install                   # or python -m venv .venv && pip install -r requirements-dev.txt
make run                       # reload-enabled dev server on :8000
```

### Docker / Compose

```bash
make docker-up                 # builds image + runs compose.yaml
# stop
make docker-down
```

### Dev Containers / Codespaces

Open the repo in VS Code and run **Dev Containers: Reopen in Container**. The `.devcontainer` definition layers the project Dockerfile plus the required Python extensions.

See `docs/DEPLOYMENT.md` for production guidance (scaling workers, health checks, Prometheus scraping, etc.).

### Key Configuration

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `COHERE_API_KEY`, `AZURE_OPENAI_API_KEY` | Provider credentials (set any combination). |
| `COHERE_API_BASE` | Override Cohere endpoint (default `https://api.cohere.ai`). |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION` | Azure endpoint base (e.g., `https://my-resource.openai.azure.com`) + API version. |
| `AZURE_OPENAI_DEPLOYMENT_MAP` | Comma list of `model=deployment` pairs (`gpt-4o=prod-gpt4o,gpt-4o-mini=mini`). |
| `LLM_PROVIDER_SEQUENCE` | Preferred routing order (`openai,anthropic,...`). |
| `MODEL_ROUTER_WEIGHTS` | Weighted product model coefficients (`cost=0.35,latency=0.2,...`). |
| `CACHE_SIMILARITY_THRESHOLD` / `CACHE_TOP_K` | Semantic cache sensitivity + breadth. |
| `RATE_LIMIT_PER_MINUTE` | Token-bucket limit per requester. |
| `PROMETHEUS_METRICS_ENABLED` | Toggle `/metrics` endpoint. |
| `CACHE_PERSIST_PATH`, `LEDGER_DB_PATH` | Override disk locations for cache + SQLite energy ledger. |
| `OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS` | Enable tracing and point to OTLP collector (headers optional `key=value` list). |

See `.env.example` for the full matrix of tunables.

> **Azure OpenAI mapping** – Provide every model→deployment pairing (comma-delimited) so the proxy can route to the correct Azure deployment. Example: `AZURE_OPENAI_DEPLOYMENT_MAP=gpt-4o=prod4o,gpt-4o-mini=mini4o`.

## API Surface

| Endpoint | Description |
| --- | --- |
| `POST /v1/chat/completions` | Drop-in OpenAI-compatible body. Automatic provider routing. Headers: `X-GreenGate-Status`, `X-GreenGate-Energy-Joules`, `X-GreenGate-Provider`, `X-GreenGate-Cache-Similarity`. Supports `"stream": true` for SSE pass-through. |
| `GET /` | JSON diagnostics with cumulative joules spent/saved and request counts (via SQLite ledger). |
| `GET /healthz` | Lightweight readiness probe. |
| `GET /metrics` | Prometheus exposition (Guarded by `PROMETHEUS_METRICS_ENABLED`). |

### Example Request

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "gpt-4o-mini",
        "messages": [
          {"role": "system", "content": "You summarize sustainably."},
          {"role": "user", "content": "How can I green my API?"}
        ]
      }' | jq '.'
```

Streaming (SSE) is just as easy:

```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-3-haiku", "messages": [{"role": "user", "content": "Tell me a limerick"}], "stream": true}'
```

## Architecture Overview

```
┌────────────┐   cache miss   ┌──────────────┐   scored by   ┌────────────────┐
│ Client App │ ─────────────▶ │ Rate Limiter │ ────────────▶ │ ECO ModelRouter │
└────────────┘                └──────────────┘               └────────────────┘
        ▲                               │                              │
        │                               ▼                              ▼
   cache hit ◀───────────── ChromaDB Semantic Cache ◀── ProxyService ⇄ Providers
                                   │                               (OpenAI, Anthropic,...)
                                   ▼
                        Energy Ledger (SQLite) → Prometheus Metrics
```

- **CacheService** – Persistent ChromaDB collection with hybrid exact-hash + cosine similarity to eliminate duplicate calls above a configurable threshold.
- **ProxyService + Providers** – Shared async HTTPX client, provider-specific translators (OpenAI, Anthropic) and streaming passthrough.
- **ModelRouter** – Weighted product model (WPM) ranks candidates on cost, latency, reliability, and energy modifier, then selects the winning provider for each model.
- **EnergyLedger** – Persists joule stats per request for audits and dashboards.
- **Observability** – Prometheus counters/histograms + structured logging; root endpoint surfaces ledger snapshots.

## Operations Docs

- `docs/DEPLOYMENT.md` – local, Docker, devcontainer, and production rollout guidance.
- `docs/OPERATIONS.md` – runbook for metrics, persistence, rate limiting, and provider onboarding.

## Tooling, Testing & CI

```bash
make lint             # Ruff
make test             # pytest (async services + routers)
make docker-build     # smoke build container image
make smoke            # run scripts/smoke_test.py against local/staging URL
make loadtest         # run Locust in headless mode (overrides via LOCUST_ARGS)
```

CI (`.github/workflows/ci.yml`) now caches pip deps, runs lint/tests, and finishes with a Docker build smoke test. PRs must also satisfy the GitHub templates + checklist.

Tagging `v*.*.*` automatically triggers `.github/workflows/release.yml`, which reruns lint/tests, builds/pushes `ghcr.io/<repo>` images, and publishes GitHub Releases with generated notes.

## Extending GreenGate

1. **Add a Provider** – Implement `LLMProvider` in `app/providers/`, add entries to `Settings.provider_configs()`, and list it in `LLM_PROVIDER_SEQUENCE`.
2. **Tune the Router** – Adjust `MODEL_ROUTER_WEIGHTS` to bias toward cost, latency, uptime, or energy impact.
3. **Deep Metrics** – Hook Prometheus output into Grafana, or read the SQLite ledger directly for emission reports.
4. **Cache Warmers** – Use dependency overrides or a simple script to pre-seed the ChromaDB store for heavy workflows.
5. **Docs** – Add more runbooks under `docs/` (deployment + operations guides already included).

Contributions welcome! See `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md`, then open an issue or pull request with ideas for more providers, dashboards, or carbon intelligence modules.
