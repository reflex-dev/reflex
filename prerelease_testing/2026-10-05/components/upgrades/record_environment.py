"""Record an isolated app's exact installed graph and source provenance."""

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

import reflex
import reflex_base


def main() -> None:
    """Write versions, import paths and source/lock hashes for one test phase."""
    root = Path.cwd()
    records = []
    for dist in sorted(
        importlib.metadata.distributions(),
        key=lambda item: item.metadata["Name"].lower(),
    ):
        assert dist.read_text("direct_url.json") is None, dist.metadata["Name"]
        records.append({"name": dist.metadata["Name"], "version": dist.version})
    paths = {"reflex": str(reflex.__file__), "reflex_base": str(reflex_base.__file__)}
    for path in paths.values():
        assert "/private/tmp/" in path
        assert "/site-packages/" in path
    hashes = {}
    for pattern in ["**/*.py", "reflex.lock/*", ".web/package.json", ".web/bun.lock"]:
        for path in root.glob(pattern):
            if ".web" in path.parts and path.name.endswith(".py"):
                continue
            if path.is_file():
                hashes[str(path.relative_to(root))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    Path(sys.argv[1]).write_text(
        json.dumps(
            {
                "cwd": str(root),
                "executable": sys.executable,
                "imports": paths,
                "graph": records,
                "hashes": hashes,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
