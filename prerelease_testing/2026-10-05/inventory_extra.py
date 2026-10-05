"""Audit an additional published alpha cut without changing the install pins."""

import argparse
import json
from pathlib import Path

from inventory import audit_package


def main() -> None:
    """Check an alpha superseded by another release in the same batch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_package(
        {
            "package": args.package,
            "version": args.version,
            "alpha": True,
            "scope": "superseded alpha in the same batch",
        }
    )
    assert result["status"] == "published", result
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
