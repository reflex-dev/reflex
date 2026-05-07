import math
from pathlib import Path
from unittest import mock

import pytest
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.event import Event

import reflex.constants
import reflex.model
from reflex.model import (
    Model,
    ModelRegistry,
    alembic_autogenerate,
    alembic_init,
    get_engine,
    migrate,
)
from reflex.state import BaseState, State
from tests.units.test_state import (
    mock_app_simple,  # noqa: F401 # for pytest.mark.usefixtures
)

pytest.importorskip("alembic")
pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")


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


@pytest.mark.filterwarnings(
    "ignore:This declarative base already contains a class with the same class name",
)
def test_automigration(
    tmp_working_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_registry: type[ModelRegistry],
):
    """Test alembic automigration with add and drop table and column.

    Args:
        tmp_working_dir: directory where database and migrations are stored
        monkeypatch: pytest fixture to overwrite attributes
        model_registry: clean reflex ModelRegistry
    """
    import sqlalchemy.exc
    import sqlmodel

    alembic_ini = tmp_working_dir / "alembic.ini"
    versions = tmp_working_dir / "alembic" / "versions"
    monkeypatch.setattr(reflex.constants, "ALEMBIC_CONFIG", str(alembic_ini))

    config_mock = mock.Mock()
    config_mock.db_url = f"sqlite:///{tmp_working_dir}/reflex.db"
    monkeypatch.setattr(reflex.model, "get_config", mock.Mock(return_value=config_mock))

    alembic_init()
    assert alembic_ini.exists()
    assert versions.exists()

    # initial table
    class AlembicThing(Model, table=True):  # pyright: ignore [reportRedeclaration]
        t1: str

    with get_engine().connect() as connection:
        assert alembic_autogenerate(connection=connection, message="Initial Revision")
    assert migrate()
    version_scripts = list(versions.glob("*.py"))
    assert len(version_scripts) == 1
    assert version_scripts[0].name.endswith("initial_revision.py")

    with reflex.model.session() as session:
        session.add(AlembicThing(id=None, t1="foo"))
        session.commit()

    model_registry.get_metadata().clear()

    # Create column t2, mark t1 as optional with default
    class AlembicThing(Model, table=True):  # pyright: ignore [reportRedeclaration]
        t1: str | None = "default"
        t2: str = "bar"

    assert migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 2

    with reflex.model.session() as session:
        session.add(AlembicThing(t2="baz"))
        session.commit()
        result = session.exec(sqlmodel.select(AlembicThing)).all()
        assert len(result) == 2
        assert result[0].t1 == "foo"
        assert result[0].t2 == "bar"
        assert result[1].t1 == "default"
        assert result[1].t2 == "baz"

    model_registry.get_metadata().clear()

    # Drop column t1
    class AlembicThing(Model, table=True):  # pyright: ignore [reportRedeclaration]
        t2: str = "bar"

    assert migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 3

    with reflex.model.session() as session:
        result = session.exec(sqlmodel.select(AlembicThing)).all()
        assert len(result) == 2
        assert result[0].t2 == "bar"
        assert result[1].t2 == "baz"

    # Add table
    class AlembicSecond(Model, table=True):
        a: int = 42
        b: float = 4.2

    assert migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 4

    with reflex.model.session() as session:
        session.add(AlembicSecond(id=None))
        session.commit()
        result = session.exec(sqlmodel.select(AlembicSecond)).all()
        assert len(result) == 1
        assert result[0].a == 42
        assert math.isclose(result[0].b, 4.2)

    # No-op
    assert migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 4

    # drop table (AlembicSecond)
    model_registry.get_metadata().clear()

    class AlembicThing(Model, table=True):  # pyright: ignore [reportRedeclaration]
        t2: str = "bar"

    assert migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 5

    with reflex.model.session() as session:
        with pytest.raises(sqlalchemy.exc.OperationalError) as errctx:
            session.exec(sqlmodel.select(AlembicSecond)).all()
        assert errctx.match(r"no such table: alembicsecond")
        # first table should still exist
        result = session.exec(sqlmodel.select(AlembicThing)).all()
        assert len(result) == 2
        assert result[0].t2 == "bar"
        assert result[1].t2 == "baz"

    model_registry.get_metadata().clear()

    class AlembicThing(Model, table=True):
        # changing column type not supported by default
        t2: int = 42

    assert migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 5

    # clear all metadata to avoid influencing subsequent tests
    model_registry.get_metadata().clear()

    # drop remaining tables
    assert migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 6


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
