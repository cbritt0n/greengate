# Operations Runbook

## Logs

FastAPI/uvicorn logs go to STDOUT. Each request includes a `request_id` field (FastAPI middleware) so you can correlate downstream logs from providers.

## Metrics

Prometheus metrics (enabled by default) include:

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `greengate_requests_total` | Counter | `provider`, `cache`, `status` | Total chat completion calls |
| `greengate_energy_joules` | Histogram | _none_ | Distribution of joules spent per request |
| `greengate_energy_saved_joules` | Histogram | _none_ | Distribution of joules saved thanks to cache hits |

Scrape `/metrics` and forward to your observability stack. Pair these with the SQLite ledger for audits.

## Persistence

- **Chroma cache** – stored in `CACHE_PERSIST_PATH` (defaults to `data/cache`).
- **Energy ledger** – SQLite DB at `LEDGER_DB_PATH` (defaults to `data/ledger.db`).

Make sure both paths live on durable storage in production.

## Rate Limiting

`RATE_LIMIT_PER_MINUTE` governs a token bucket per unique caller (API key or IP). Throttled requests return `429` with `Retry-After` header. Tune this per environment.

## Smoke Testing

Use `scripts/smoke_test.py` (via `make smoke` or direct execution) to validate a deployment after provisioning. Configure the target URL with `--base-url` or `GREENGATE_BASE_URL` and set `--stream` to validate SSE.

## Load Testing

There is a lightweight Locust scenario under `loadtests/locustfile.py`. Run `make loadtest LOCUST_ARGS="-u 20 -r 5 --run-time 2m"` to stress `/v1/chat/completions` against a staging deployment. Tune the environment through `GREENGATE_BASE_URL`, `GREENGATE_MODEL`, and `GREENGATE_PROMPT`.

## OpenTelemetry Tracing

Enable distributed tracing by setting `OTEL_ENABLED=true` and pointing `OTEL_EXPORTER_OTLP_ENDPOINT` at your collector (e.g., `https://otlp.yourcompany.com/v1/traces`). Optional headers are supplied via `OTEL_EXPORTER_OTLP_HEADERS` as comma-separated `key=value` pairs for authentication. Once enabled, FastAPI request spans and outbound HTTPX calls to providers are emitted automatically.

## Provider Onboarding Checklist

1. Extend `app/providers` with an `LLMProvider` implementation (OpenAI, Anthropic, Cohere, and Azure OpenAI included by default).
2. Add config keys to `.env.example` & `Settings.provider_configs()`.
3. Register the provider in `LLM_PROVIDER_SEQUENCE` and optionally adjust router weights.
4. Add unit tests + docs.

## Disaster Recovery

- Cache is recreatable; ledger DB forms the source of truth for historical energy usage. Backup the ledger file (e.g., via nightly blob storage uploads).
- Configure CI to run `pytest` + `docker build` (see `.github/workflows/ci.yml`).
- Keep provider API keys rotated per your organization's policy.
