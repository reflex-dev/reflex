"""Record wheel provenance without importing anything from the checkout."""

import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path


def main() -> None:
    """Verify isolated imports and write the exact installed package graph."""
    checkout = "/Users/masenf/.codex/worktrees/48e6/reflex"
    prefix = "/private/tmp/reflex-alpha-core-state/venv"
    modules = {}
    for name in (
        "reflex",
        "reflex.state",
        "reflex.experimental.client_state",
        "reflex_base",
        "reflex_base.vars.base",
        "reflex_base.components.memo",
    ):
        module = importlib.import_module(name)
        source = str(Path(module.__file__).resolve())
        assert source.startswith(prefix), (name, source)
        modules[name] = {
            "source": source,
            "sha256": hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        }
    assert os.environ.get("PYTHONPATH") is None
    assert not any(checkout in value for value in sys.path)
    distributions = []
    for dist in importlib.metadata.distributions():
        direct_url = dist.read_text("direct_url.json")
        assert direct_url is None, (dist.metadata["Name"], direct_url)
        distributions.append({
            "name": dist.metadata["Name"],
            "version": dist.version,
            "requires": dist.requires or [],
            "installer": dist.read_text("INSTALLER"),
        })
    assert importlib.metadata.version("reflex") == "0.10.0a1"
    assert importlib.metadata.version("reflex-base") == "0.10.0a1"
    result = {
        "executable": sys.executable,
        "python": sys.version,
        "cwd": str(Path.cwd()),
        "sys_path": sys.path,
        "pythonpath": os.environ.get("PYTHONPATH"),
        "modules": modules,
        "distributions": sorted(distributions, key=lambda value: value["name"].lower()),
    }
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps({
            "verified_modules": len(modules),
            "distributions": len(distributions),
            "executable": sys.executable,
        })
    )


if __name__ == "__main__":
    main()
