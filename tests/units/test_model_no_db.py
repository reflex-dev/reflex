import subprocess
import sys
import textwrap

import pytest

from reflex.model import _ClassThatErrorsOnInit


def test_subclassing_without_db_extra_points_to_install():
    """Declaring a table model without sqlmodel installed must name the fix, not raise a bare TypeError."""
    with pytest.raises(ImportError, match=r"reflex\[db\]"):

        class Item(_ClassThatErrorsOnInit, table=True):  # pyright: ignore[reportUnusedClass]
            name: str


def test_plain_subclassing_without_db_extra_points_to_install():
    with pytest.raises(ImportError, match=r"reflex\[db\]"):

        class Item(_ClassThatErrorsOnInit):  # pyright: ignore[reportUnusedClass]
            name: str


def test_public_model_without_db_extra_points_to_install():
    """Declare a table model through the public `rx.Model` with the db packages hidden.

    Runs in a subprocess so `reflex.model` is imported fresh with sqlalchemy,
    sqlmodel and alembic unavailable, which selects the placeholder class.
    """
    script = textwrap.dedent(
        """
        import importlib.util
        import sys
        from importlib.abc import MetaPathFinder

        BLOCKED = ("sqlalchemy", "sqlmodel", "alembic")
        real_find_spec = importlib.util.find_spec

        def find_spec(name, package=None):
            if name.split(".")[0] in BLOCKED:
                return None
            return real_find_spec(name, package)

        class Blocker(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] in BLOCKED:
                    raise ModuleNotFoundError(f"No module named {fullname!r}")
                return None

        importlib.util.find_spec = find_spec
        sys.meta_path.insert(0, Blocker())
        import reflex as rx

        try:
            class Item(rx.Model, table=True):
                name: str
        except ImportError as error:
            print(error)
        else:
            print("no error")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )

    assert "reflex[db]" in result.stdout
