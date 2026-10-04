"""Fields keep their value types: in defaults without the missing sentinel, and on class access."""

import dataclasses
from dataclasses import MISSING

from reflex_base.components.field import BaseField
from reflex_base.utils.compat import MISSING_TYPE
from reflex_base.vars.base import Field, field
from reflex_base.vars.object import ObjectVar
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing_extensions import assert_type

from reflex.state import State


def check_missing_default(value: int | MISSING_TYPE = MISSING) -> None:
    """Check that excluding MISSING narrows a field default to its value type.

    Args:
        value: A field default or the missing sentinel.
    """
    if value is not MISSING:
        assert_type(value, int)
        assert_type(BaseField(default=value).default_value(), int)
        assert_type(field(default=value), Field[int])
        assert_type(field(default=value, is_var=False), int)


class _Base(DeclarativeBase):
    pass


class _Model(_Base):
    __tablename__ = "type_checking_model"

    id: Mapped[int] = mapped_column(primary_key=True)


@dataclasses.dataclass
class _Data:
    value: int


class _ObjectFieldState(State):
    model: Field[_Model] = field(default_factory=lambda: _Model(id=0))
    optional_model: Field[_Model | None] = field(default=None)
    data: Field[_Data] = field(default_factory=lambda: _Data(value=0))
    optional_data: Field[_Data | None] = field(default=None)
    mapping: Field[dict[str, int]] = field(default_factory=dict)
    optional_mapping: Field[dict[str, int] | None] = field(default=None)


# An optional object field reads as the Var of the object on the class, the same
# as a required one: the optional `self` overload has to be tried first, or a
# checker may solve the type variable, whose bound admits `None`, to the union.
assert_type(_ObjectFieldState.model, ObjectVar[_Model])
assert_type(_ObjectFieldState.optional_model, ObjectVar[_Model])
assert_type(_ObjectFieldState.data, ObjectVar[_Data])
assert_type(_ObjectFieldState.optional_data, ObjectVar[_Data])
assert_type(_ObjectFieldState.mapping, ObjectVar[dict[str, int]])
assert_type(_ObjectFieldState.optional_mapping, ObjectVar[dict[str, int]])
