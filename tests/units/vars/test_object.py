import dataclasses
from collections.abc import Sequence
from typing import Any

import pytest
from reflex_base.utils.exceptions import VarAttributeError
from reflex_base.utils.imports import ImportVar
from reflex_base.utils.types import GenericType
from reflex_base.vars.base import Var, VarData
from reflex_base.vars.number import NumberVar
from reflex_base.vars.object import LiteralObjectVar, ObjectVar, RestProp
from reflex_base.vars.sequence import ArrayVar
from typing_extensions import assert_type

import reflex as rx

pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic")

import pydantic
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

from reflex.experimental import hybrid_property


class HybridQuantity:
    """Mixin defining hybrid properties on top of a ``quantity`` attribute.

    Used to verify that ``hybrid_property`` resolves uniformly across every kind of
    object var (bare class, pydantic model, sqlalchemy model and dataclass).
    """

    # Provided by each subclass; typed loosely so the various concrete declarations
    # (e.g. sqlalchemy's `Mapped[int]`) don't conflict with the mixin.
    quantity: Any

    @hybrid_property
    def doubled(self) -> int:
        """A simple hybrid property reusing the same code on frontend and backend.

        Returns:
            Twice the quantity.
        """
        return self.quantity * 2

    @hybrid_property
    def is_nonzero(self) -> bool:
        """A hybrid property whose backend getter differs from the frontend var.

        Returns:
            Whether the quantity is non-zero.
        """
        return self.quantity != 0

    @is_nonzero.var
    def is_nonzero(cls) -> Var[bool]:
        """The frontend var for ``is_nonzero`` (deliberately distinct from the getter).

        Returns:
            A Var that is True when the quantity is greater than zero.
        """
        return cls.quantity > 0


class Bare(HybridQuantity):
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


class Base(HybridQuantity, pydantic.BaseModel):
    """A pydantic BaseModel class with a single attribute."""

    quantity: int = 0


class SqlaBase(DeclarativeBase, MappedAsDataclass):
    """Sqlalchemy declarative mapping base class."""


class SqlaModel(HybridQuantity, SqlaBase):
    """A sqlalchemy model with a single attribute."""

    __tablename__: str = "sqla_model"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    quantity: Mapped[int] = mapped_column(default=0)


@dataclasses.dataclass
class Dataclass(HybridQuantity):
    """A dataclass with a single attribute."""

    quantity: int = 0


class ObjectState(rx.State):
    """A reflex state with bare, base and sqlalchemy base vars."""

    bare: rx.Field[Bare] = rx.field(Bare())
    bare_optional: rx.Field[Bare | None] = rx.field(None)
    base: rx.Field[Base] = rx.field(Base())
    base_optional: rx.Field[Base | None] = rx.field(None)
    sqlamodel: rx.Field[SqlaModel] = rx.field(SqlaModel())
    sqlamodel_optional: rx.Field[SqlaModel | None] = rx.field(None)
    dataclass: rx.Field[Dataclass] = rx.field(Dataclass())
    dataclass_optional: rx.Field[Dataclass | None] = rx.field(None)

    base_list: rx.Field[list[Base]] = rx.field([Base()])


@pytest.mark.parametrize("type_", [Base, Bare, SqlaModel, Dataclass])
def test_var_create(type_: type[Base | Bare | SqlaModel | Dataclass]) -> None:
    my_object = type_()
    var = Var.create(my_object)
    assert var._var_type is type_
    assert isinstance(var, ObjectVar)
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
def test_guess(type_: type[Base | Bare | SqlaModel | Dataclass]) -> None:
    my_object = type_()
    var = Var.create(my_object)
    var = var.guess_type()
    assert var._var_type is type_
    assert isinstance(var, ObjectVar)
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


@pytest.mark.parametrize("type_", [Base, Bare, SqlaModel, Dataclass])
def test_hybrid_property_on_object_var(type_: GenericType) -> None:
    """A hybrid property on the underlying type resolves with the object var as ``self``.

    Args:
        type_: The object type to access the hybrid property on.
    """
    obj_var: ObjectVar = getattr(ObjectState, type_.__name__.lower())
    quantity = obj_var.quantity.to(NumberVar)

    # The simple hybrid property reuses its getter, with attribute access resolved
    # against the object var (e.g. `obj.doubled` behaves like `obj.quantity * 2`).
    assert str(Var.create(obj_var.doubled)) == str(Var.create(quantity * 2))

    # The custom `.var` function is used for the frontend (not the getter), so the
    # result matches `obj.quantity > 0` rather than the getter's `obj.quantity != 0`.
    assert str(Var.create(obj_var.is_nonzero)) == str(Var.create(quantity > 0))


def test_hybrid_property_on_object_var_issue_6617() -> None:
    """A hybrid property on a nested dataclass renders as if accessed on the state."""

    @dataclasses.dataclass
    class Info:
        a: str
        b: str

        @hybrid_property
        def a_b(self) -> str:
            return f"{self.a} - {self.b}"

    class InfoState(rx.State):
        info: Info = Info(a="a", b="b")

    assert str(Var.create(InfoState.info.a_b)) == str(
        Var.create(f"{InfoState.info.a} - {InfoState.info.b}")
    )


def test_hybrid_property_missing_attribute_still_raises() -> None:
    """Accessing a non-existent attribute on an object var still raises VarAttributeError."""
    with pytest.raises(VarAttributeError):
        _ = ObjectState.dataclass.does_not_exist


def test_hybrid_property_class_access_on_non_state_returns_descriptor() -> None:
    """Class-level access on a non-state (not via an object var) returns the descriptor.

    Only a state exposes a hybrid property as a frontend var at the class level, since
    its class attributes are vars. On a plain class accessed directly there is no var
    context, so it behaves like a normal property and returns the descriptor itself.
    """
    from reflex_base.vars.hybrid_property import HybridProperty

    @dataclasses.dataclass
    class Info:
        a: str
        b: str

        @hybrid_property
        def a_b(self) -> str:
            return f"{self.a} - {self.b}"

    # Direct class-level access yields the descriptor, not a var or a default-based value.
    assert isinstance(Info.a_b, HybridProperty)
    # Instance access still returns the computed backend value.
    assert Info(a="1", b="2").a_b == "1 - 2"


def test_hybrid_property_class_access_on_state_returns_var() -> None:
    """Class-level access on a state still resolves to a frontend var (not the descriptor)."""
    from reflex_base.vars.hybrid_property import HybridProperty

    class HybridState(rx.State):
        value: str = "v"

        @hybrid_property
        def shout(self) -> str:
            return self.value

    assert not isinstance(HybridState.shout, HybridProperty)
    assert isinstance(Var.create(HybridState.shout), Var)


def test_typing() -> None:
    # Bare
    var = ObjectState.bare.to(ObjectVar)
    _ = assert_type(var, ObjectVar[Bare])

    # Base
    var = ObjectState.base
    _ = assert_type(var, ObjectVar[Base])
    optional_var = ObjectState.base_optional
    _ = assert_type(optional_var, ObjectVar[Base])
    list_var = ObjectState.base_list
    _ = assert_type(list_var, ArrayVar[Sequence[Base]])
    list_var_0 = list_var[0]
    _ = assert_type(list_var_0, ObjectVar[Base])

    # Sqla
    var = ObjectState.sqlamodel
    _ = assert_type(var, ObjectVar[SqlaModel])
    optional_var = ObjectState.sqlamodel_optional
    _ = assert_type(optional_var, ObjectVar[SqlaModel])
    list_var = ObjectState.base_list
    _ = assert_type(list_var, ArrayVar[Sequence[Base]])
    list_var_0 = list_var[0]
    _ = assert_type(list_var_0, ObjectVar[Base])

    # Dataclass
    var = ObjectState.dataclass
    _ = assert_type(var, ObjectVar[Dataclass])
    optional_var = ObjectState.dataclass_optional
    _ = assert_type(optional_var, ObjectVar[Dataclass])
    list_var = ObjectState.base_list
    _ = assert_type(list_var, ArrayVar[Sequence[Base]])
    list_var_0 = list_var[0]
    _ = assert_type(list_var_0, ObjectVar[Base])


def test_rest_prop_merge_with_dict_preserves_type_and_spreads():
    """`RestProp.merge` accepts a dict, spreads both, and stays a RestProp.

    The result must remain a `RestProp` so a memo body can keep forwarding it
    (e.g. `rest.merge({...})` passed positionally still lifts to a `{...}` spread).
    """
    rest = RestProp(_js_expr="rest", _var_type=dict[str, Any])

    # A plain mapping merges like an object var (the signature accepts Mapping).
    merged = rest.merge({"color": "red"})

    assert isinstance(merged, RestProp)
    assert merged._var_type == dict[str, Any]
    assert str(merged) == '({...rest, ...({ ["color"] : "red" })})'


def test_rest_prop_merge_with_object_var():
    """`RestProp.merge` spreads another object Var after the rest props."""
    rest = RestProp(_js_expr="rest", _var_type=dict[str, Any])
    other = Var(_js_expr="extra", _var_type=dict).to(ObjectVar)

    merged = rest.merge(other)

    assert isinstance(merged, RestProp)
    assert str(merged) == "({...rest, ...extra})"


def test_rest_prop_merge_propagates_var_data():
    """`RestProp.merge` carries the merged object's VarData (deps/imports)."""
    rest = RestProp(_js_expr="rest", _var_type=dict[str, Any])
    other = Var(
        _js_expr="extra",
        _var_type=dict,
        _var_data=VarData(imports={"some-lib": [ImportVar(tag="thing")]}),
    ).to(ObjectVar)

    merged = rest.merge(other)

    var_data = merged._get_all_var_data()
    assert var_data is not None
    assert "some-lib" in dict(var_data.imports)
