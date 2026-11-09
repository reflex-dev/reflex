"""Tests for reflex_base.utils.serializers."""

import json
import subprocess
import sys

import pytest
from reflex_base.utils import serializers
from reflex_base.utils.format import json_dumps

pytest.importorskip("sqlalchemy")

from sqlalchemy import ForeignKey, create_engine, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
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


def test_declarative_base_serializer_transient_unassigned_relationship(monkeypatch):
    """Serialize a transient model with unassigned relationships without triggering a load."""
    import sqlalchemy

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

    team = Team(name="Avengers")
    state = sqlalchemy.inspect(team)
    assert "heroes" in state.unloaded
    assert "leader" in state.unloaded
    assert "id" in state.unloaded

    orig_value_prop = type(state.attrs.heroes).value
    orig_value_fget = orig_value_prop.fget
    assert orig_value_fget is not None

    def guarded_value(self):
        if self.key in ("heroes", "leader"):
            msg = f"Loader was triggered for unassigned relationship {self.key!r}"
            raise AssertionError(msg)
        return orig_value_fget(self)

    monkeypatch.setattr(type(state.attrs.heroes), "value", property(guarded_value))

    payload = serializers.serialize(team)

    assert isinstance(payload, dict)
    assert "heroes" not in payload
    assert "leader" not in payload
    assert payload == {"id": None, "name": "Avengers"}


def test_declarative_base_serializer_pending_unassigned_relationship(monkeypatch):
    """Serialize a pending model with unassigned relationships without triggering a load."""
    import sqlalchemy

    class Base(DeclarativeBase):
        pass

    class Team(Base):
        __tablename__ = "pending_serializer_team"

        id: Mapped[int | None] = mapped_column(primary_key=True, default=None)
        name: Mapped[str]
        leader: Mapped["Hero | None"] = relationship()
        heroes: Mapped[list["Hero"]] = relationship(overlaps="leader")

    class Hero(Base):
        __tablename__ = "pending_serializer_hero"

        id: Mapped[int | None] = mapped_column(primary_key=True, default=None)
        name: Mapped[str]
        team_id: Mapped[int | None] = mapped_column(
            ForeignKey("pending_serializer_team.id")
        )

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        team = Team(name="Avengers")
        session.add(team)
        state = sqlalchemy.inspect(team)
        assert state.pending
        assert "heroes" in state.unloaded
        assert "leader" in state.unloaded
        assert "id" in state.unloaded

        orig_value_prop = type(state.attrs.heroes).value
        orig_value_fget = orig_value_prop.fget
        assert orig_value_fget is not None

        def guarded_value(self):
            if self.key in ("heroes", "leader"):
                msg = f"Loader was triggered for unassigned relationship {self.key!r}"
                raise AssertionError(msg)
            return orig_value_fget(self)

        monkeypatch.setattr(type(state.attrs.heroes), "value", property(guarded_value))

        payload = serializers.serialize(team)

        assert isinstance(payload, dict)
        assert "heroes" not in payload
        assert "leader" not in payload
        assert payload == {"id": None, "name": "Avengers"}

    engine.dispose()


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
