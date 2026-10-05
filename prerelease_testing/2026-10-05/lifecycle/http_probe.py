"""Verify route status codes and compressed production assets over real HTTP."""

import argparse
import gzip
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def request(url: str, **headers: str) -> dict:
    """Fetch one real production response, including errors.

    Args:
        url: Target URL.
        **headers: Request headers.

    Returns:
        Status, headers and response bytes.
    """
    try:
        response = urllib.request.urlopen(
            urllib.request.Request(url, headers=headers), timeout=15
        )
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return {
            "url": url,
            "status": response.status,
            "headers": {key.lower(): value for key, value in response.headers.items()},
            "content": response.read(),
        }


def main() -> None:
    """Test routable SPA paths and ordinary JavaScript asset compression."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.url.rstrip("/")
    results = []
    for suffix, status in (
        ("/", 200),
        ("/articles/7", 200),
        ("/articles/7?self=1", 200),
        ("/unknown-qa-route", 404),
        ("/articles/7/extra", 404),
    ):
        result = request(root + suffix, self="qa-header")
        assert result["status"] == status, result
        results.append(result)
    html = results[0]["content"].decode()
    source = re.search(r'(?:src|href)="([^"]+\.js)"', html).group(1)
    url = urllib.parse.urljoin(root + "/", source)
    plain = request(url)
    compressed = request(url, **{"Accept-Encoding": "gzip"})
    assert plain["status"] == compressed["status"] == 200
    assert compressed["headers"].get("content-encoding") == "gzip", compressed[
        "headers"
    ]
    assert gzip.decompress(compressed["content"]) == plain["content"]
    results.extend((plain, compressed))
    for result in results:
        result["byte_count"] = len(result.pop("content"))
    args.output.write_text(
        json.dumps({"status": "passed", "responses": results}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
