from pathlib import Path
from unittest import mock

import pytest

import reflex.constants
import reflex.model
from reflex.model import Model, ModelRegistry, sqla_session
from reflex.state import MutableProxy
from reflex.utils.serializers import serializer

pytest.importorskip("sqlalchemy")
pytest.importorskip("sqlmodel")
pytest.importorskip("alembic")
pytest.importorskip("pydantic")

# Import SQLAlchemy classes for mutable tests
from sqlalchemy import ARRAY, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tests.units.states.mutation import MutableTestState


class MutableSQLABase(DeclarativeBase):
    """SQLAlchemy base model for mutable vars."""


class MutableSQLAModel(MutableSQLABase):
    """SQLAlchemy model for mutable vars."""

    __tablename__: str = "mutable_test_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strlist: Mapped[list[str]] = mapped_column(ARRAY(String))
    hashmap: Mapped[dict[str, str]] = mapped_column(JSON)
    test_set: Mapped[set[str]] = mapped_column(ARRAY(String))


@serializer
def serialize_mutable_sqla_model(
    model: MutableSQLAModel,
) -> dict[str, list[str] | dict[str, str]]:
    """Serialize the MutableSQLAModel.

    Args:
        model: The MutableSQLAModel instance to serialize.

    Returns:
        The serialized model.
    """
    return {"strlist": model.strlist, "hashmap": model.hashmap}


class MutableTestStateWithSQLAlchemy(MutableTestState):
    """A test state."""

    sqla_model: MutableSQLAModel = MutableSQLAModel(
        strlist=["a", "b", "c"],
        hashmap={"key": "value"},
        test_set={"one", "two", "three"},
    )

    def reassign_mutables(self):
        """Assign mutable fields to different values."""
        super().reassign_mutables()
        self.sqla_model = MutableSQLAModel(
            strlist=["d", "e", "f"],
            hashmap={"key": "value"},
            test_set={"one", "two", "three"},
        )


@pytest.fixture
def mutable_state() -> MutableTestStateWithSQLAlchemy:
    """Create a Test state containing mutable types.

    Returns:
        A state object.
    """
    return MutableTestStateWithSQLAlchemy()


def test_setattr_of_mutable_types(mutable_state: MutableTestStateWithSQLAlchemy):
    """Test that mutable types are converted to corresponding Reflex wrappers.

    Args:
        mutable_state: A test state.
    """
    sqla_model = mutable_state.sqla_model

    assert isinstance(sqla_model, MutableProxy)
    assert isinstance(sqla_model, MutableSQLAModel)
    assert isinstance(sqla_model.strlist, MutableProxy)
    assert isinstance(sqla_model.strlist, list)
    assert isinstance(sqla_model.hashmap, MutableProxy)
    assert isinstance(sqla_model.hashmap, dict)
    assert isinstance(sqla_model.test_set, MutableProxy)
    assert isinstance(sqla_model.test_set, set)

    mutable_state.reassign_mutables()

    sqla_model = mutable_state.sqla_model

    assert isinstance(sqla_model, MutableProxy)
    assert isinstance(sqla_model, MutableSQLAModel)
    assert isinstance(sqla_model.strlist, MutableProxy)
    assert isinstance(sqla_model.strlist, list)
    assert isinstance(sqla_model.hashmap, MutableProxy)
    assert isinstance(sqla_model.hashmap, dict)
    assert isinstance(sqla_model.test_set, MutableProxy)
    assert isinstance(sqla_model.test_set, set)


def test_mutable_sqla_model(mutable_state: MutableTestStateWithSQLAlchemy):
    """Test that mutable SQLA models are tracked correctly.

    Args:
        mutable_state: A test state.
    """
    assert not mutable_state.dirty_vars

    def assert_sqla_model_dirty():
        assert mutable_state.dirty_vars == {"sqla_model"}
        mutable_state._clean()
        assert not mutable_state.dirty_vars

    mutable_state.sqla_model.strlist.append("foo")
    assert_sqla_model_dirty()
    mutable_state.sqla_model.hashmap["key"] = "value"
    assert_sqla_model_dirty()
    mutable_state.sqla_model.test_set.add("bar")
    assert_sqla_model_dirty()


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
    from sqlalchemy import select
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import (
        DeclarativeBase,
        Mapped,
        MappedAsDataclass,
        declared_attr,
        mapped_column,
    )

    alembic_ini = tmp_working_dir / "alembic.ini"
    versions = tmp_working_dir / "alembic" / "versions"
    monkeypatch.setattr(reflex.constants, "ALEMBIC_CONFIG", str(alembic_ini))

    config_mock = mock.Mock()
    config_mock.db_url = f"sqlite:///{tmp_working_dir}/reflex.db"
    monkeypatch.setattr(reflex.model, "get_config", mock.Mock(return_value=config_mock))

    assert alembic_ini.exists() is False
    assert versions.exists() is False
    Model.alembic_init()
    assert alembic_ini.exists()
    assert versions.exists()

    class Base(DeclarativeBase):
        @declared_attr.directive
        def __tablename__(cls) -> str:
            return cls.__name__.lower()

    assert model_registry.register(Base)

    class ModelBase(Base, MappedAsDataclass):
        __abstract__ = True
        id: Mapped[int | None] = mapped_column(primary_key=True, default=None)

    # initial table
    class AlembicThing(ModelBase):  # pyright: ignore[reportRedeclaration]
        t1: Mapped[str] = mapped_column(default="")

    with Model.get_db_engine().connect() as connection:
        assert Model.alembic_autogenerate(
            connection=connection, message="Initial Revision"
        )
    assert Model.migrate()
    version_scripts = list(versions.glob("*.py"))
    assert len(version_scripts) == 1
    assert version_scripts[0].name.endswith("initial_revision.py")

    with sqla_session() as session:
        session.add(AlembicThing(t1="foo"))
        session.commit()

    model_registry.get_metadata().clear()

    # Create column t2, mark t1 as optional with default
    class AlembicThing(ModelBase):  # pyright: ignore[reportRedeclaration]
        t1: Mapped[str | None] = mapped_column(default="default")
        t2: Mapped[str] = mapped_column(default="bar")

    assert Model.migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 2

    with sqla_session() as session:
        session.add(AlembicThing(t2="baz"))
        session.commit()
        result = session.scalars(select(AlembicThing)).all()
        assert len(result) == 2
        assert result[0].t1 == "foo"
        assert result[0].t2 == "bar"
        assert result[1].t1 == "default"
        assert result[1].t2 == "baz"

    model_registry.get_metadata().clear()

    # Drop column t1
    class AlembicThing(ModelBase):  # pyright: ignore[reportRedeclaration]
        t2: Mapped[str] = mapped_column(default="bar")

    assert Model.migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 3

    with sqla_session() as session:
        result = session.scalars(select(AlembicThing)).all()
        assert len(result) == 2
        assert result[0].t2 == "bar"
        assert result[1].t2 == "baz"

    # Add table
    class AlembicSecond(ModelBase):
        a: Mapped[int] = mapped_column(default=42)
        b: Mapped[float] = mapped_column(default=4.2)

    assert Model.migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 4

    with reflex.model.session() as session:
        session.add(AlembicSecond(id=None))
        session.commit()
        result = session.scalars(select(AlembicSecond)).all()
        assert len(result) == 1
        assert result[0].a == 42
        assert result[0].b == 4.2

    # No-op
    # assert Model.migrate(autogenerate=True) #noqa: ERA001
    # assert len(list(versions.glob("*.py"))) == 4 #noqa: ERA001

    # drop table (AlembicSecond)
    model_registry.get_metadata().clear()

    class AlembicThing(ModelBase):  # pyright: ignore[reportRedeclaration]
        t2: Mapped[str] = mapped_column(default="bar")

    assert Model.migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 5

    with reflex.model.session() as session:
        with pytest.raises(OperationalError) as errctx:
            _ = session.scalars(select(AlembicSecond)).all()
        assert errctx.match(r"no such table: alembicsecond")
        # first table should still exist
        result = session.scalars(select(AlembicThing)).all()
        assert len(result) == 2
        assert result[0].t2 == "bar"
        assert result[1].t2 == "baz"

    model_registry.get_metadata().clear()

    class AlembicThing(ModelBase):
        # changing column type not supported by default
        t2: Mapped[int] = mapped_column(default=42)

    assert Model.migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 5

    # clear all metadata to avoid influencing subsequent tests
    model_registry.get_metadata().clear()

    # drop remaining tables
    assert Model.migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 6
