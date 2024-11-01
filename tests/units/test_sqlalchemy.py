from pathlib import Path
from typing import Optional, Type
from unittest import mock

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    declared_attr,
    mapped_column,
)

import reflex.constants
import reflex.model
from reflex.model import Model, ModelRegistry, sqla_session


@pytest.mark.filterwarnings(
    "ignore:This declarative base already contains a class with the same class name",
)
def test_automigration(
    tmp_working_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_registry: Type[ModelRegistry],
):
    """Test alembic automigration with add and drop table and column.

    Args:
        tmp_working_dir: directory where database and migrations are stored
        monkeypatch: pytest fixture to overwrite attributes
        model_registry: clean reflex ModelRegistry
    """
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
        id: Mapped[Optional[int]] = mapped_column(primary_key=True, default=None)

    # initial table
    class AlembicThing(ModelBase):  # pyright: ignore[reportGeneralTypeIssues]
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
    class AlembicThing(ModelBase):  # pyright: ignore[reportGeneralTypeIssues]
        t1: Mapped[Optional[str]] = mapped_column(default="default")
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
    class AlembicThing(ModelBase):  # pyright: ignore[reportGeneralTypeIssues]
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
    # assert Model.migrate(autogenerate=True)
    # assert len(list(versions.glob("*.py"))) == 4

    # drop table (AlembicSecond)
    model_registry.get_metadata().clear()

    class AlembicThing(ModelBase):  # pyright: ignore[reportGeneralTypeIssues]
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
