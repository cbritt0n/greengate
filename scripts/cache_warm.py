#!/usr/bin/env python3
"""Warm the semantic cache by replaying prompts against a running GreenGate instance."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import httpx


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Warm GreenGate semantic cache")
    parser.add_argument(
        "--base-url",
        default=os.getenv("GREENGATE_BASE_URL", "http://localhost:8000"),
        help="Gateway base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("GREENGATE_MODEL", "gpt-4o-mini"),
        help="Model identifier to request",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Text file with one prompt per line",
    )
    parser.add_argument(
        "--prompt",
        default=os.getenv("GREENGATE_PROMPT"),
        help="Single prompt to warm (if --file is not provided)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("GREENGATE_WARM_CONCURRENCY", "4")),
        help="Concurrent requests",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("GREENGATE_TIMEOUT", "30")),
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("GREENGATE_API_KEY"),
        help="Gateway API key (sent as Authorization: Bearer <key>)",
    )
    return parser


def _load_prompts(args: argparse.Namespace) -> list[str]:
    if args.file:
        lines = args.file.read_text(encoding="utf-8").splitlines()
        return [line.strip() for line in lines if line.strip()]
    if args.prompt:
        return [str(args.prompt).strip()]
    raise SystemExit("Provide --file or --prompt (or set GREENGATE_PROMPT)")


async def _warm_one(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    model: str,
    prompt: str,
) -> None:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Warm the cache."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    response = await client.post(url, json=payload, headers=headers)
    response.raise_for_status()


async def main() -> int:
    args = build_parser().parse_args()
    prompts = _load_prompts(args)
    url = args.base_url.rstrip("/") + "/v1/chat/completions"

    headers: dict[str, str] = {}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"

    semaphore = asyncio.Semaphore(max(args.concurrency, 1))

    async with httpx.AsyncClient(timeout=args.timeout) as client:
        async def run(prompt: str) -> None:
            async with semaphore:
                await _warm_one(client, url, headers, args.model, prompt)

        await asyncio.gather(*(run(prompt) for prompt in prompts))

    print(f"Warmed {len(prompts)} prompts against {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
