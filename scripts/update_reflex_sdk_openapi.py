"""Refresh the Reflex Cloud OpenAPI snapshot that the reflex-sdk tests check routes against."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

SNAPSHOT = Path(__file__).resolve().parent.parent / "packages/reflex-sdk/openapi.json"


def main() -> None:
    """Download the OpenAPI schema and write it with stable formatting."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="https://build.reflex.dev",
        help="the Reflex Cloud URL to download the schema from",
    )
    args = parser.parse_args()
    response = httpx.get(f"{args.base_url.rstrip('/')}/api/openapi.json", timeout=30)
    response.raise_for_status()
    SNAPSHOT.write_text(json.dumps(response.json(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
