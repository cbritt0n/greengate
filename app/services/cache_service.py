from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings


@dataclass(slots=True)
class CacheHit:
    response: dict
    metadata: dict[str, str]
    similarity: float

    @property
    def estimated_energy(self) -> float:
        raw_value = self.metadata.get("energy_joules", "0")
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return 0.0


class CacheService:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(
            path=str(settings.cache_path()),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.CACHE_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._exact_cache: dict[str, CacheHit] = {}

    @staticmethod
    def _hash_prompt(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    @staticmethod
    def _distance_to_similarity(distance: float | None) -> float:
        if distance is None:
            return 0.0
        if distance <= 0:
            return 1.0
        return 1.0 / (1.0 + distance)

    async def get_cached_response(self, prompt: str) -> CacheHit | None:
        prompt_hash = self._hash_prompt(prompt)
        cached = self._exact_cache.get(prompt_hash)
        if cached:
            return cached

        return await asyncio.to_thread(self._query_collection, prompt, prompt_hash)

    def _query_collection(self, prompt: str, prompt_hash: str) -> CacheHit | None:
        try:
            results = self.collection.query(
                query_texts=[prompt],
                n_results=min(settings.CACHE_TOP_K, settings.CACHE_MAX_RESULTS),
                include=["metadatas", "distances"],
            )

            if not results.get("ids") or not results["ids"][0]:
                return None

            distance = results["distances"][0][0]
            similarity = self._distance_to_similarity(distance)
            if similarity < settings.CACHE_SIMILARITY_THRESHOLD:
                return None

            metadata = results["metadatas"][0][0]
            cached_json = metadata.get("response")
            if not cached_json:
                return None

            response = json.loads(cached_json)
            hit = CacheHit(response=response, metadata=metadata, similarity=similarity)
            self._exact_cache[prompt_hash] = hit
            return hit
        except Exception as exc:  # pragma: no cover - defensive logging branch
            print(f"Cache lookup error: {exc}")
            return None

    async def save_response(
        self,
        prompt: str,
        response: dict,
        *,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        energy_joules: float,
        provider: str,
    ) -> None:
        prompt_hash = self._hash_prompt(prompt)
        metadata = {
            "response": json.dumps(response),
            "prompt_hash": prompt_hash,
            "model": model,
            "prompt_tokens": str(prompt_tokens),
            "completion_tokens": str(completion_tokens),
            "energy_joules": str(energy_joules),
            "provider": provider,
        }

        hit = CacheHit(response=response, metadata=metadata, similarity=1.0)
        self._exact_cache[prompt_hash] = hit

        await asyncio.to_thread(self._persist_entry, prompt, metadata)

    def _persist_entry(self, prompt: str, metadata: dict[str, str]) -> None:
        try:
            self.collection.add(
                documents=[prompt],
                metadatas=[metadata],
                ids=[f"{metadata['prompt_hash']}:{uuid.uuid4().hex}"],
            )
        except Exception as exc:  # pragma: no cover - defensive logging branch
            print(f"Cache save error: {exc}")


cache_service = CacheService()
