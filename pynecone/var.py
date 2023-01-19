"""Define a state var."""
from __future__ import annotations

import json
from abc import ABC
from typing import _GenericAlias  # type: ignore
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Type, Union

from plotly.graph_objects import Figure
from plotly.io import to_json
from pydantic.fields import ModelField

from pynecone import constants, utils
from pynecone.base import Base

if TYPE_CHECKING:
    from pynecone.state import State


class Var(ABC):
    """An abstract var."""

    # The name of the var.
    name: str

    # The type of the var.
    type_: Type

    # The name of the enclosing state.
    state: str = ""

    # Whether this is a local javascript variable.
    is_local: bool = False

    # Whether the var is a string literal.
    is_string: bool = False

    @classmethod
    def create(
        cls, value: Any, is_local: bool = True, is_string: bool = False
    ) -> Optional[Var]:
        """Create a var from a value.

        Args:
            value: The value to create the var from.
            is_local: Whether the var is local.
            is_string: Whether the var is a string literal.

        Returns:
            The var.
        """
        # Check for none values.
        if value is None:
            return None

        # If the value is already a var, do nothing.
        if isinstance(value, Var):
            return value

        type_ = type(value)

        # Special case for plotly figures.
        if isinstance(value, Figure):
            value = json.loads(to_json(value))["data"]
            type_ = Figure

        name = json.dumps(value) if not isinstance(value, str) else value

        return BaseVar(name=name, type_=type_, is_local=is_local, is_string=is_string)

    @classmethod
    def __class_getitem__(cls, type_: str) -> _GenericAlias:
        """Get a typed var.

        Args:
            type_: The type of the var.

        Returns:
            The var class item.
        """
        return _GenericAlias(cls, type_)

    def equals(self, other: Var) -> bool:
        """Check if two vars are equal.

        Args:
            other: The other var to compare.

        Returns:
            Whether the vars are equal.
        """
        return (
            self.name == other.name
            and self.type_ == other.type_
            and self.state == other.state
            and self.is_local == other.is_local
        )

    def to_string(self) -> Var:
        """Convert a var to a string.

        Returns:
            The stringified var.
        """
        return self.operation(fn="JSON.stringify")

    def __hash__(self) -> int:
        """Define a hash function for a var.

        Returns:
            The hash of the var.
        """
        return hash((self.name, str(self.type_)))

    def __str__(self) -> str:
        """Wrap the var so it can be used in templates.

        Returns:
            The wrapped var, i.e. {state.var}.
        """
        if self.is_local:
            out = self.full_name
        else:
            out = utils.wrap(self.full_name, "{")
        if self.is_string:
            out = utils.format_string(out)
        return out

    def __getitem__(self, i: Any) -> Var:
        """Index into a var.

        Args:
            i: The index to index into.

        Returns:
            The indexed var.

        Raises:
            TypeError: If the var is not indexable.
        """
        # Indexing is only supported for lists, dicts, and dataframes.
        if not (
            utils._issubclass(self.type_, Union[List, Dict])
            or utils.is_dataframe(self.type_)
        ):
            raise TypeError(
                f"Var {self.name} of type {self.type_} does not support indexing."
            )

        # The type of the indexed var.
        type_ = Any

        # Convert any vars to local vars.
        if isinstance(i, Var):
            i = BaseVar(name=i.name, type_=i.type_, state=i.state, is_local=True)

        # Handle list indexing.
        if utils._issubclass(self.type_, List):
            # List indices must be ints, slices, or vars.
            if not isinstance(i, utils.get_args(Union[int, slice, Var])):
                raise TypeError("Index must be an integer.")

            # Handle slices first.
            if isinstance(i, slice):
                # Get the start and stop indices.
                start = i.start or 0
                stop = i.stop or "undefined"

                # Use the slice function.
                return BaseVar(
                    name=f"{self.name}.slice({start}, {stop})",
                    type_=self.type_,
                    state=self.state,
                )

            # Get the type of the indexed var.
            if utils.is_generic_alias(self.type_):
                type_ = utils.get_args(self.type_)[0]
            else:
                type_ = Any

            # Use `at` to support negative indices.
            return BaseVar(
                name=f"{self.name}.at({i})",
                type_=type_,
                state=self.state,
            )

        # Dictionary / dataframe indexing.
        # Get the type of the indexed var.
        if isinstance(i, str):
            i = utils.wrap(i, '"')
        if utils.is_generic_alias(self.type_):
            type_ = utils.get_args(self.type_)[1]
        else:
            type_ = Any

        # Use normal indexing here.
        return BaseVar(
            name=f"{self.name}[{i}]",
            type_=type_,
            state=self.state,
        )

    def __getattribute__(self, name: str) -> Var:
        """Get a var attribute.

        Args:
            name: The name of the attribute.

        Returns:
            The var attribute.

        Raises:
            Exception: If the attribute is not found.
        """
        try:
            return super().__getattribute__(name)
        except Exception as e:
            # Check if the attribute is one of the class fields.
            if (
                not name.startswith("_")
                and hasattr(self.type_, "__fields__")
                and name in self.type_.__fields__
            ):
                type_ = self.type_.__fields__[name].outer_type_
                if isinstance(type_, ModelField):
                    type_ = type_.type_
                return BaseVar(
                    name=f"{self.name}.{name}",
                    type_=type_,
                    state=self.state,
                )
            raise e

    def operation(
        self,
        op: str = "",
        other: Optional[Var] = None,
        type_: Optional[Type] = None,
        flip: bool = False,
        fn: Optional[str] = None,
    ) -> Var:
        """Perform an operation on a var.

        Args:
            op: The operation to perform.
            other: The other var to perform the operation on.
            type_: The type of the operation result.
            flip: Whether to flip the order of the operation.
            fn: A function to apply to the operation.

        Returns:
            The operation result.
        """
        # Wrap strings in quotes.
        if isinstance(other, str):
            other = Var.create(json.dumps(other))
        else:
            other = Var.create(other)
        if type_ is None:
            type_ = self.type_
        if other is None:
            name = f"{op}{self.full_name}"
        else:
            props = (self, other) if not flip else (other, self)
            name = f"{props[0].full_name} {op} {props[1].full_name}"
            if fn is None:
                name = utils.wrap(name, "(")
        if fn is not None:
            name = f"{fn}({name})"
        return BaseVar(
            name=name,
            type_=type_,
        )

    def compare(self, op: str, other: Var) -> Var:
        """Compare two vars with inequalities.

        Args:
            op: The comparison operator.
            other: The other var to compare with.

        Returns:
            The comparison result.
        """
        return self.operation(op, other, bool)

    def __invert__(self) -> Var:
        """Invert a var.

        Returns:
            The inverted var.
        """
        return self.operation("!", type_=bool)

    def __neg__(self) -> Var:
        """Negate a var.

        Returns:
            The negated var.
        """
        return self.operation(fn="-")

    def __abs__(self) -> Var:
        """Get the absolute value of a var.

        Returns:
            A var with the absolute value.
        """
        return self.operation(fn="Math.abs")

    def length(self) -> Var:
        """Get the length of a list var.

        Returns:
            A var with the absolute value.

        Raises:
            TypeError: If the var is not a list.
        """
        if not utils._issubclass(self.type_, List):
            raise TypeError(f"Cannot get length of non-list var {self}.")
        return BaseVar(
            name=f"{self.full_name}.length",
            type_=int,
        )

    def __eq__(self, other: Var) -> Var:
        """Perform an equality comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the equality comparison.
        """
        return self.compare("==", other)

    def __ne__(self, other: Var) -> Var:
        """Perform an inequality comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the inequality comparison.
        """
        return self.compare("!=", other)

    def __gt__(self, other: Var) -> Var:
        """Perform a greater than comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the greater than comparison.
        """
        return self.compare(">", other)

    def __ge__(self, other: Var) -> Var:
        """Perform a greater than or equal to comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the greater than or equal to comparison.
        """
        return self.compare(">=", other)

    def __lt__(self, other: Var) -> Var:
        """Perform a less than comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the less than comparison.
        """
        return self.compare("<", other)

    def __le__(self, other: Var) -> Var:
        """Perform a less than or equal to comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the less than or equal to comparison.
        """
        return self.compare("<=", other)

    def __add__(self, other: Var) -> Var:
        """Add two vars.

        Args:
            other: The other var to add.

        Returns:
            A var representing the sum.
        """
        return self.operation("+", other)

    def __radd__(self, other: Var) -> Var:
        """Add two vars.

        Args:
            other: The other var to add.

        Returns:
            A var representing the sum.
        """
        return self.operation("+", other, flip=True)

    def __sub__(self, other: Var) -> Var:
        """Subtract two vars.

        Args:
            other: The other var to subtract.

        Returns:
            A var representing the difference.
        """
        return self.operation("-", other)

    def __rsub__(self, other: Var) -> Var:
        """Subtract two vars.

        Args:
            other: The other var to subtract.

        Returns:
            A var representing the difference.
        """
        return self.operation("-", other, flip=True)

    def __mul__(self, other: Var) -> Var:
        """Multiply two vars.

        Args:
            other: The other var to multiply.

        Returns:
            A var representing the product.
        """
        return self.operation("*", other)

    def __rmul__(self, other: Var) -> Var:
        """Multiply two vars.

        Args:
            other: The other var to multiply.

        Returns:
            A var representing the product.
        """
        return self.operation("*", other, flip=True)

    def __pow__(self, other: Var) -> Var:
        """Raise a var to a power.

        Args:
            other: The power to raise to.

        Returns:
            A var representing the power.
        """
        return self.operation(",", other, fn="Math.pow")

    def __rpow__(self, other: Var) -> Var:
        """Raise a var to a power.

        Args:
            other: The power to raise to.

        Returns:
            A var representing the power.
        """
        return self.operation(",", other, flip=True, fn="Math.pow")

    def __truediv__(self, other: Var) -> Var:
        """Divide two vars.

        Args:
            other: The other var to divide.

        Returns:
            A var representing the quotient.
        """
        return self.operation("/", other)

    def __rtruediv__(self, other: Var) -> Var:
        """Divide two vars.

        Args:
            other: The other var to divide.

        Returns:
            A var representing the quotient.
        """
        return self.operation("/", other, flip=True)

    def __floordiv__(self, other: Var) -> Var:
        """Divide two vars.

        Args:
            other: The other var to divide.

        Returns:
            A var representing the quotient.
        """
        return self.operation("/", other, fn="Math.floor")

    def __mod__(self, other: Var) -> Var:
        """Get the remainder of two vars.

        Args:
            other: The other var to divide.

        Returns:
            A var representing the remainder.
        """
        return self.operation("%", other)

    def __rmod__(self, other: Var) -> Var:
        """Get the remainder of two vars.

        Args:
            other: The other var to divide.

        Returns:
            A var representing the remainder.
        """
        return self.operation("%", other, flip=True)

    def __and__(self, other: Var) -> Var:
        """Perform a logical and.

        Args:
            other: The other var to perform the logical and with.

        Returns:
            A var representing the logical and.
        """
        return self.operation("&&", other)

    def __rand__(self, other: Var) -> Var:
        """Perform a logical and.

        Args:
            other: The other var to perform the logical and with.

        Returns:
            A var representing the logical and.
        """
        return self.operation("&&", other, flip=True)

    def __or__(self, other: Var) -> Var:
        """Perform a logical or.

        Args:
            other: The other var to perform the logical or with.

        Returns:
            A var representing the logical or.
        """
        return self.operation("||", other)

    def __ror__(self, other: Var) -> Var:
        """Perform a logical or.

        Args:
            other: The other var to perform the logical or with.

        Returns:
            A var representing the logical or.
        """
        return self.operation("||", other, flip=True)

    def foreach(self, fn: Callable) -> Var:
        """Return a list of components. after doing a foreach on this var.

        Args:
            fn: The function to call on each component.

        Returns:
            A var representing foreach operation.
        """
        arg = BaseVar(
            name=utils.get_unique_variable_name(),
            type_=self.type_,
        )
        return BaseVar(
            name=f"{self.full_name}.map(({arg.name}, i) => {fn(arg, key='i')})",
            type_=self.type_,
        )

    def to(self, type_: Type) -> Var:
        """Convert the type of the var.

        Args:
            type_: The type to convert to.

        Returns:
            The converted var.
        """
        return BaseVar(
            name=self.name,
            type_=type_,
            state=self.state,
            is_local=self.is_local,
        )

    @property
    def full_name(self) -> str:
        """Get the full name of the var.

        Returns:
            The full name of the var.
        """
        if self.state == "":
            return self.name
        return ".".join([self.state, self.name])

    def set_state(self, state: Type[State]) -> Any:
        """Set the state of the var.

        Args:
            state: The state to set.

        Returns:
            The var with the set state.
        """
        self.state = state.get_full_name()
        return self


class BaseVar(Var, Base):
    """A base (non-computed) var of the app state."""

    # The name of the var.
    name: str

    # The type of the var.
    type_: Any

    # The name of the enclosing state.
    state: str = ""

    # Whether this is a local javascript variable.
    is_local: bool = False

    # Whether this var is a raw string.
    is_string: bool = False

    def __hash__(self) -> int:
        """Define a hash function for a var.

        Returns:
            The hash of the var.
        """
        return hash((self.name, str(self.type_)))

    def get_default_value(self) -> Any:
        """Get the default value of the var.

        Returns:
            The default value of the var.
        """
        if utils.is_generic_alias(self.type_):
            type_ = self.type_.__origin__
        else:
            type_ = self.type_
        if issubclass(type_, str):
            return ""
        if issubclass(type_, utils.get_args(Union[int, float])):
            return 0
        if issubclass(type_, bool):
            return False
        if issubclass(type_, list):
            return []
        if issubclass(type_, dict):
            return {}
        if issubclass(type_, tuple):
            return ()
        if issubclass(type_, set):
            return set()
        return None

    def get_setter_name(self, include_state: bool = True) -> str:
        """Get the name of the var's generated setter function.

        Args:
            include_state: Whether to include the state name in the setter name.

        Returns:
            The name of the setter function.
        """
        setter = constants.SETTER_PREFIX + self.name
        if not include_state or self.state == "":
            return setter
        return ".".join((self.state, setter))

    def get_setter(self) -> Callable[[State, Any], None]:
        """Get the var's setter function.

        Returns:
            A function that that creates a setter for the var.
        """

        def setter(state: State, value: Any):
            """Get the setter for the var.

            Args:
                state: The state within which we add the setter function.
                value: The value to set.
            """
            setattr(state, self.name, value)

        setter.__qualname__ = self.get_setter_name()

        return setter

    def json(self) -> str:
        """Convert the object to a json string.

        Returns:
            The object as a json string.
        """
        return self.__config__.json_dumps(self.dict())


class ComputedVar(property, Var):
    """A field with computed getters."""

    @property
    def name(self) -> str:
        """Get the name of the var.

        Returns:
            The name of the var.
        """
        assert self.fget is not None, "Var must have a getter."
        return self.fget.__name__

    @property
    def type_(self):
        """Get the type of the var.

        Returns:
            The type of the var.
        """
        if "return" in self.fget.__annotations__:
            return self.fget.__annotations__["return"]
        return Any
