"""Check that previously tested core/tooling alpha artifacts remain unchanged."""

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    """Compare original alpha metadata to live PyPI filenames and hashes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = []
    for item in json.loads(args.inventory.read_text()):
        if not item.get("alpha") or item["package"] == "reflex-enterprise":
            continue
        url = f"https://pypi.org/pypi/{item['package']}/{item['version']}/json"
        with urllib.request.urlopen(url, timeout=30) as response:
            current = json.load(response)
        prior = {file["filename"]: file["sha256"] for file in item["files"]}
        now = {file["filename"]: file["digests"]["sha256"] for file in current["urls"]}
        results.append(
            {
                "package": item["package"],
                "version": item["version"],
                "pypi_url": url,
                "artifacts_unchanged": prior == now,
                "any_yanked": any(file["yanked"] for file in current["urls"]),
                "files": now,
            }
        )
    summary = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "unchanged original core/tooling alpha artifacts; enterprise a4 audited separately",
        "packages": results,
        "passed": bool(results)
        and all(
            item["artifacts_unchanged"] and not item["any_yanked"] for item in results
        ),
    }
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"passed": summary["passed"], "package_count": len(results)}))
    raise SystemExit(not summary["passed"])


if __name__ == "__main__":
    main()
