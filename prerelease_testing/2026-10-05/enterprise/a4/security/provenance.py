"""Assert the fresh published graph and isolated framework import origins."""

import hashlib
import importlib
import json
import os
import sys
from importlib import metadata
from pathlib import Path


def main() -> None:
    """Record the exact primary or prepared-baseline environment provenance."""
    label = sys.argv[1]
    assert label in {"a4", "a3"}
    prefix = (
        "/private/tmp/reflex-enterprise-a4-20261005-security"
        + ("-a3" if label == "a3" else "")
        + "-venv"
    )
    assert str(Path(sys.prefix).resolve()) == prefix
    assert os.environ.get("PYTHONPATH") is None
    assert not any(
        "/Users/masenf/.codex/worktrees/48e6/reflex" in value for value in sys.path
    )
    pins = (
        Path("requirements-input.txt").read_text().replace("0.9.7a4", "0.9.7" + label)
    )
    expected = {
        name.lower().replace("_", "-"): version
        for name, version in (
            line.split("==", 1) for line in pins.splitlines() if "==" in line
        )
    }
    distributions = []
    versions = {}
    for distribution in metadata.distributions():
        assert distribution.read_text("direct_url.json") is None
        name = distribution.metadata["Name"].lower().replace("_", "-")
        versions[name] = distribution.version
        distributions.append(
            {
                "name": name,
                "version": distribution.version,
                "requires": distribution.requires or [],
            }
        )
    assert versions == expected
    assert len(versions) == 104
    assert versions["reflex"] == versions["reflex-base"] == "0.10.0a1"
    modules = {}
    for name in (
        "reflex",
        "reflex.state",
        "reflex_base",
        "reflex_enterprise",
        "reflex_enterprise.auth.enforcement",
        "reflex_enterprise.auth.oidc.state",
        "reflex_enterprise.plugins.mcp_auth.provider",
        "playwright",
        "mcp",
        "oidc_provider_mock",
    ):
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        assert str(path).startswith(prefix + "/")
        modules[name] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    result = {
        "status": "passed",
        "label": label,
        "prefix": prefix,
        "python": sys.version,
        "cwd": str(Path.cwd()),
        "pythonpath": os.environ.get("PYTHONPATH"),
        "sys_path": sys.path,
        "modules": modules,
        "distributions": sorted(distributions, key=lambda item: item["name"]),
    }
    Path("logs/provenance-" + label + ".json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(
        json.dumps({"status": "passed", "label": label, "distributions": len(versions)})
    )


if __name__ == "__main__":
    main()
