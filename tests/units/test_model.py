import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.event import Event

from reflex.model import Model, _ClassThatErrorsOnInit
from reflex.state import BaseState, State
from tests.units.test_state import (
    mock_app_simple,  # noqa: F401 # for pytest.mark.usefixtures
)

pytest.importorskip("alembic")
sa = pytest.importorskip("sqlalchemy")
sqlmodel = pytest.importorskip("sqlmodel")


@pytest.mark.parametrize("version", ["0.0.45", "0.0.47"])
def test_db_extra_accepts_utc_sqlmodel(version: str):
    """The database extra must accept versions used to generate UTC migrations.

    Args:
        version: A SQLModel version supporting UTCDateTime.
    """
    project = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text())
    requirement = next(
        parsed
        for dep in project["project"]["optional-dependencies"]["db"]
        if (parsed := Requirement(dep)).name == "sqlmodel"
    )
    assert requirement.specifier.contains(version)


@pytest.fixture
def model_default_primary() -> Model:
    """Returns a model object with no defined primary key.

    Returns:
        Model: Model object.
    """

    class ChildModel(Model):
        name: str

    return ChildModel(name="name")


@pytest.fixture
def model_custom_primary() -> Model:
    """Returns a model object with a custom primary key.

    Returns:
        Model: Model object.
    """
    import sqlmodel

    class ChildModel(Model):
        custom_id: int | None = sqlmodel.Field(default=None, primary_key=True)
        name: str

    return ChildModel(name="name")


def test_default_primary_key(model_default_primary: Model):
    """Test that if no primary key is defined, an "id" field is added.

    Args:
        model_default_primary: Fixture.
    """
    assert "id" in type(model_default_primary).model_fields


def test_custom_primary_key(model_custom_primary: Model):
    """Test that if a primary key is defined it is not overridden.

    Args:
        model_custom_primary: Fixture.
    """
    assert "id" in type(model_custom_primary).model_fields


class ReflexModel(Model):
    """A model for testing."""

    foo: str


class UpcastStateWithSqlAlchemy(BaseState):
    """A state for testing upcasting."""

    passed: bool = False

    def rx_model(self, m: ReflexModel):  # noqa: D102
        assert isinstance(m, ReflexModel)
        self.passed = True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "payload"),
    [
        (UpcastStateWithSqlAlchemy.rx_model, {"m": {"foo": "bar"}}),
    ],
)
async def test_upcast_event_handler_arg(
    handler, payload, mock_base_state_event_processor, emitted_deltas
):
    """Test that upcast event handler args work correctly.

    Args:
        handler: The handler to test.
        payload: The payload to test.
        mock_base_state_event_processor: Fixture for processing events with a BaseState.
        emitted_deltas: List to store emitted deltas.
    """
    async with mock_base_state_event_processor as processor:
        await processor.enqueue(
            "test_token", Event.from_event_type(handler(**payload))[0]
        )
    assert emitted_deltas == [
        (
            "test_token",
            {
                UpcastStateWithSqlAlchemy.get_full_name(): {
                    "passed" + FIELD_MARKER: True
                }
            },
        ),
    ]


def test_no_rebind_mutable_proxy_for_instrumented_functions():
    """Test that we don't rebind mutable proxies for instrumented functions."""
    import sqlalchemy
    import sqlalchemy.orm

    class SABase(sqlalchemy.orm.MappedAsDataclass, sqlalchemy.orm.DeclarativeBase):
        pass

    class SAKeyword(SABase):
        __tablename__ = "sa_keyword"

        id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
            primary_key=True, init=False, default=None
        )
        value: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(default="")
        obj_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
            sqlalchemy.ForeignKey("sa_obj.id"), default=None
        )

    class SAObj(SABase):
        __tablename__ = "sa_obj"

        id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
            primary_key=True, init=False, default=None
        )
        keywords: sqlalchemy.orm.Mapped[list[SAKeyword]] = sqlalchemy.orm.relationship(
            lazy="selectin",  # codespell:ignore
            cascade="all, delete",
            default_factory=list,
        )

    class SAState(State):
        sa_obj: SAObj = SAObj()

    sa_state = SAState()
    assert "sa_obj" not in sa_state.dirty_vars
    sa_state.sa_obj.keywords.append(SAKeyword(value="test"))
    assert "sa_obj" in sa_state.dirty_vars


@pytest.mark.parametrize("class_kwargs", [{}, {"table": True}])
def test_subclass_without_db_extra_points_to_install(class_kwargs: dict):
    """Subclassing the placeholder Model raises the guided db extra ImportError.

    Args:
        class_kwargs: Class keywords passed to the subclass declaration.
    """
    with pytest.raises(ImportError, match=r"reflex\[db\]"):

        class Item(_ClassThatErrorsOnInit, **class_kwargs):  # pyright: ignore[reportUnusedClass]
            name: str


_NO_GREENLET_SCRIPT = """
import sys

GREENLET_MSG = "The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed."


class _NoGreenlet:
    def find_spec(self, name, path=None, target=None):
        if name == "greenlet" or name.startswith("sqlalchemy.ext.asyncio"):
            raise ImportError(GREENLET_MSG)
        return None


sys.meta_path.insert(0, _NoGreenlet())
for mod in [
    m for m in sys.modules if m == "greenlet" or m.startswith("sqlalchemy.ext.asyncio")
]:
    del sys.modules[mod]

import sqlalchemy.orm
import sqlmodel

import reflex as rx
import reflex.model


class Base(sqlalchemy.orm.DeclarativeBase):
    pass


rx.ModelRegistry.register(Base)


class Item(rx.Model, table=True):
    name: str


with rx.session("sqlite:///reflex.db") as session:
    rx.Model.metadata.create_all(session.get_bind())
    session.add(Item(name="widget"))
    session.commit()
    assert session.exec(sqlmodel.select(Item.name)).all() == ["widget"]

try:
    rx.asession("sqlite+aiosqlite:///reflex.db")
except ImportError as err:
    assert "greenlet" in str(err), err
else:
    raise AssertionError("asession should require greenlet")

print("OK")
"""


def test_sync_db_api_without_greenlet(tmp_path: Path):
    """The sync database API works when sqlalchemy.ext.asyncio cannot be imported.

    SQLAlchemy 2.1 only installs greenlet with the ``asyncio`` extra, and without it
    ``import sqlalchemy.ext.asyncio`` raises ImportError. Only the async helpers
    should need it.

    Args:
        tmp_path: Working directory for the subprocess.
    """
    result = subprocess.run(
        [sys.executable, "-c", _NO_GREENLET_SCRIPT],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("OK")
