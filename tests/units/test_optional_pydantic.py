"""Verify reflex imports and works when pydantic is not installed."""

import subprocess
import sys

# Runs in a subprocess with pydantic (and the db extras that require it)
# blocked, mirroring the "without db dependencies" CI job.
_SCRIPT = """
import sys

BLOCKED = ("pydantic", "sqlmodel", "alembic", "sqlalchemy")


class _Filter:
    # Hide blocked packages from every finder so both ``import`` and
    # ``find_spec`` see them as absent.
    def __init__(self, inner):
        self.inner = inner

    def find_spec(self, name, path=None, target=None):
        if name.partition(".")[0] in BLOCKED:
            return None
        finder = getattr(self.inner, "find_spec", None)
        return finder(name, path, target) if finder is not None else None


sys.meta_path = [_Filter(f) for f in sys.meta_path]

from importlib.util import find_spec

assert find_spec("pydantic") is None

import datetime

import reflex as rx
from reflex_base.utils import serializers


class S(rx.State):
    val: rx.Field[str] = rx.field("hello")


comp = rx.text(S.val)
assert "val" in str(comp.render())

assert serializers.serialize(datetime.datetime(2026, 1, 2, 3, 4, 5)) == "2026-01-02 03:04:05"
assert not any(
    getattr(cls, "__module__", "").startswith("pydantic")
    for cls in serializers.SERIALIZERS
)

print("OK")
"""


def test_reflex_works_without_pydantic() -> None:
    """Core import, state, component render, and serializers work without pydantic."""
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, (
        f"reflex failed without pydantic:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "OK" in result.stdout
