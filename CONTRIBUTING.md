# Contributing to GreenGate

Thanks for helping build a greener AI gateway! This document captures the expectations for issues, code, and releases.

## Development Flow

1. **Fork & branch** – create a descriptive branch (e.g., `feature/provider-cohere`).
2. **Set up tooling** – run `make install` (or `pip install -r requirements.txt`) and copy `.env.example` to `.env` with your provider keys.
3. **Tests before commits** – `make lint test` must pass locally. Add new tests for every feature or bug fix.
4. **Conventional commits** – use short, action-oriented messages (`feat: add cohere provider`).
5. **Pull requests** – fill out the PR template, link an issue, and describe verification steps/screenshots.

## Coding Guidelines

- **Async-first** – prefer `async`/`await`, `httpx.AsyncClient`, and non-blocking IO.
- **Small, testable units** – isolate provider integrations, cache utilities, and routers behind services.
- **Config via settings** – never hardcode secrets; extend `app/core/config.py` and `.env.example`.
- **Documentation** – update README or `/docs` whenever behavior or operations change.

## Testing Matrix

| Layer | Command |
| --- | --- |
| Unit | `pytest` |
| Lint | `ruff check .` |
| Type stubs (optional) | `pyright` (if installed) |
| Docker smoke | `make docker-build` |

## Raising Issues

- Use the issue templates.
- Provide reproduction steps, expected/actual results, and logs/headers when relevant.
- Label sustainability impact if the change ties to measurable energy savings.

## Security Reports

Never disclose vulnerabilities in public issues. Email `security@greengate.local` per `SECURITY.md` and follow responsible disclosure procedures.

## Code of Conduct

Participation is governed by the [Contributor Covenant](CODE_OF_CONDUCT.md). Report unacceptable behavior via the channels listed in `SECURITY.md`.
