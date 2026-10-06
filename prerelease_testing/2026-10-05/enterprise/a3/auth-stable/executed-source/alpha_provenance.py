"""Verify the borrowed published alpha environment without modifying it."""

import hashlib
import importlib
import importlib.metadata as metadata
import json
import os
import sys
from pathlib import Path


def main() -> None:
    """Assert published origins and record the exact alpha dependency graph."""
    prefix = "/private/tmp/reflex-enterprise-a3-20261005-free-tier-venv"
    assert str(Path(sys.prefix).resolve()) == prefix
    assert os.environ.get("PYTHONPATH") is None
    assert not any("/Users/masenf/.codex/worktrees/48e6/reflex" in path for path in sys.path)
    expected = {"reflex": "0.10.0a1", "reflex-base": "0.10.0a1", "reflex-enterprise": "0.9.7a3"}
    for name, version in expected.items():
        assert metadata.version(name) == version
    modules = {}
    for name in ("reflex", "reflex.state", "reflex_base", "reflex_enterprise", "reflex_enterprise.auth.enforcement"):
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        assert str(path).startswith(prefix + "/")
        modules[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    distributions = []
    for distribution in metadata.distributions():
        assert distribution.read_text("direct_url.json") is None, distribution.metadata["Name"]
        distributions.append({"name": distribution.metadata["Name"], "version": distribution.version, "requires": distribution.requires or []})
    result = {"status": "passed", "prefix": prefix, "python": sys.version, "cwd": str(Path.cwd()), "pythonpath": os.environ.get("PYTHONPATH"), "sys_path": sys.path, "modules": modules, "distributions": sorted(distributions, key=lambda item: item["name"].lower())}
    Path("logs/alpha-provenance.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": "passed", "distributions": len(distributions), "versions": expected}))


if __name__ == "__main__":
    main()
