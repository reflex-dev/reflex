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
