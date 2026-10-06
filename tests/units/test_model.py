import datetime
import math
import tomllib
from pathlib import Path
from unittest import mock

import pytest
from packaging.requirements import Requirement
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.event import Event

import reflex.constants
import reflex.model
from reflex.model import (
    Model,
    ModelRegistry,
    _ClassThatErrorsOnInit,
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


@pytest.mark.skipif(
    not hasattr(sqlmodel, "UTCDateTime"), reason="SQLModel before 0.0.45"
)
def test_utc_datetime_migration_and_roundtrip(
    tmp_working_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_registry: type[ModelRegistry],
):
    """Generated UTC migrations work on fresh databases and retain aware datetimes.

    Args:
        tmp_working_dir: The database and migration directory.
        monkeypatch: The configuration patch fixture.
        model_registry: The isolated model registry.
    """
    monkeypatch.setattr(
        reflex.constants, "ALEMBIC_CONFIG", str(tmp_working_dir / "alembic.ini")
    )
    config = mock.Mock(db_url=f"sqlite:///{tmp_working_dir}/reflex.db")
    monkeypatch.setattr(reflex.model, "get_config", lambda: config)
    alembic_init()

    class UTCPost(Model, table=True):
        created_at: datetime.datetime

    with get_engine().connect() as connection:
        assert alembic_autogenerate(connection=connection, message="UTC datetime")
    migration = next((tmp_working_dir / "alembic" / "versions").glob("*.py"))
    assert "sqlmodel.sql.sqltypes.UTCDateTime()" in migration.read_text()
    assert migrate()

    value = datetime.datetime(
        2026, 9, 21, 12, tzinfo=datetime.timezone(datetime.timedelta(hours=5))
    )
    with reflex.model.session() as session:
        session.add(UTCPost(created_at=value))
        session.commit()
        stored = session.exec(sqlmodel.select(UTCPost)).one()
        assert stored.created_at == value
        assert stored.created_at.utcoffset() == datetime.timedelta(0)

    get_engine().dispose()
    (tmp_working_dir / "reflex.db").unlink()
    assert migrate()
    with reflex.model.session() as session:
        assert session.exec(sqlmodel.select(UTCPost)).all() == []


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


@pytest.mark.filterwarnings(
    "ignore:This declarative base already contains a class with the same class name",
)
def test_automigration_add_column_with_callable_default(
    tmp_working_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_registry: type[ModelRegistry],
):
    """Test adding a column with a callable default to an existing table.

    A callable default (e.g. ``default_factory=datetime.now``) must be evaluated
    before it can be rendered as a SQL literal server_default for existing rows.

    Args:
        tmp_working_dir: directory where database and migrations are stored
        monkeypatch: pytest fixture to overwrite attributes
        model_registry: clean reflex ModelRegistry
    """
    import datetime

    import sqlmodel

    alembic_ini = tmp_working_dir / "alembic.ini"
    versions = tmp_working_dir / "alembic" / "versions"
    monkeypatch.setattr(reflex.constants, "ALEMBIC_CONFIG", str(alembic_ini))

    config_mock = mock.Mock()
    config_mock.db_url = f"sqlite:///{tmp_working_dir}/reflex.db"
    monkeypatch.setattr(reflex.model, "get_config", mock.Mock(return_value=config_mock))

    alembic_init()

    class AlembicCallable(Model, table=True):  # pyright: ignore [reportRedeclaration]
        t1: str

    with get_engine().connect() as connection:
        assert alembic_autogenerate(connection=connection, message="Initial Revision")
    assert migrate()

    with reflex.model.session() as session:
        session.add(AlembicCallable(t1="existing"))
        session.commit()

    model_registry.get_metadata().clear()

    # Add a non-nullable column with a callable default alongside a scalar
    # default. Rendering the migration script previously raised CompileError
    # because the callable was fed into sqlalchemy.literal(); both defaults must
    # be carried as server defaults so the existing row can be migrated.
    class AlembicCallable(Model, table=True):  # pyright: ignore [reportRedeclaration]
        t1: str
        created: datetime.datetime = sqlmodel.Field(
            default_factory=datetime.datetime.now,
            sa_type=sa.DateTime(timezone=False),
        )
        count: int = 5

    assert migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 2

    now = datetime.datetime.now()
    with reflex.model.session() as session:
        session.add(AlembicCallable(t1="foo"))
        session.commit()
        result = session.exec(sqlmodel.select(AlembicCallable)).all()
        assert len(result) == 2
        assert result[0].t1 == "existing"
        assert result[0].count == 5
        assert result[0].created < now
        assert result[1].t1 == "foo"
        assert result[1].count == 5
        assert result[1].created >= now

    model_registry.get_metadata().clear()

    # A nullable callable default is evaluated for existing rows and remains a
    # Python-side default for new rows.
    class AlembicCallable(Model, table=True):  # pyright: ignore [reportRedeclaration]
        t1: str
        created: datetime.datetime = sqlmodel.Field(
            default_factory=datetime.datetime.now,
            sa_type=sa.DateTime(timezone=False),
        )
        count: int = 5
        note: str | None = sqlmodel.Field(default_factory=lambda: "generated")

    assert migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 3

    with reflex.model.session() as session:
        session.add(AlembicCallable(t1="bar"))
        session.commit()
        result = session.exec(sqlmodel.select(AlembicCallable)).all()
        assert len(result) == 3
        # Pre-existing rows receive the evaluated server default.
        assert result[0].t1 == "existing"
        assert result[0].note == "generated"
        assert result[1].t1 == "foo"
        assert result[1].note == "generated"
        # Newly inserted row gets the callable default from sqlmodel.
        assert result[2].t1 == "bar"
        assert result[2].note == "generated"

    model_registry.get_metadata().clear()


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
