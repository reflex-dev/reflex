"""The playground's seed data is the same on every machine and every run."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

from reflex_bench.fixtures import playground_dir

SEED_DIGEST = "sha256:d194fce71a52b5c9d9282c2d5d44e6a8bc91676f24f44a1479e98fe17b17d700"


def _load(path: Path, name: str) -> ModuleType:
    """Load a module of the playground by path.

    Args:
        path: The module's file.
        name: The name to load it under.

    Returns:
        The module.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _digest(rows: list[dict[str, object]]) -> str:
    """Hash seed rows.

    Args:
        rows: The rows.

    Returns:
        ``sha256:<hex>`` of their canonical JSON.
    """
    data = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def test_seed_rows_are_deterministic():
    seed = _load(playground_dir() / "playground" / "seed.py", "playground_seed")
    first, second = seed.product_rows(), seed.product_rows()
    assert first == second
    assert len(first) == seed.PRODUCT_COUNT
    assert 1000 <= seed.PRODUCT_COUNT <= 5000
    assert [row["id"] for row in first] == list(range(1, seed.PRODUCT_COUNT + 1))
    assert _digest(first) == SEED_DIGEST


def test_seed_module_imports_only_the_stdlib():
    source = (playground_dir() / "playground" / "seed.py").read_text(encoding="utf-8")
    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert imports == {"random"}


def test_database_lives_next_to_rxconfig():
    rxconfig = _load(playground_dir() / "rxconfig.py", "playground_rxconfig")
    path = rxconfig.config.db_url.removeprefix("sqlite:///")
    assert Path(path) == playground_dir().resolve() / "playground.db"
