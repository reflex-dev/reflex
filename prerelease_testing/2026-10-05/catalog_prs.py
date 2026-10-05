"""Preserve linked issue/PR descriptions without changing GitHub state."""

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


def fetch(url: str) -> dict:
    """Fetch the issue record, which also contains a PR's description.

    Args:
        url: Link recorded in the release changelog.

    Returns:
        Read-only GitHub metadata or a retrieval error.
    """
    parts = urlsplit(url).path.strip("/").split("/")
    if len(parts) != 4 or parts[2] not in ("issues", "pull", "pulls"):
        return {"url": url, "status": "reference"}
    owner, repository, _, number = parts
    result = subprocess.run(
        [
            os.environ.get("QA_GH") or shutil.which("gh") or "/opt/homebrew/bin/gh",
            "api",
            f"repos/{owner}/{repository}/issues/{number}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        return {"url": url, "status": "unverified", "error": result.stderr}
    data = json.loads(result.stdout)
    return {
        "url": url,
        "status": "read",
        **{
            key: data.get(key)
            for key in ("number", "title", "body", "html_url", "state", "pull_request")
        },
    }


def main() -> None:
    """Read and save descriptions for every changelog-head link."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    links = sorted(
        {
            url
            for entry in json.loads(args.inventory.read_text())
            for url in entry["prs"]
        }
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        descriptions = list(pool.map(fetch, links))
    args.output.write_text(json.dumps(descriptions, indent=2) + "\n")
    for entry in descriptions:
        print(entry["status"], entry["url"], entry.get("title", ""))


if __name__ == "__main__":
    main()
