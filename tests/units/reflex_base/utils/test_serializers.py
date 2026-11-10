"""Tests for reflex_base.utils.serializers."""

import gc
import json
import subprocess
import sys
import weakref

import pytest
from reflex_base.utils import serializers
from reflex_base.utils.format import json_dumps
from reflex_base.vars.base import Var
from reflex_base.vars.object import ObjectVar

pytest.importorskip("sqlalchemy")

from sqlalchemy import ForeignKey, create_engine, event, select
from sqlalchemy.orm import (
    DeclarativeBase,
    DynamicMapped,
    Mapped,
    MappedAsDataclass,
    Session,
    WriteOnlyMapped,
    mapped_column,
    relationship,
    selectinload,
    synonym,
)


def test_declarative_base_serializer_handles_loaded_and_unloaded_attributes():
    """Serialize loaded SQLAlchemy attributes without triggering lazy loading."""

    class SerializerBase(DeclarativeBase):
        """Base for serializer regression models."""

    class SerializerTeam(SerializerBase):
        """Team model with a loaded and an unloaded relationship."""

        __tablename__ = "serializer_team"

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str]
        nickname: Mapped[str | None] = mapped_column(nullable=True)
        private_note: Mapped[str] = mapped_column(deferred=True)
        heroes: Mapped[list["SerializerHero"]] = relationship()

    class SerializerHero(SerializerBase):
        """Related model."""

        __tablename__ = "serializer_hero"

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str]
        team_id: Mapped[int] = mapped_column(ForeignKey("serializer_team.id"))

    engine = create_engine("sqlite://")
    SerializerBase.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            SerializerTeam(
                name="Avengers",
                nickname=None,
                private_note="Internal note",
                heroes=[SerializerHero(name="Thor")],
            )
        )
        session.commit()

        loaded_team = session.scalar(
            select(SerializerTeam).options(selectinload(SerializerTeam.heroes))
        )
        assert loaded_team is not None

        # The instance should remain serializable after detachment.
        session.expunge_all()

    assert (
        serializers.get_serializer(SerializerTeam)
        is serializers.serialize_sqlalchemy_base
    )

    payload = json.loads(json_dumps(loaded_team))

    # Loaded scalar attributes are included, including nullable values.
    assert payload["name"] == "Avengers"
    assert payload["nickname"] is None

    # The loaded relationship is serialized recursively.
    assert [hero["name"] for hero in payload["heroes"]] == ["Thor"]

    # The deferred attribute must not trigger a database load.
    assert "private_note" not in payload

    with Session(engine) as session:
        unloaded_team = session.scalar(select(SerializerTeam))
        assert unloaded_team is not None

        # Expired and unloaded attributes must both be omitted.
        session.expire(unloaded_team, ["name"])
        session.expunge(unloaded_team)

    # This also verifies that serialization of a detached instance does
    # not raise DetachedInstanceError.
    unloaded_payload = json.loads(json_dumps(unloaded_team))

    assert "name" not in unloaded_payload
    assert "heroes" not in unloaded_payload
    assert "private_note" not in unloaded_payload

    engine.dispose()


def test_declarative_base_serializer_handles_bidirectional_relationships():
    """Serialize bidirectional relationships without circular references."""

    class Base(DeclarativeBase):
        pass

    class Parent(Base):
        __tablename__ = "serializer_parent"

        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list["Child"]] = relationship(back_populates="parent")

    class Child(Base):
        __tablename__ = "serializer_child"

        id: Mapped[int] = mapped_column(primary_key=True)
        parent_id: Mapped[int] = mapped_column(ForeignKey("serializer_parent.id"))
        parent: Mapped[Parent] = relationship(back_populates="children")

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Parent(id=1, children=[Child(id=2)]))
        session.commit()

        parent = session.scalar(
            select(Parent).options(
                selectinload(Parent.children).selectinload(Child.parent)
            )
        )
        assert parent is not None
        session.expunge_all()

    payload = json.loads(json_dumps(parent))

    assert payload["id"] == 1
    assert len(payload["children"]) == 1
    assert payload["children"][0]["id"] == 2
    assert payload["children"][0]["parent"] == {"id": 1}

    engine.dispose()


def test_declarative_base_serializer_transient_unassigned_relationship():
    """A transient model sends unassigned relationships as empty values."""

    class Base(DeclarativeBase):
        pass

    class Team(Base):
        __tablename__ = "transient_serializer_team"

        id: Mapped[int | None] = mapped_column(primary_key=True, default=None)
        name: Mapped[str]
        leader: Mapped["Hero | None"] = relationship()
        heroes: Mapped[list["Hero"]] = relationship(overlaps="leader")

    class Hero(Base):
        __tablename__ = "transient_serializer_hero"

        id: Mapped[int | None] = mapped_column(primary_key=True, default=None)
        name: Mapped[str]
        team_id: Mapped[int | None] = mapped_column(
            ForeignKey("transient_serializer_team.id")
        )

    assert serializers.serialize(Team(name="Avengers")) == {
        "id": None,
        "name": "Avengers",
        "leader": None,
        "heroes": [],
    }


def test_declarative_base_serializer_pending_unassigned_relationship():
    """A pending model sends unassigned relationships as empty values without SQL."""

    class Base(DeclarativeBase):
        pass

    class Team(Base):
        __tablename__ = "pending_serializer_team"

        id: Mapped[int] = mapped_column(primary_key=True)
        heroes: Mapped[list["Hero"]] = relationship(back_populates="team")

    class Hero(Base):
        __tablename__ = "pending_serializer_hero"

        id: Mapped[int | None] = mapped_column(primary_key=True, default=None)
        name: Mapped[str]
        team_id: Mapped[int] = mapped_column(ForeignKey("pending_serializer_team.id"))
        team: Mapped[Team | None] = relationship(back_populates="heroes")

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Team(id=1))
        session.commit()

    statements = []
    event.listen(
        engine,
        "before_cursor_execute",
        lambda *args: statements.append(args[2]),
    )
    with Session(engine) as session:
        hero = Hero(name="Thor", team_id=1)
        session.add(hero)

        payload = serializers.serialize(hero)

    assert payload == {"id": None, "name": "Thor", "team_id": 1, "team": None}
    assert statements == []
    engine.dispose()


def test_declarative_base_serializer_deleted_attributes():
    """Deleted attributes of a detached model serialize as None without a load."""

    class Base(DeclarativeBase):
        pass

    class Owner(Base):
        __tablename__ = "deleted_attr_owner"

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str | None]

    class Pet(Base):
        __tablename__ = "deleted_attr_pet"

        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int | None] = mapped_column(
            ForeignKey("deleted_attr_owner.id")
        )
        owner: Mapped[Owner | None] = relationship()

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Owner(id=1, name="ada"), Pet(id=1, owner_id=1)])
        session.commit()

    with Session(engine) as session:
        pet = session.scalar(select(Pet).options(selectinload(Pet.owner)))
        assert pet is not None
        owner = pet.owner
        assert owner is not None
        del owner.name
        del pet.owner
        session.expunge_all()

    assert serializers.serialize(owner) == {"id": 1, "name": None}
    assert serializers.serialize(pet) == {"id": 1, "owner_id": 1, "owner": None}
    engine.dispose()


def test_declarative_base_serializer_shared_related_object():
    """An object reached by two non-cyclic paths serializes in full on both paths."""

    class Base(DeclarativeBase):
        pass

    class Author(Base):
        __tablename__ = "shared_author"

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str]

    class Article(Base):
        __tablename__ = "shared_article"

        id: Mapped[int] = mapped_column(primary_key=True)
        author_id: Mapped[int | None] = mapped_column(ForeignKey("shared_author.id"))
        author: Mapped[Author | None] = relationship()
        comments: Mapped[list["Comment"]] = relationship()

    class Comment(Base):
        __tablename__ = "shared_comment"

        id: Mapped[int] = mapped_column(primary_key=True)
        article_id: Mapped[int | None] = mapped_column(ForeignKey("shared_article.id"))
        author_id: Mapped[int | None] = mapped_column(ForeignKey("shared_author.id"))
        author: Mapped[Author | None] = relationship()

    author = Author(id=1, name="ada")
    article = Article(id=1, author=author, comments=[Comment(id=2, author=author)])

    payload = serializers.serialize(article)

    assert isinstance(payload, dict)
    assert payload["author"] == {"id": 1, "name": "ada"}
    assert payload["comments"][0]["author"] == {"id": 1, "name": "ada"}


def test_declarative_base_serializer_omits_write_only_and_dynamic_relationships():
    """Write-only and dynamic relationships never hold loaded values, so they are omitted."""

    class Base(DeclarativeBase):
        pass

    class Team(Base):
        __tablename__ = "query_only_team"

        id: Mapped[int] = mapped_column(primary_key=True)
        recent: WriteOnlyMapped["Hero"] = relationship(overlaps="members")
        members: DynamicMapped["Hero"] = relationship(overlaps="recent")
        latest = synonym("recent")

    class Hero(Base):
        __tablename__ = "query_only_hero"

        id: Mapped[int] = mapped_column(primary_key=True)
        team_id: Mapped[int | None] = mapped_column(ForeignKey("query_only_team.id"))

    assert serializers.serialize(Team(id=1)) == {"id": 1}

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    statements = []
    event.listen(
        engine,
        "before_cursor_execute",
        lambda *args: statements.append(args[2]),
    )
    with Session(engine) as session:
        team = Team(id=2)
        session.add(team)

        assert serializers.serialize(team) == {"id": 2}

    assert statements == []
    engine.dispose()


def test_declarative_base_serializer_does_not_retain_model_classes():
    """Serializing a model does not keep its class alive after the class is dropped."""

    def serialize_new_model() -> weakref.ref:
        """Serialize a temporary model without retaining its class.

        Returns:
            A weak reference to the temporary model class.
        """

        class Base(DeclarativeBase):
            pass

        class Model(Base):
            __tablename__ = "retained_model"

            id: Mapped[int] = mapped_column(primary_key=True)

        assert serializers.serialize(Model(id=1)) == {"id": 1}
        return weakref.ref(Model)

    model = serialize_new_model()
    serializers.get_serializer.cache_clear()
    serializers.get_serializer_type.cache_clear()
    gc.collect()

    assert model() is None


def test_declarative_base_serializer_includes_column_synonyms():
    """A column synonym is sent with the value of its target column."""

    class DataclassBase(MappedAsDataclass, DeclarativeBase):
        pass

    class Account(DataclassBase):
        __tablename__ = "synonym_account"

        id: Mapped[int] = mapped_column(init=False, primary_key=True)
        username: Mapped[str] = mapped_column()
        name: Mapped[str] = synonym("username", init=False)

    class PlainBase(DeclarativeBase):
        pass

    class Label(PlainBase):
        __tablename__ = "synonym_label"

        id: Mapped[int] = mapped_column(primary_key=True)
        text: Mapped[str]
        caption: Mapped[str] = synonym("text")

    engine = create_engine("sqlite://")
    DataclassBase.metadata.create_all(engine)
    PlainBase.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Account(username="ada"), Label(id=1, text="hi")])
        session.commit()
    with Session(engine) as session:
        account = session.scalar(select(Account))
        label = session.scalar(select(Label))
        session.expunge_all()

    assert serializers.serialize(account) == {"id": 1, "username": "ada", "name": "ada"}
    assert serializers.serialize(label) == {"id": 1, "text": "hi", "caption": "hi"}
    assert serializers.serialize(Account(username="new")) == {
        "id": None,
        "username": "new",
        "name": "new",
    }
    engine.dispose()


def test_declarative_base_serializer_reads_synonym_descriptor():
    """A synonym with a custom descriptor is sent through its getter."""

    class Base(DeclarativeBase):
        pass

    class Member(Base):
        __tablename__ = "synonym_member"

        id: Mapped[int] = mapped_column(primary_key=True)
        raw_status: Mapped[str] = mapped_column("status")
        status = synonym(
            "raw_status", descriptor=property(lambda self: self.raw_status.upper())
        )

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Member(id=1, raw_status="active"))
        session.commit()
    with Session(engine) as session:
        member = session.scalar(select(Member))
        session.expunge_all()
    with Session(engine) as session:
        expired = session.scalar(select(Member))
        session.expire(expired, ["raw_status"])
        session.expunge_all()

    expected = {"id": 1, "raw_status": "active", "status": "ACTIVE"}
    assert serializers.serialize(expired) == {"id": 1}
    assert serializers.serialize(member) == expected
    assert serializers.serialize(Member(id=1, raw_status="active")) == expected
    engine.dispose()


def test_declarative_base_serializer_includes_relationship_synonyms():
    """A relationship synonym is serialized like its target relationship."""

    class Base(DeclarativeBase):
        pass

    class Writer(Base):
        __tablename__ = "synonym_writer"

        id: Mapped[int] = mapped_column(primary_key=True)
        articles: Mapped[list["Article"]] = relationship(back_populates="writer")

    class Article(Base):
        __tablename__ = "synonym_article"

        id: Mapped[int] = mapped_column(primary_key=True)
        writer_id: Mapped[int] = mapped_column(ForeignKey("synonym_writer.id"))
        writer: Mapped[Writer] = relationship(back_populates="articles")
        author = synonym("writer")

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Article(id=1, writer=Writer(id=1)))
        session.commit()
    with Session(engine) as session:
        article = session.scalar(select(Article).options(selectinload(Article.writer)))
        session.expunge_all()

    assert json.loads(json_dumps(article)) == {
        "id": 1,
        "writer_id": 1,
        "writer": {"id": 1},
        "author": {"id": 1},
    }
    assert json.loads(json_dumps(Article(id=2, writer=Writer(id=2)))) == {
        "id": 2,
        "writer_id": None,
        "writer": {"id": 2, "articles": [{"id": 2}]},
        "author": {"id": 2, "articles": [{"id": 2}]},
    }
    assert serializers.serialize(Article(id=3)) == {
        "id": 3,
        "writer_id": None,
        "writer": None,
        "author": None,
    }
    engine.dispose()


def test_declarative_base_model_attribute_access():
    """A plain DeclarativeBase model is an ObjectVar with typed column attributes."""

    class Base(DeclarativeBase):
        pass

    class Note(Base):
        __tablename__ = "object_var_note"

        id: Mapped[int] = mapped_column(primary_key=True)
        text: Mapped[str]

    note = Var("note", _var_type=Note).guess_type()

    assert isinstance(note, ObjectVar)
    assert note.text._var_type is str


def test_declarative_base_serializer_transient_loaded_relationship():
    """Serialize a transient model with an assigned relationship."""

    class Base(DeclarativeBase):
        pass

    class Team(Base):
        __tablename__ = "transient_loaded_team"

        id: Mapped[int | None] = mapped_column(primary_key=True, default=None)
        name: Mapped[str]
        heroes: Mapped[list["Hero"]] = relationship()

    class Hero(Base):
        __tablename__ = "transient_loaded_hero"

        id: Mapped[int | None] = mapped_column(primary_key=True, default=None)
        name: Mapped[str]
        team_id: Mapped[int | None] = mapped_column(
            ForeignKey("transient_loaded_team.id")
        )

    team = Team(name="Avengers", heroes=[Hero(name="Thor")])
    payload = serializers.serialize(team)

    assert isinstance(payload, dict)
    assert payload["id"] is None
    assert payload["name"] == "Avengers"
    assert isinstance(payload["heroes"], list)
    assert len(payload["heroes"]) == 1
    assert isinstance(payload["heroes"][0], dict)
    assert payload["heroes"][0]["id"] is None
    assert payload["heroes"][0]["name"] == "Thor"


def test_sqlalchemy_optional_serializer_annotations_resolve() -> None:
    """Runtime introspection must resolve the optional SQLAlchemy annotation."""
    script = """
from typing import Any, get_type_hints

from sqlalchemy.orm import DeclarativeBase
from reflex_base.utils import serializers

hints = get_type_hints(serializers.serialize_sqlalchemy_base)

assert hints["m"] is DeclarativeBase
assert hints["return"] == dict[str, Any]
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr


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


def test_serialize_sqlalchemy_dataclass_uninitialized_field():
    """Uninitialized unmapped dataclass fields should be skipped."""
    import dataclasses

    from reflex_base.utils.serializers import serialize
    from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

    class Base(MappedAsDataclass, DeclarativeBase):
        pass

    class User(Base):
        __tablename__ = "test_user_uninitialized"

        id: Mapped[int] = mapped_column(primary_key=True)
        display_label: str = ""
        computed_label: str = dataclasses.field(init=False)

    user = User(id=1)

    result = serialize(user)

    assert isinstance(result, dict)
    assert result["id"] == 1
    assert result["display_label"] == ""
    assert "computed_label" not in result


def test_serialize_sqlalchemy_pending_model_includes_unset_fields():
    """Pending models preserve unset mapped fields during serialization."""
    from reflex_base.utils.serializers import serialize
    from sqlalchemy import create_engine
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

    class Base(DeclarativeBase):
        pass

    class User(Base):
        __tablename__ = "test_pending_user"

        id: Mapped[int | None] = mapped_column(primary_key=True, default=None)
        username: Mapped[str]

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    user = User(username="ada")

    with Session(engine) as session:
        session.add(user)

        result = serialize(user)

        assert result == {"id": None, "username": "ada"}

    engine.dispose()


def test_serialize_sqlalchemy_transient_unloaded_relationship():
    """Test that transient models send unassigned relationships as empty values."""
    from reflex_base.utils.serializers import serialize
    from sqlalchemy import ForeignKey, inspect
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

    class Base(DeclarativeBase):
        pass

    class TransientParent(Base):
        __tablename__ = "test_transient_unloaded_parent"
        id: Mapped[int | None] = mapped_column(primary_key=True, default=None)
        children: Mapped[list["TransientChild"]] = relationship()

    class TransientChild(Base):
        __tablename__ = "test_transient_unloaded_child"
        id: Mapped[int | None] = mapped_column(primary_key=True, default=None)
        parent_id: Mapped[int | None] = mapped_column(
            ForeignKey("test_transient_unloaded_parent.id")
        )

    parent = TransientParent()
    assert "children" in inspect(parent).unloaded

    assert serialize(parent) == {"id": None, "children": []}
