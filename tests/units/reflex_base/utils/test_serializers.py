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
    Session,
    WriteOnlyMapped,
    mapped_column,
    relationship,
    selectinload,
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
