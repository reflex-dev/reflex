"""Tests for reflex_workflow.dataclass, the mixins for dataclass models.

The migration test needs a database to compare a schema against; set
REFLEX_TEST_POSTGRES to a postgresql:// URL for one the tests may wipe.
"""

from __future__ import annotations

import dataclasses
import inspect
import os
import warnings
from typing import Any

import pytest
from alembic.autogenerate import produce_migrations, render_python_code
from alembic.migration import MigrationContext
from reflex_workflow import dataclass as dc
from reflex_workflow import model, step
from sqlalchemy import MetaData, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

URL = os.environ.get("REFLEX_TEST_POSTGRES", "").replace(
    "postgresql://", "postgresql+psycopg://", 1
)


class Base(MappedAsDataclass, DeclarativeBase, kw_only=True):
    """The base a generated application declares."""


class Plain(DeclarativeBase):
    """The base an application that does not use dataclasses declares."""


class Onboarding(Base, dc.Workflow):
    """A run on a dataclass base, as an application would write it."""

    __tablename__ = "wf_dataclass_onboarding"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    email: Mapped[str] = mapped_column(String(128))
    nudges: Mapped[int] = mapped_column(default=0)

    @step
    async def welcome(self):
        """Record and stop."""
        self.nudges += 1


class Ordinary(Plain, model.Workflow):
    """The same run on a plain base, to compare the two mixins against."""

    __tablename__ = "wf_dataclass_ordinary"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(128))
    nudges: Mapped[int] = mapped_column(default=0)


def shapes(metadata: MetaData, table: str) -> dict[str, tuple[Any, ...]]:
    """Describe a table's columns in the ways a migration would care about.

    Args:
        metadata: The metadata the table was declared on.
        table: Its name.

    Returns:
        Each column's type, nullability, indexing and defaults, by name.
    """
    return {
        column.name: (
            str(column.type),
            column.nullable,
            bool(column.index),
            column.primary_key,
            getattr(column.server_default, "arg", None),
        )
        for column in metadata.tables[table].columns
    }


@pytest.fixture(scope="module", autouse=True)
def _forget_the_tables_declared_here():
    """Leave the registry without this module's tables in it.

    A worker told no workflows runs every workflow in the registry, so a table
    left behind here is one another module's worker would try to claim against
    a database that never had it.

    Yields:
        Nothing; the registry is cleaned up afterwards.
    """
    yield
    for name, cls in list(model.REGISTRY.items()):
        if cls.__module__ == __name__:
            del model.REGISTRY[name]


def test_a_dataclass_model_keeps_the_constructor_it_would_have_had():
    # The engine's columns are the engine's to set, so they stay out of the
    # constructor and the model reads as it did before the mixin was added.
    assert list(inspect.signature(Onboarding.__init__).parameters) == [
        "self",
        "email",
        "nudges",
    ]
    row = Onboarding(email="a@b.c")
    assert (row.nudges, row.next_step, row.attempts) == (0, None, 0)
    assert dataclasses.is_dataclass(row)


def test_the_engines_own_tables_take_no_constructor_arguments(monkeypatch):
    # Whichever test module mapped one first holds the engine's pointer to it;
    # these are a second pair, for their shape rather than to be written to.
    monkeypatch.setattr(model, "ATTEMPTS", None)
    monkeypatch.setattr(model, "BUCKET", None)

    class Attempt(Base, dc.AttemptLog):
        """The attempt history on a dataclass base."""

        __tablename__ = "wf_dataclass_attempt"

    class Rate(Base, dc.RateBucket):
        """The rate buckets on a dataclass base."""

        __tablename__ = "wf_dataclass_rate"

    # The engine writes these rows with inserts of its own; nothing builds one,
    # and a column without a default would otherwise be a required argument.
    for cls in (Attempt, Rate):
        assert list(inspect.signature(cls.__init__).parameters) == ["self"]
    # Without a server default, a NOT NULL column cannot be added to a table
    # that already has rows.
    assert Rate.__table__.c.tokens.server_default.arg == "0"


def test_the_two_mixins_declare_the_same_columns():
    theirs = shapes(Base.metadata, Onboarding.__tablename__)
    plain = shapes(Plain.metadata, Ordinary.__tablename__)
    # Two spellings of one mixin: a column that gained a default, an index or a
    # type in one of them and not the other would be a difference between
    # applications that should not differ.
    assert theirs == plain


@pytest.mark.parametrize("name", ["attempts", "wf_version"])
def test_the_counting_columns_start_at_zero_in_the_database(name):
    # Without a server default, a NOT NULL column cannot be added to a table
    # that already has rows, which is what mixing a workflow into one means.
    column = Onboarding.__table__.c[name]
    assert column.server_default is not None
    assert column.server_default.arg == "0"


def test_a_dataclass_mixin_warns_about_nothing():
    with warnings.catch_warnings():
        warnings.simplefilter("error")

        class Late(Base, dc.Workflow):
            """Declared under warnings-as-errors, which 2.1 makes real errors."""

            __tablename__ = "wf_dataclass_late"

            id: Mapped[int] = mapped_column(primary_key=True, init=False)

    assert Late.__tablename__ == "wf_dataclass_late"


@pytest.mark.skipif(not URL, reason="set REFLEX_TEST_POSTGRES to test against Postgres")
def test_a_migration_renders_the_defaults_as_literals():
    class Fresh(MappedAsDataclass, DeclarativeBase, kw_only=True):
        """A base of this test's own, so only its table is rendered."""

    class Job(Fresh, dc.Workflow):
        """One workflow table, as an application's first migration would add it."""

        __tablename__ = "wf_dataclass_migrated"

        id: Mapped[int] = mapped_column(primary_key=True, init=False)

    engine = create_engine(URL)
    try:
        with engine.connect() as connection:
            # Against an empty schema, so what is rendered is the whole table
            # as a migration would first create it.
            context = MigrationContext.configure(
                connection, opts={"target_metadata": Fresh.metadata}
            )
            upgrade = produce_migrations(context, Fresh.metadata).upgrade_ops
            assert upgrade is not None
            script = render_python_code(upgrade)
    finally:
        engine.dispose()

    # Literal text, which is what a migration reviewer reads and what a rule
    # that only accepts literals can check -- not a repr of a Python object.
    assert script.count("server_default='0'") == 2
    for name in ("attempts", "wf_version"):
        line = next(sql for sql in script.splitlines() if f"'{name}'" in sql)
        assert "server_default='0'" in line
    assert "<sqlalchemy" not in script


def test_the_dataclass_module_offers_the_same_names():
    assert set(dc.__all__) == {"Workflow", "AttemptLog", "RateBucket"}
    for name in dc.__all__:
        assert issubclass(getattr(dc, name), getattr(model, name))


def test_a_dataclass_workflow_is_a_workflow_like_any_other():
    # The engine finds it by table name and reads its steps the same way, so a
    # deployment can hold both spellings at once.
    assert model.REGISTRY["wf_dataclass_onboarding"] is Onboarding
    assert set(Onboarding.__workflow_steps__) == {"welcome"}
    assert isinstance(Onboarding(email="a@b.c"), model.Workflow)
