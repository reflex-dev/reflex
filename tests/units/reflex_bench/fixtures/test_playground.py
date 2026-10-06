"""The playground's seed data is the same on every machine and every run, and any worker can seed it."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from reflex_bench.fixtures import playground_dir

SEED_DIGEST = "sha256:d194fce71a52b5c9d9282c2d5d44e6a8bc91676f24f44a1479e98fe17b17d700"
# Runs in a fresh interpreter, which reads the database URL from the rxconfig.py
# in its working directory and registers the playground's table only there.
RACED_SEED = """
import sys

import sqlalchemy
from sqlalchemy.dialects.sqlite.base import SQLiteDialect

sys.path.append(PLAYGROUND)
from playground.models import Product, seed_database

engine = sqlalchemy.create_engine("sqlite:///race.db")
# Another worker creates the table after this one found it missing.
Product.__table__.create(engine)
SQLiteDialect.has_table = lambda *args, **kwargs: False
seed_database()
with engine.connect() as connection:
    print(connection.exec_driver_sql("SELECT COUNT(*) FROM product").scalar())
"""


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


def test_seed_database_starts_when_another_worker_created_the_table(tmp_path: Path):
    """Seeding survives the table appearing between its existence check and its creation.

    Every backend worker seeds at start, so on a new database a second worker can
    find the table missing and then lose the race to create it.

    Args:
        tmp_path: The working directory of the seeding process.
    """
    pytest.importorskip("sqlmodel")
    (tmp_path / "rxconfig.py").write_text(
        "import reflex as rx\n\n"
        'config = rx.Config(app_name="playground", db_url="sqlite:///race.db")\n'
    )
    script = RACED_SEED.replace("PLAYGROUND", repr(str(playground_dir())))
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.split()[-1] == str(_seed_module().PRODUCT_COUNT)
