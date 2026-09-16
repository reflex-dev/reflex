"""Refresh the Reflex Cloud OpenAPI snapshot that the reflex-sdk tests check routes against."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx
from reflex_sdk._base import DEFAULT_BASE_URL

SNAPSHOT = Path(__file__).resolve().parent.parent / "packages/reflex-sdk/openapi.json"
# Where the control plane serves its schema, relative to the Reflex Cloud URL.
OPENAPI_PATH = "/api/openapi.json"


def main() -> None:
    """Download the OpenAPI schema and write it with stable formatting."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="the Reflex Cloud URL to download the schema from",
    )
    args = parser.parse_args()
    response = httpx.get(f"{args.base_url.rstrip('/')}{OPENAPI_PATH}", timeout=30)
    response.raise_for_status()
    # Pinned newlines keep a refresh on Windows from rewriting every line.
    SNAPSHOT.write_text(
        json.dumps(response.json(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
