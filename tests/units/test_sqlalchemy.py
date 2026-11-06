import math
from pathlib import Path
from unittest import mock

import pytest
from reflex_base.utils.serializers import serializer

import reflex.constants
import reflex.model
from reflex.istate.proxy import MutableProxy
from reflex.model import (
    ModelRegistry,
    alembic_autogenerate,
    alembic_init,
    get_engine,
    migrate,
    sqla_session,
)

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
    alembic_init()
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

    with get_engine().connect() as connection:
        assert alembic_autogenerate(connection=connection, message="Initial Revision")
    assert migrate()
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

    assert migrate(autogenerate=True)
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

    assert migrate(autogenerate=True)
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

    assert migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 4

    with reflex.model.session() as session:
        session.add(AlembicSecond(id=None))
        session.commit()
        result = session.scalars(select(AlembicSecond)).all()
        assert len(result) == 1
        assert result[0].a == 42
        assert math.isclose(result[0].b, 4.2)

    # No-op
    # assert migrate(autogenerate=True) #noqa: ERA001
    # assert len(list(versions.glob("*.py"))) == 4 #noqa: ERA001

    # drop table (AlembicSecond)
    model_registry.get_metadata().clear()

    class AlembicThing(ModelBase):  # pyright: ignore[reportRedeclaration]
        t2: Mapped[str] = mapped_column(default="bar")

    assert migrate(autogenerate=True)
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

    assert migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 5

    # clear all metadata to avoid influencing subsequent tests
    model_registry.get_metadata().clear()

    # drop remaining tables
    assert migrate(autogenerate=True)
    assert len(list(versions.glob("*.py"))) == 6


def test_serialize_sqlalchemy_cyclic_custom_serializer():
    """Test that custom serializers on related models are called, and cycles are broken safely."""
    from reflex_base.utils import serializers
    from reflex_base.utils.serializers import serialize
    from sqlalchemy import ForeignKey
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

    class Base(DeclarativeBase):
        pass

    class Parent(Base):
        __tablename__ = "test_parent"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list["Child"]] = relationship(back_populates="parent")

    class Child(Base):
        __tablename__ = "test_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        parent_id: Mapped[int] = mapped_column(ForeignKey("test_parent.id"))
        parent: Mapped["Parent"] = relationship(back_populates="children")

    original_serializers = serializers.SERIALIZERS.copy()
    original_serializer_types = serializers.SERIALIZER_TYPES.copy()

    try:

        @serializers.serializer
        def serialize_child(child: Child) -> dict:
            return {
                "custom_child_id": child.id,
                "has_parent": child.parent is not None,
            }

        parent = Parent(id=1)
        child = Child(id=2, parent=parent)
        parent.children = [child]

        result = serialize(parent)

        assert isinstance(result, dict)
        assert result["id"] == 1
        assert isinstance(result["children"], list)
        assert len(result["children"]) == 1
        assert result["children"][0]["custom_child_id"] == 2
        assert result["children"][0]["has_parent"] is True

        child_result = serialize(child)

        assert isinstance(child_result, dict)
        assert child_result["custom_child_id"] == 2

        serializers.SERIALIZERS.pop(Child)
        serializers.SERIALIZER_TYPES.pop(Child, None)
        serializers.get_serializer.cache_clear()
        serializers.get_serializer_type.cache_clear()

        result = serialize(parent)

        assert isinstance(result, dict)
        assert isinstance(result["children"], list)
        assert result["children"][0]["parent"] == {"id": 1}

    finally:
        serializers.SERIALIZERS.clear()
        serializers.SERIALIZERS.update(original_serializers)
        serializers.SERIALIZER_TYPES.clear()
        serializers.SERIALIZER_TYPES.update(original_serializer_types)
        serializers.get_serializer.cache_clear()
        serializers.get_serializer_type.cache_clear()


def test_serialize_sqlalchemy_keyed_dict_relationship():
    """Test that dictionary-based and list-based relationships are serialized correctly."""
    from reflex_base.utils.serializers import serialize
    from sqlalchemy import ForeignKey
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
    from sqlalchemy.orm.collections import attribute_keyed_dict

    class Base(DeclarativeBase):
        pass

    class Parent(Base):
        __tablename__ = "test_parent_keyed"
        id: Mapped[int] = mapped_column(primary_key=True)

        dict_children: Mapped[dict[str, "DictChild"]] = relationship(
            "DictChild",
            collection_class=attribute_keyed_dict("name"),
            back_populates="parent",
        )

        list_children: Mapped[list["ListChild"]] = relationship(
            "ListChild",
            back_populates="parent",
        )

    class DictChild(Base):
        __tablename__ = "test_dict_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()
        parent_id: Mapped[int] = mapped_column(ForeignKey("test_parent_keyed.id"))
        parent: Mapped["Parent"] = relationship(
            "Parent", back_populates="dict_children"
        )

    class ListChild(Base):
        __tablename__ = "test_list_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        parent_id: Mapped[int] = mapped_column(ForeignKey("test_parent_keyed.id"))
        parent: Mapped["Parent"] = relationship(
            "Parent", back_populates="list_children"
        )

    parent = Parent(id=1)

    dict_child = DictChild(id=10, name="Alice", parent=parent)
    parent.dict_children["Alice"] = dict_child

    ListChild(id=20, parent=parent)

    result = serialize(parent)

    assert isinstance(result, dict)
    assert result["id"] == 1
    assert isinstance(result["dict_children"], dict)
    assert "Alice" in result["dict_children"]
    assert isinstance(result["dict_children"]["Alice"], dict)
    assert result["dict_children"]["Alice"]["name"] == "Alice"
    assert result["dict_children"]["Alice"]["id"] == 10
    assert isinstance(result["list_children"], list)
    assert len(result["list_children"]) == 1
    assert isinstance(result["list_children"][0], dict)
    assert result["list_children"][0]["id"] == 20


def test_serialize_sqlalchemy_unloaded_relationship():
    """Test that unloaded relationships are omitted during serialization without triggering a load."""
    from reflex_base.utils.serializers import serialize
    from sqlalchemy import ForeignKey, create_engine
    from sqlalchemy.orm import (
        DeclarativeBase,
        Mapped,
        Session,
        mapped_column,
        relationship,
    )
    from sqlalchemy.orm.collections import attribute_keyed_dict

    class Base(DeclarativeBase):
        pass

    class UnloadedParent(Base):
        __tablename__ = "test_unloaded_parent"
        id: Mapped[int] = mapped_column(primary_key=True)

        dict_children: Mapped[dict[str, "UnloadedChild"]] = relationship(
            "UnloadedChild",
            collection_class=attribute_keyed_dict("name"),
        )

    class UnloadedChild(Base):
        __tablename__ = "test_unloaded_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()
        parent_id: Mapped[int] = mapped_column(ForeignKey("test_unloaded_parent.id"))

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        parent = UnloadedParent(id=1)
        child = UnloadedChild(id=10, name="Alice", parent_id=1)
        session.add_all([parent, child])
        session.commit()

    with Session(engine) as session:
        loaded_parent = session.get(UnloadedParent, 1)
        assert loaded_parent is not None

        from sqlalchemy import inspect

        assert "dict_children" in inspect(loaded_parent).unloaded

        result = serialize(loaded_parent)

        assert isinstance(result, dict)
        assert result["id"] == 1
        assert "dict_children" not in result
        assert "dict_children" in inspect(loaded_parent).unloaded


def test_unserialized_property_on_sqlalchemy_dataclass():
    """Test that plain properties on SQLAlchemy dataclasses are flagged."""
    from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

    from reflex.utils.types import is_unserialized_property

    class Base(MappedAsDataclass, DeclarativeBase):
        pass

    class User(Base):
        __tablename__ = "test_user_property"

        id: Mapped[int] = mapped_column(primary_key=True)
        first_name: Mapped[str]
        last_name: Mapped[str]

        @property
        def double(self) -> str:
            return f"{self.first_name} {self.last_name}"

    assert is_unserialized_property(User, "double")


def test_serialize_sqlalchemy_cycle_uses_mapped_attribute_names():
    """Cycle references use Python mapped attribute names instead of column names."""
    from reflex_base.utils.serializers import serialize
    from sqlalchemy import ForeignKey
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

    class Base(DeclarativeBase):
        pass

    class Parent(Base):
        __tablename__ = "test_parent_column_name"

        id: Mapped[int] = mapped_column("parent_id", primary_key=True)
        children: Mapped[list["Child"]] = relationship(back_populates="parent")

    class Child(Base):
        __tablename__ = "test_child_column_name"

        id: Mapped[int] = mapped_column(primary_key=True)
        parent_id: Mapped[int] = mapped_column(
            ForeignKey("test_parent_column_name.parent_id")
        )
        parent: Mapped[Parent] = relationship(back_populates="children")

    parent = Parent(id=1)
    child = Child(id=2, parent=parent)
    parent.children = [child]

    result = serialize(parent)

    assert isinstance(result, dict)
    assert isinstance(result["children"], list)
    assert isinstance(result["children"][0], dict)
    assert result["id"] == 1
    assert result["children"][0]["parent"] == {"id": 1}


def test_serialize_sqlalchemy_expired_detached_cycle():
    """Test that serializing a cyclic relationship with an expired/detached parent does not raise DetachedInstanceError."""
    from reflex_base.utils.serializers import serialize
    from sqlalchemy import ForeignKey, create_engine
    from sqlalchemy.orm import (
        DeclarativeBase,
        Mapped,
        Session,
        mapped_column,
        relationship,
    )

    class Base(DeclarativeBase):
        pass

    class DetachedParent(Base):
        __tablename__ = "test_detached_parent"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list["DetachedChild"]] = relationship(back_populates="parent")

    class DetachedChild(Base):
        __tablename__ = "test_detached_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        parent_id: Mapped[int] = mapped_column(ForeignKey("test_detached_parent.id"))
        parent: Mapped["DetachedParent"] = relationship(back_populates="children")

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        parent = DetachedParent(id=1)
        child = DetachedChild(id=2, parent=parent)
        session.add_all([parent, child])
        session.flush()

        _ = parent.children
        _ = child.parent

        session.expire(parent, ["id"])
        session.expunge_all()

    result = serialize(parent)

    assert isinstance(result, dict)
    assert "id" not in result
    assert isinstance(result.get("children"), list)
    assert len(result["children"]) == 1
    assert result["children"][0]["id"] == 2
    assert result["children"][0]["parent"] is None


def test_serialize_sqlalchemy_composite_pk_cycle():
    """Test that cyclic relationships with composite primary keys are serialized correctly, even if partially expired."""
    from reflex_base.utils.serializers import serialize
    from sqlalchemy import ForeignKeyConstraint, create_engine
    from sqlalchemy.orm import (
        DeclarativeBase,
        Mapped,
        Session,
        mapped_column,
        relationship,
    )

    class Base(DeclarativeBase):
        pass

    class CompositeParent(Base):
        __tablename__ = "test_composite_parent"
        id1: Mapped[int] = mapped_column(primary_key=True)
        id2: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list["CompositeChild"]] = relationship(back_populates="parent")

    class CompositeChild(Base):
        __tablename__ = "test_composite_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        parent_id1: Mapped[int] = mapped_column()
        parent_id2: Mapped[int] = mapped_column()

        __table_args__ = (
            ForeignKeyConstraint(
                ["parent_id1", "parent_id2"],
                ["test_composite_parent.id1", "test_composite_parent.id2"],
            ),
        )

        parent: Mapped["CompositeParent"] = relationship(back_populates="children")

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        parent = CompositeParent(id1=1, id2=2)
        child = CompositeChild(id=10, parent=parent)
        session.add_all([parent, child])
        session.commit()

        parent = session.get(CompositeParent, (1, 2))

        assert parent is not None

        _ = parent.children
        _ = parent.children[0].parent

        result = serialize(parent)

        assert isinstance(result, dict)
        assert result["id1"] == 1
        assert result["id2"] == 2
        assert isinstance(result.get("children"), list)
        assert len(result["children"]) == 1
        assert isinstance(result["children"][0], dict)
        assert result["children"][0].get("parent") == {"id1": 1, "id2": 2}

    with Session(engine) as session:
        parent2 = CompositeParent(id1=3, id2=4)
        child2 = CompositeChild(id=20, parent=parent2)
        session.add_all([parent2, child2])
        session.flush()

        _ = parent2.children
        _ = child2.parent

        session.expire(parent2, ["id1"])
        session.expunge_all()

    result2 = serialize(parent2)

    assert isinstance(result2, dict)
    assert "id1" not in result2
    assert result2["id2"] == 4
    assert isinstance(result2.get("children"), list)
    assert isinstance(result2["children"][0], dict)
    assert result2["children"][0].get("parent") is None


def test_serialize_sqlalchemy_dataclass_unmapped_fields():
    """Test that unmapped dataclass fields are preserved."""
    from reflex_base.utils.serializers import serialize
    from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

    class Base(MappedAsDataclass, DeclarativeBase):
        pass

    class User(Base):
        __tablename__ = "test_user_unmapped"

        id: Mapped[int] = mapped_column(primary_key=True)
        display_label: str = ""

    user = User(id=1, display_label="Somil")

    result = serialize(user)

    assert isinstance(result, dict)
    assert result["id"] == 1
    assert result["display_label"] == "Somil"
