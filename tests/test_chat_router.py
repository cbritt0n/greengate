from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.dependencies import (
    get_cache_service,
    get_energy_ledger,
    get_proxy_service,
    get_rate_limiter,
)
from app.main import app
from app.providers.base import ProviderResult
from app.schemas.chat import ChatMessage
from app.services.cache_service import CacheHit


class DummyCache:
    def __init__(self) -> None:
        self.hit: CacheHit | None = None
        self.saved_payload = None

    async def get_cached_response(self, prompt: str):  # noqa: D401 - simple stub
        return self.hit

    async def save_response(self, *args, **kwargs):  # noqa: ANN001 - forward args
        self.saved_payload = {
            "args": args,
            "kwargs": kwargs,
        }


class DummyProxy:
    def __init__(self) -> None:
        self.calls = []
        self.response = {
            "choices": [
                {"message": {"role": "assistant", "content": "Hello!"}},
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

    async def forward_request(self, payload: dict, stream: bool = False):
        self.calls.append({"stream": stream, "payload": payload})
        if stream:
            async def fake_stream():  # pragma: no cover - not used in non-stream tests
                yield b"data: test\n\n"

            return ProviderResult(
                provider_name="openai",
                response=None,
                usage=self.response["usage"],
                energy_modifier=1.0,
                stream=fake_stream(),
            )
        return ProviderResult(
            provider_name="openai",
            response=self.response,
            usage=self.response["usage"],
            energy_modifier=1.0,
        )


class DummyLedger:
    def __init__(self) -> None:
        self.records = []

    async def record(self, **data):
        self.records.append(data)

    async def snapshot(self):
        return {"requests": float(len(self.records)), "energy_spent": 0.0, "energy_saved": 0.0}


class DummyLimiter:
    async def check(self, identifier: str):  # noqa: D401 - stub
        return None


@pytest.fixture
def test_client():
    dummy_cache = DummyCache()
    dummy_proxy = DummyProxy()
    dummy_ledger = DummyLedger()
    dummy_limiter = DummyLimiter()

    app.dependency_overrides[get_cache_service] = lambda: dummy_cache
    app.dependency_overrides[get_proxy_service] = lambda: dummy_proxy
    app.dependency_overrides[get_energy_ledger] = lambda: dummy_ledger
    app.dependency_overrides[get_rate_limiter] = lambda: dummy_limiter

    with TestClient(app) as client:
        yield client, dummy_cache, dummy_proxy, dummy_ledger

    app.dependency_overrides.clear()


def _build_payload():
    return {
        "model": "gpt-3.5-turbo",
        "messages": [ChatMessage(role="user", content="Hello?").model_dump()],
    }


def test_cache_hit_short_circuits_network(test_client):
    client, dummy_cache, dummy_proxy, dummy_ledger = test_client
    dummy_cache.hit = CacheHit(
        response={"choices": [{"message": {"content": "cached"}}]},
        metadata={
            "prompt_tokens": "5",
            "completion_tokens": "5",
            "energy_joules": "1.5",
            "provider": "openai",
        },
        similarity=0.99,
    )

    resp = client.post("/v1/chat/completions", json=_build_payload())

    assert resp.status_code == 200
    assert resp.headers["X-GreenGate-Status"] == "CACHE_HIT"
    assert len(dummy_proxy.calls) == 0
    assert dummy_ledger.records[0]["saved"] == 1.5


def test_cache_miss_proxies_and_persists(test_client):
    client, dummy_cache, dummy_proxy, dummy_ledger = test_client

    resp = client.post("/v1/chat/completions", json=_build_payload())

    assert resp.status_code == 200
    assert resp.headers["X-GreenGate-Status"] == "CACHE_MISS"
    assert len(dummy_proxy.calls) == 1
    assert dummy_cache.saved_payload is not None
    assert dummy_ledger.records[0]["spent"] > 0


def test_streaming_bypasses_cache(test_client):
    client, dummy_cache, dummy_proxy, dummy_ledger = test_client
    payload = _build_payload()
    payload["stream"] = True

    resp = client.post("/v1/chat/completions", json=payload)

    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith("text/event-stream")
    assert resp.headers["X-GreenGate-Status"] == "STREAMING"
    assert len(dummy_proxy.calls) == 1
    assert len(dummy_ledger.records) == 1


def test_gateway_auth_rejects_missing_token(monkeypatch, test_client):
    from app.core.config import settings

    previous = settings.GATEWAY_API_KEY
    monkeypatch.setattr(settings, "GATEWAY_API_KEY", "secret")
    try:
        client, *_ = test_client
        resp = client.post("/v1/chat/completions", json=_build_payload())
        assert resp.status_code == 401
    finally:
        monkeypatch.setattr(settings, "GATEWAY_API_KEY", previous)


def test_gateway_auth_allows_bearer_token(monkeypatch, test_client):
    from app.core.config import settings

    previous = settings.GATEWAY_API_KEY
    monkeypatch.setattr(settings, "GATEWAY_API_KEY", "secret")
    try:
        client, *_ = test_client
        resp = client.post(
            "/v1/chat/completions",
            json=_build_payload(),
            headers={"Authorization": "Bearer secret"},
        )
        assert resp.status_code == 200
    finally:
        monkeypatch.setattr(settings, "GATEWAY_API_KEY", previous)

