import dataclasses

import pytest
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
from typing_extensions import assert_type

import reflex as rx
from reflex.utils.types import GenericType
from reflex.vars.base import Var
from reflex.vars.object import LiteralObjectVar, ObjectVar


class Bare:
    """A bare class with a single attribute."""

    quantity: int = 0


@rx.serializer
def serialize_bare(obj: Bare) -> dict:
    """A serializer for the bare class.

    Args:
        obj: The object to serialize.

    Returns:
        A dictionary with the quantity attribute.
    """
    return {"quantity": obj.quantity}


class Base(rx.Base):
    """A reflex base class with a single attribute."""

    quantity: int = 0


class SqlaBase(DeclarativeBase, MappedAsDataclass):
    """Sqlalchemy declarative mapping base class."""

    pass


class SqlaModel(SqlaBase):
    """A sqlalchemy model with a single attribute."""

    __tablename__: str = "sqla_model"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    quantity: Mapped[int] = mapped_column(default=0)


@dataclasses.dataclass
class Dataclass:
    """A dataclass with a single attribute."""

    quantity: int = 0


class ObjectState(rx.State):
    """A reflex state with bare, base and sqlalchemy base vars."""

    bare: rx.Field[Bare] = rx.field(Bare())
    base: rx.Field[Base] = rx.field(Base())
    sqlamodel: rx.Field[SqlaModel] = rx.field(SqlaModel())
    dataclass: rx.Field[Dataclass] = rx.field(Dataclass())


@pytest.mark.parametrize("type_", [Base, Bare, SqlaModel, Dataclass])
def test_var_create(type_: GenericType) -> None:
    my_object = type_()
    var = Var.create(my_object)
    assert var._var_type is type_

    quantity = var.quantity
    assert quantity._var_type is int


@pytest.mark.parametrize("type_", [Base, Bare, SqlaModel, Dataclass])
def test_literal_create(type_: GenericType) -> None:
    my_object = type_()
    var = LiteralObjectVar.create(my_object)
    assert var._var_type is type_

    quantity = var.quantity
    assert quantity._var_type is int


@pytest.mark.parametrize("type_", [Base, Bare, SqlaModel, Dataclass])
def test_guess(type_: GenericType) -> None:
    my_object = type_()
    var = Var.create(my_object)
    var = var.guess_type()
    assert var._var_type is type_

    quantity = var.quantity
    assert quantity._var_type is int


@pytest.mark.parametrize("type_", [Base, Bare, SqlaModel, Dataclass])
def test_state(type_: GenericType) -> None:
    attr_name = type_.__name__.lower()
    var = getattr(ObjectState, attr_name)
    assert var._var_type is type_

    quantity = var.quantity
    assert quantity._var_type is int


@pytest.mark.parametrize("type_", [Base, Bare, SqlaModel, Dataclass])
def test_state_to_operation(type_: GenericType) -> None:
    attr_name = type_.__name__.lower()
    original_var = getattr(ObjectState, attr_name)

    var = original_var.to(ObjectVar, type_)
    assert var._var_type is type_

    var = original_var.to(ObjectVar)
    assert var._var_type is type_


def test_typing() -> None:
    # Bare
    var = ObjectState.bare.to(ObjectVar)
    _ = assert_type(var, ObjectVar[Bare])

    # Base
    var = ObjectState.base
    _ = assert_type(var, ObjectVar[Base])

    # Sqla
    var = ObjectState.sqlamodel
    _ = assert_type(var, ObjectVar[SqlaModel])

    # Dataclass
    var = ObjectState.dataclass
    _ = assert_type(var, ObjectVar[Dataclass])
