"""Record installed wheel origins and graph without importing the checkout."""

import argparse
import importlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path


def main() -> None:
    """Record the disposable root environment and reject source installations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    origins = {}
    for name in ("reflex", "reflex_base", "reflex_enterprise"):
        module = importlib.import_module(name)
        assert Path(module.__file__).is_relative_to(Path(sys.prefix)), module.__file__
        origins[name] = module.__file__
    graph = []
    for distribution in importlib.metadata.distributions():
        assert distribution.read_text("direct_url.json") is None, distribution.name
        graph.append({"name": distribution.name, "version": distribution.version})
    result = {
        "executable": sys.executable,
        "prefix": sys.prefix,
        "cwd": str(Path.cwd()),
        "platform": platform.platform(),
        "imports": origins,
        "graph": sorted(graph, key=lambda entry: entry["name"].lower()),
        "direct_url_installations": [],
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
