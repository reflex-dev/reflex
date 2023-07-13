"""Define a state var."""
from __future__ import annotations

import contextlib
import dis
import json
import random
import string
from abc import ABC
from types import FunctionType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
    _GenericAlias,  # type: ignore
    cast,
    get_type_hints,
)

from plotly.graph_objects import Figure
from plotly.io import to_json
from pydantic.fields import ModelField

from reflex import constants
from reflex.base import Base
from reflex.utils import format, types

if TYPE_CHECKING:
    from reflex.state import State

# Set of unique variable names.
USED_VARIABLES = set()


def get_unique_variable_name() -> str:
    """Get a unique variable name.

    Returns:
        The unique variable name.
    """
    name = "".join([random.choice(string.ascii_lowercase) for _ in range(8)])
    if name not in USED_VARIABLES:
        USED_VARIABLES.add(name)
        return name
    return get_unique_variable_name()


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

        Raises:
            TypeError: If the value is JSON-unserializable.
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
            value = json.loads(to_json(value))["data"]  # type: ignore
            type_ = Figure

        if isinstance(value, dict):
            value = format.format_dict(value)

        try:
            name = value if isinstance(value, str) else json.dumps(value)
        except TypeError as e:
            raise TypeError(
                f"To create a Var must be Var or JSON-serializable. Got {value} of type {type(value)}."
            ) from e

        return BaseVar(name=name, type_=type_, is_local=is_local, is_string=is_string)

    @classmethod
    def create_safe(
        cls, value: Any, is_local: bool = True, is_string: bool = False
    ) -> Var:
        """Create a var from a value, guaranteeing that it is not None.

        Args:
            value: The value to create the var from.
            is_local: Whether the var is local.
            is_string: Whether the var is a string literal.

        Returns:
            The var.
        """
        var = cls.create(value, is_local=is_local, is_string=is_string)
        assert var is not None
        return var

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
        out = self.full_name if self.is_local else format.wrap(self.full_name, "{")
        if self.is_string:
            out = format.format_string(out)
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
        # Indexing is only supported for strings, lists, tuples, dicts, and dataframes.
        if not (
            types._issubclass(self.type_, Union[List, Dict, Tuple, str])
            or types.is_dataframe(self.type_)
        ):
            if self.type_ == Any:
                raise TypeError(
                    f"Could not index into var of type Any. (If you are trying to index into a state var, "
                    f"add the correct type annotation to the var.)"
                )
            raise TypeError(
                f"Var {self.name} of type {self.type_} does not support indexing."
            )

        # The type of the indexed var.
        type_ = Any

        # Convert any vars to local vars.
        if isinstance(i, Var):
            i = BaseVar(name=i.name, type_=i.type_, state=i.state, is_local=True)

        # Handle list/tuple/str indexing.
        if types._issubclass(self.type_, Union[List, Tuple, str]):
            # List/Tuple/String indices must be ints, slices, or vars.
            if (
                not isinstance(i, types.get_args(Union[int, slice, Var]))
                or isinstance(i, Var)
                and not i.type_ == int
            ):
                raise TypeError("Index must be an integer or an integer var.")

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
            type_ = (
                types.get_args(self.type_)[0]
                if types.is_generic_alias(self.type_)
                else Any
            )

            # Use `at` to support negative indices.
            return BaseVar(
                name=f"{self.name}.at({i})",
                type_=type_,
                state=self.state,
            )

        # Dictionary / dataframe indexing.
        # Tuples are currently not supported as indexes.
        if (
            (types._issubclass(self.type_, Dict) or types.is_dataframe(self.type_))
            and not isinstance(i, types.get_args(Union[int, str, float, Var]))
        ) or (
            isinstance(i, Var)
            and not types._issubclass(i.type_, types.get_args(Union[int, str, float]))
        ):
            raise TypeError(
                "Index must be one of the following types: int, str, int or str Var"
            )
        # Get the type of the indexed var.
        if isinstance(i, str):
            i = format.wrap(i, '"')
        type_ = (
            types.get_args(self.type_)[1] if types.is_generic_alias(self.type_) else Any
        )

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
            AttributeError: If the var is wrongly annotated or can't find attribute.
            TypeError: If an annotation to the var isn't provided.
        """
        try:
            return super().__getattribute__(name)
        except Exception as e:
            # Check if the attribute is one of the class fields.
            if not name.startswith("_"):
                if self.type_ == Any:
                    raise TypeError(
                        f"You must provide an annotation for the state var `{self.full_name}`. Annotation cannot be `{self.type_}`"
                    ) from None
                if hasattr(self.type_, "__fields__") and name in self.type_.__fields__:
                    type_ = self.type_.__fields__[name].outer_type_
                    if isinstance(type_, ModelField):
                        type_ = type_.type_
                    return BaseVar(
                        name=f"{self.name}.{name}",
                        type_=type_,
                        state=self.state,
                    )
            raise AttributeError(
                f"The State var `{self.full_name}` has no attribute '{name}' or may have been annotated "
                f"wrongly.\n"
                f"original message: {e.args[0]}"
            ) from e

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
            props = (other, self) if flip else (self, other)
            name = f"{props[0].full_name} {op} {props[1].full_name}"
            if fn is None:
                name = format.wrap(name, "(")
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
        if not types._issubclass(self.type_, List):
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
        return self.compare("===", other)

    def __ne__(self, other: Var) -> Var:
        """Perform an inequality comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the inequality comparison.
        """
        return self.compare("!==", other)

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
            name=get_unique_variable_name(),
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
        return self.name if self.state == "" else ".".join([self.state, self.name])

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

        Raises:
            ImportError: If the var is a dataframe and pandas is not installed.
        """
        type_ = (
            self.type_.__origin__ if types.is_generic_alias(self.type_) else self.type_
        )
        if issubclass(type_, str):
            return ""
        if issubclass(type_, types.get_args(Union[int, float])):
            return 0
        if issubclass(type_, bool):
            return False
        if issubclass(type_, list):
            return []
        if issubclass(type_, dict):
            return {}
        if issubclass(type_, tuple):
            return ()
        if types.is_dataframe(type_):
            try:
                import pandas as pd

                return pd.DataFrame()
            except ImportError as e:
                raise ImportError(
                    "Please install pandas to use dataframes in your app."
                ) from e
        return set() if issubclass(type_, set) else None

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


class ComputedVar(Var, property):
    """A field with computed getters."""

    # Whether to track dependencies and cache computed values
    cache: bool = False

    @property
    def name(self) -> str:
        """Get the name of the var.

        Returns:
            The name of the var.
        """
        assert self.fget is not None, "Var must have a getter."
        return self.fget.__name__

    @property
    def cache_attr(self) -> str:
        """Get the attribute used to cache the value on the instance.

        Returns:
            An attribute name.
        """
        return f"__cached_{self.name}"

    def __get__(self, instance, owner):
        """Get the ComputedVar value.

        If the value is already cached on the instance, return the cached value.

        Args:
            instance: the instance of the class accessing this computed var.
            owner: the class that this descriptor is attached to.

        Returns:
            The value of the var for the given instance.
        """
        if instance is None or not self.cache:
            return super().__get__(instance, owner)

        # handle caching
        if not hasattr(instance, self.cache_attr):
            setattr(instance, self.cache_attr, super().__get__(instance, owner))
        return getattr(instance, self.cache_attr)

    def deps(
        self,
        objclass: Type,
        obj: Optional[FunctionType] = None,
    ) -> Set[str]:
        """Determine var dependencies of this ComputedVar.

        Save references to attributes accessed on "self".  Recursively called
        when the function makes a method call on "self".

        Args:
            objclass: the class obj this ComputedVar is attached to.
            obj: the object to disassemble (defaults to the fget function).

        Returns:
            A set of variable names accessed by the given obj.
        """
        d = set()
        if obj is None:
            if self.fget is not None:
                obj = cast(FunctionType, self.fget)
            else:
                return set()
        with contextlib.suppress(AttributeError):
            # unbox functools.partial
            obj = cast(FunctionType, obj.func)  # type: ignore
        with contextlib.suppress(AttributeError):
            # unbox EventHandler
            obj = cast(FunctionType, obj.fn)  # type: ignore

        try:
            self_name = obj.__code__.co_varnames[0]
        except (AttributeError, IndexError):
            # cannot reference self if method takes no args
            return set()
        self_is_top_of_stack = False
        for instruction in dis.get_instructions(obj):
            if instruction.opname == "LOAD_FAST" and instruction.argval == self_name:
                self_is_top_of_stack = True
                continue
            if self_is_top_of_stack and instruction.opname == "LOAD_ATTR":
                d.add(instruction.argval)
            elif self_is_top_of_stack and instruction.opname == "LOAD_METHOD":
                d.update(
                    self.deps(
                        objclass=objclass,
                        obj=getattr(objclass, instruction.argval),
                    )
                )
            self_is_top_of_stack = False
        return d

    def mark_dirty(self, instance) -> None:
        """Mark this ComputedVar as dirty.

        Args:
            instance: the state instance that needs to recompute the value.
        """
        with contextlib.suppress(AttributeError):
            delattr(instance, self.cache_attr)

    @property
    def type_(self):
        """Get the type of the var.

        Returns:
            The type of the var.
        """
        hints = get_type_hints(self.fget)
        if "return" in hints:
            return hints["return"]
        return Any


def cached_var(fget: Callable[[Any], Any]) -> ComputedVar:
    """A field with computed getter that tracks other state dependencies.

    The cached_var will only be recalculated when other state vars that it
    depends on are modified.

    Args:
        fget: the function that calculates the variable value.

    Returns:
        ComputedVar that is recomputed when dependencies change.
    """
    cvar = ComputedVar(fget=fget)
    cvar.cache = True
    return cvar


class ReflexList(list):
    """A custom list that reflex can detect its mutation."""

    def __init__(
        self,
        original_list: List,
        reassign_field: Callable = lambda _field_name: None,
        field_name: str = "",
    ):
        """Initialize ReflexList.

        Args:
            original_list (List): The original list
            reassign_field (Callable):
                The method in the parent state to reassign the field.
                Default to be a no-op function
            field_name (str): the name of field in the parent state
        """
        self._reassign_field = lambda: reassign_field(field_name)

        super().__init__(original_list)

    def append(self, *args, **kwargs):
        """Append.

        Args:
            args: The args passed.
            kwargs: The kwargs passed.
        """
        super().append(*args, **kwargs)
        self._reassign_field()

    def __setitem__(self, *args, **kwargs):
        """Set item.

        Args:
            args: The args passed.
            kwargs: The kwargs passed.
        """
        super().__setitem__(*args, **kwargs)
        self._reassign_field()

    def __delitem__(self, *args, **kwargs):
        """Delete item.

        Args:
            args: The args passed.
            kwargs: The kwargs passed.
        """
        super().__delitem__(*args, **kwargs)
        self._reassign_field()

    def clear(self, *args, **kwargs):
        """Remove all item from the list.

        Args:
            args: The args passed.
            kwargs: The kwargs passed.
        """
        super().clear(*args, **kwargs)
        self._reassign_field()

    def extend(self, *args, **kwargs):
        """Add all item of a list to the end of the list.

        Args:
            args: The args passed.
            kwargs: The kwargs passed.
        """
        super().extend(*args, **kwargs)
        self._reassign_field() if hasattr(self, "_reassign_field") else None

    def pop(self, *args, **kwargs):
        """Remove an element.

        Args:
            args: The args passed.
            kwargs: The kwargs passed.
        """
        super().pop(*args, **kwargs)
        self._reassign_field()

    def remove(self, *args, **kwargs):
        """Remove an element.

        Args:
            args: The args passed.
            kwargs: The kwargs passed.
        """
        super().remove(*args, **kwargs)
        self._reassign_field()


class ReflexDict(dict):
    """A custom dict that reflex can detect its mutation."""

    def __init__(
        self,
        original_dict: Dict,
        reassign_field: Callable = lambda _field_name: None,
        field_name: str = "",
    ):
        """Initialize ReflexDict.

        Args:
            original_dict: The original dict
            reassign_field:
                The method in the parent state to reassign the field.
                Default to be a no-op function
            field_name: the name of field in the parent state
        """
        super().__init__(original_dict)
        self._reassign_field = lambda: reassign_field(field_name)

    def clear(self):
        """Remove all item from the list."""
        super().clear()

        self._reassign_field()

    def setdefault(self, *args, **kwargs):
        """Return value of key if or set default.

        Args:
            args: The args passed.
            kwargs: The kwargs passed.
        """
        super().setdefault(*args, **kwargs)
        self._reassign_field()

    def popitem(self):
        """Pop last item."""
        super().popitem()
        self._reassign_field()

    def pop(self, k, d=None):
        """Remove an element.

        Args:
            k: The args passed.
            d: The kwargs passed.
        """
        super().pop(k, d)
        self._reassign_field()

    def update(self, *args, **kwargs):
        """Update the dict with another dict.

        Args:
            args: The args passed.
            kwargs: The kwargs passed.
        """
        super().update(*args, **kwargs)
        self._reassign_field()

    def __setitem__(self, *args, **kwargs):
        """Set an item in the dict.

        Args:
            args: The args passed.
            kwargs: The kwargs passed.
        """
        super().__setitem__(*args, **kwargs)
        self._reassign_field() if hasattr(self, "_reassign_field") else None

    def __delitem__(self, *args, **kwargs):
        """Delete an item in the dict.

        Args:
            args: The args passed.
            kwargs: The kwargs passed.
        """
        super().__delitem__(*args, **kwargs)
        self._reassign_field()


class ImportVar(Base):
    """An import var."""

    # The name of the import tag.
    tag: Optional[str]

    # whether the import is default or named.
    is_default: Optional[bool] = False

    # The tag alias.
    alias: Optional[str] = None

    @property
    def name(self) -> str:
        """The name of the import.

        Returns:
            The name(tag name with alias) of tag.
        """
        return self.tag if not self.alias else " as ".join([self.tag, self.alias])  # type: ignore

    def __hash__(self) -> int:
        """Define a hash function for the import var.

        Returns:
            The hash of the var.
        """
        return hash((self.tag, self.is_default, self.alias))


def get_local_storage(key: Optional[Union[Var, str]] = None) -> BaseVar:
    """Provide a base var as payload to get local storage item(s).

    Args:
        key: Key to obtain value in the local storage.

    Returns:
        A BaseVar of the local storage method/function to call.

    Raises:
        TypeError:  if the wrong key type is provided.
    """
    if key:
        if not (isinstance(key, Var) and key.type_ == str) and not isinstance(key, str):
            type_ = type(key) if not isinstance(key, Var) else key.type_
            raise TypeError(
                f"Local storage keys can only be of type `str` or `var` of type `str`. Got `{type_}` instead."
            )
        key = key.full_name if isinstance(key, Var) else format.wrap(key, "'")
        return BaseVar(name=f"localStorage.getItem({key})", type_=str)
    return BaseVar(name="getAllLocalStorageItems()", type_=Dict)
