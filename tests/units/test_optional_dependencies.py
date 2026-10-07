"""Checks on the optional dependency groups declared in pyproject.toml."""

import tomllib
from pathlib import Path

from packaging.requirements import Requirement

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _extra_requirements(extra: str) -> dict[str, Requirement]:
    """Parse the requirements of an optional dependency group.

    Args:
        extra: The name of the extra, e.g. ``"db"``.

    Returns:
        The group's requirements keyed by normalized project name.
    """
    with PYPROJECT.open("rb") as f:
        pyproject = tomllib.load(f)
    reqs = (
        Requirement(r) for r in pyproject["project"]["optional-dependencies"][extra]
    )
    return {req.name.lower(): req for req in reqs}


def test_db_extra_installs_greenlet():
    """reflex.model imports sqlalchemy.ext.asyncio, which needs greenlet at import time.

    SQLAlchemy 2.1 stopped depending on greenlet unconditionally, so the ``db`` extra
    has to carry it; otherwise a fresh ``pip install reflex[db]`` fails on import.
    """
    db = _extra_requirements("db")
    assert "greenlet" in db, "the db extra must list greenlet"
    assert db["greenlet"].marker is None, "greenlet must be installed on every platform"
