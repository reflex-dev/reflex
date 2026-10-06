"""Verify the published a3/stable graph and isolated import origins."""

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path


def main() -> None:
    """Record provenance and enforce the requested dependency contrast."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    prefix = "/private/tmp/reflex-enterprise-a3-20261005-stable"
    assert str(Path(sys.prefix).resolve()) == prefix
    assert os.environ.get("PYTHONPATH") is None
    assert not any("/Users/masenf/.codex/worktrees/48e6/reflex" in path for path in sys.path)
    modules = {}
    for name in ("reflex", "reflex.state", "reflex_base", "reflex_enterprise", "reflex_enterprise.auth.decorators", "reflex_enterprise.auth.oidc.state", "playwright", "oidc_provider_mock", "pytest"):
        module = importlib.import_module(name)
        source = Path(module.__file__).resolve()
        assert str(source).startswith(prefix + "/"), (name, source)
        modules[name] = {"source": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    distributions = []
    versions = {}
    for distribution in importlib.metadata.distributions():
        assert distribution.read_text("direct_url.json") is None, distribution.metadata["Name"]
        name = distribution.metadata["Name"].lower().replace("_", "-")
        versions[name] = distribution.version
        distributions.append({"name": name, "version": distribution.version, "requires": distribution.requires or []})
    baseline = dict(line.split("==", 1) for line in args.baseline.read_text().splitlines() if "==" in line)
    assert baseline["reflex-enterprise"] == "0.9.7a2"
    changes = {}
    for name, version in baseline.items():
        expected = "0.9.7a3" if name == "reflex-enterprise" else version
        assert versions[name] == expected, (name, versions[name], expected)
        if version != expected:
            changes[name] = {"old": version, "new": expected}
    assert versions["reflex"] == versions["reflex-base"] == "0.9.12"
    assert versions["pytest"] == "8.4.2"
    additions = {name: version for name, version in versions.items() if name not in baseline}
    assert set(additions) == {"pytest", "pluggy", "iniconfig"}, additions
    result = {"status": "passed", "executable": sys.executable, "python": sys.version, "cwd": str(Path.cwd()), "sys_path": sys.path, "pythonpath": os.environ.get("PYTHONPATH"), "modules": modules, "changes_from_retained_stable_graph": changes, "permitted_test_additions": additions, "distributions": sorted(distributions, key=lambda value: value["name"])}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": "passed", "distributions": len(distributions), "changes": changes, "test_additions": additions}))


if __name__ == "__main__":
    main()
