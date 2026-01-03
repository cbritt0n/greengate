#!/usr/bin/env python3
"""Quick smoke test against a running GreenGate deployment."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

import httpx


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send a sample chat completion request to GreenGate"
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("GREENGATE_BASE_URL", "http://localhost:8000"),
        help="Gateway base URL (default: %(default)s)",
    )
    parser.add_argument("--model", default="gpt-4o-mini", help="Model identifier to request")
    parser.add_argument("--prompt", default="Give me one sustainability tip.", help="User prompt")
    parser.add_argument("--stream", action="store_true", help="Use streaming responses")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    return parser


async def run_smoke(args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": "You are GreenGate's diagnostic assistant."},
            {"role": "user", "content": args.prompt},
        ],
        "stream": args.stream,
    }
    url = args.base_url.rstrip("/") + "/v1/chat/completions"
    async with httpx.AsyncClient(timeout=args.timeout) as client:
        if args.stream:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                print("--- stream start ---")
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        print(chunk.strip())
                print("--- stream end ---")
                _print_headers(response)
        else:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            print(json.dumps(response.json(), indent=2))
            _print_headers(response)
    return 0


def _print_headers(response: httpx.Response) -> None:
    interesting = {
        "X-GreenGate-Status": response.headers.get("X-GreenGate-Status"),
        "X-GreenGate-Provider": response.headers.get("X-GreenGate-Provider"),
        "X-GreenGate-Energy-Joules": response.headers.get("X-GreenGate-Energy-Joules"),
    }
    print("Headers:")
    for key, value in interesting.items():
        if value is not None:
            print(f"  {key}: {value}")


async def _async_main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return await run_smoke(args)
    except httpx.HTTPError as exc:  # pragma: no cover - convenience
        print(f"Request failed: {exc}")
        return 1


if __name__ == "__main__":  # pragma: no cover - manual tool
    raise SystemExit(asyncio.run(_async_main()))
