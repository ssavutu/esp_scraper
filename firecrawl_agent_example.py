#!/usr/bin/env python3
"""Simple Firecrawl /v1/agent caller.

Usage:
  python firecrawl_agent_example.py --prompt "Find the tuition page and summarize key fees."

Env vars:
  FIRECRAWL_BASE_URL   Default: http://localhost:3002
  FIRECRAWL_API_KEY    Optional for self-hosted; used if provided
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

import requests


def build_payload(prompt: str, url: str | None, max_steps: int | None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"prompt": prompt}
    if url:
        payload["url"] = url
    if max_steps is not None:
        payload["maxSteps"] = max_steps
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Call Firecrawl /v1/agent")
    parser.add_argument("--prompt", required=True, help="Agent instruction prompt")
    parser.add_argument("--url", help="Optional starting URL for the agent")
    parser.add_argument("--max-steps", type=int, help="Optional maximum agent steps")
    parser.add_argument(
        "--base-url",
        default=os.getenv("FIRECRAWL_BASE_URL", "http://localhost:3002"),
        help="Firecrawl API base URL",
    )
    args = parser.parse_args()

    endpoint = f"{args.base_url.rstrip('/')}/v1/agent"
    headers = {"Content-Type": "application/json"}

    api_key = os.getenv("FIRECRAWL_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = build_payload(args.prompt, args.url, args.max_steps)

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=300)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    try:
        data = response.json()
    except ValueError:
        print(response.text)
        return 0

    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
