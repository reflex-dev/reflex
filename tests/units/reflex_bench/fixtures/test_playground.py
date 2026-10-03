"""The playground's seed data is the same on every machine and every run."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from types import ModuleType

from reflex_bench.fixtures import playground_dir

SEED_DIGEST = "sha256:d194fce71a52b5c9d9282c2d5d44e6a8bc91676f24f44a1479e98fe17b17d700"


def _seed_module() -> ModuleType:
    """Load the playground's seed module by path; it imports only the stdlib.

    Returns:
        The module.
    """
    path = playground_dir() / "playground" / "seed.py"
    spec = importlib.util.spec_from_file_location("playground_seed", path)
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
    seed = _seed_module()
    first, second = seed.product_rows(), seed.product_rows()
    assert first == second
    assert len(first) == seed.PRODUCT_COUNT
    assert 1000 <= seed.PRODUCT_COUNT <= 5000
    assert [row["id"] for row in first] == list(range(1, seed.PRODUCT_COUNT + 1))
    assert _digest(first) == SEED_DIGEST


def test_seed_module_imports_only_the_stdlib():
    source = (playground_dir() / "playground" / "seed.py").read_text(encoding="utf-8")
    imports = {
        line.split()[1].split(".")[0]
        for line in source.splitlines()
        if line.startswith(("import ", "from "))
    }
    assert imports == {"random"}
