from pathlib import Path
from typing import Optional, Type
from unittest import mock

import pytest
import sqlalchemy
import sqlmodel

import reflex.constants
import reflex.model
from reflex.model import Model, ModelRegistry


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

    class ChildModel(Model):
        custom_id: Optional[int] = sqlmodel.Field(default=None, primary_key=True)
        name: str

    return ChildModel(name="name")


def test_default_primary_key(model_default_primary: Model):
    """Test that if a primary key is not defined a default is added.

    Args:
        model_default_primary: Fixture.
    """
    assert "id" in model_default_primary.__class__.__fields__


def test_custom_primary_key(model_custom_primary: Model):
    """Test that if a primary key is defined no default key is added.

    Args:
        model_custom_primary: Fixture.
    """
    assert "id" not in model_custom_primary.__class__.__fields__


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

    Model.alembic_init()
    assert alembic_ini.exists()
    assert versions.exists()

    # initial table
    class AlembicThing(Model, table=True):  # type: ignore
        t1: str

    with Model.get_db_engine().connect() as connection:
        assert Model.alembic_autogenerate(
            connection=connection, message="Initial Revision"
        )
    assert Model.migrate()
    version_scripts = list(versions.glob("*.py"))
    assert len(version_scripts) == 1
    assert version_scripts[0].name.endswith("initial_revision.py")

    with reflex.model.session() as session:
        session.add(AlembicThing(id=None, t1="foo"))
        session.commit()

    model_registry.get_metadata().clear()

    # Create column t2, mark t1 as optional with default
    class AlembicThing(Model, table=True):  # type: ignore
        t1: Optional[str] = "default"
        t2: str = "bar"

    assert Model.migrate(autogenerate=True)
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
    class AlembicThing(Model, table=True):  # type: ignore
        t2: str = "bar"

    assert Model.migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 3

    with reflex.model.session() as session:
        result = session.exec(sqlmodel.select(AlembicThing)).all()
        assert len(result) == 2
        assert result[0].t2 == "bar"
        assert result[1].t2 == "baz"

    # Add table
    class AlembicSecond(Model, table=True):  # type: ignore
        a: int = 42
        b: float = 4.2

    assert Model.migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 4

    with reflex.model.session() as session:
        session.add(AlembicSecond(id=None))
        session.commit()
        result = session.exec(sqlmodel.select(AlembicSecond)).all()
        assert len(result) == 1
        assert result[0].a == 42
        assert result[0].b == 4.2

    # No-op
    assert Model.migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 4

    # drop table (AlembicSecond)
    model_registry.get_metadata().clear()

    class AlembicThing(Model, table=True):  # type: ignore
        t2: str = "bar"

    assert Model.migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 5

    with reflex.model.session() as session:
        with pytest.raises(sqlalchemy.exc.OperationalError) as errctx:  # type: ignore
            session.exec(sqlmodel.select(AlembicSecond)).all()
        assert errctx.match(r"no such table: alembicsecond")
        # first table should still exist
        result = session.exec(sqlmodel.select(AlembicThing)).all()
        assert len(result) == 2
        assert result[0].t2 == "bar"
        assert result[1].t2 == "baz"

    model_registry.get_metadata().clear()

    class AlembicThing(Model, table=True):  # type: ignore
        # changing column type not supported by default
        t2: int = 42

    assert Model.migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 5

    # clear all metadata to avoid influencing subsequent tests
    model_registry.get_metadata().clear()

    # drop remaining tables
    assert Model.migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 6
