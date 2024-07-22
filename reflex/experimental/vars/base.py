"""Collection of base classes."""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from functools import cached_property
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union

from reflex import constants
from reflex.base import Base
from reflex.constants.base import REFLEX_VAR_CLOSING_TAG, REFLEX_VAR_OPENING_TAG
from reflex.utils import serializers, types
from reflex.utils.exceptions import VarTypeError
from reflex.vars import (
    ImmutableVarData,
    Var,
    VarData,
    _decode_var_immutable,
    _extract_var_data,
    _global_vars,
)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ImmutableVar(Var):
    """Base class for immutable vars."""

    # The name of the var.
    _var_name: str = dataclasses.field()

    # The type of the var.
    _var_type: Type = dataclasses.field(default=Any)

    # Extra metadata associated with the Var
    _var_data: Optional[ImmutableVarData] = dataclasses.field(default=None)

    def __str__(self) -> str:
        """String representation of the var. Guaranteed to be a valid Javascript expression.

        Returns:
            The name of the var.
        """
        return self._var_name

    @property
    def _var_is_local(self) -> bool:
        """Whether this is a local javascript variable.

        Returns:
            False
        """
        return False

    @property
    def _var_is_string(self) -> bool:
        """Whether the var is a string literal.

        Returns:
            False
        """
        return False

    @property
    def _var_full_name_needs_state_prefix(self) -> bool:
        """Whether the full name of the var needs a _var_state prefix.

        Returns:
            False
        """
        return False

    def __post_init__(self):
        """Post-initialize the var."""
        # Decode any inline Var markup and apply it to the instance
        _var_data, _var_name = _decode_var_immutable(self._var_name)
        if _var_data:
            self.__init__(
                _var_name,
                self._var_type,
                ImmutableVarData.merge(self._var_data, _var_data),
            )

    def __hash__(self) -> int:
        """Define a hash function for the var.

        Returns:
            The hash of the var.
        """
        return hash((self._var_name, self._var_type, self._var_data))

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._var_data

    def _replace(self, merge_var_data=None, **kwargs: Any):
        """Make a copy of this Var with updated fields.

        Args:
            merge_var_data: VarData to merge into the existing VarData.
            **kwargs: Var fields to update.

        Returns:
            A new ImmutableVar with the updated fields overwriting the corresponding fields in this Var.

        Raises:
            TypeError: If _var_is_local, _var_is_string, or _var_full_name_needs_state_prefix is not None.
        """
        if kwargs.get("_var_is_local", False) is not False:
            raise TypeError(
                "The _var_is_local argument is not supported for ImmutableVar."
            )

        if kwargs.get("_var_is_string", False) is not False:
            raise TypeError(
                "The _var_is_string argument is not supported for ImmutableVar."
            )

        if kwargs.get("_var_full_name_needs_state_prefix", False) is not False:
            raise TypeError(
                "The _var_full_name_needs_state_prefix argument is not supported for ImmutableVar."
            )

        field_values = dict(
            _var_name=kwargs.pop("_var_name", self._var_name),
            _var_type=kwargs.pop("_var_type", self._var_type),
            _var_data=ImmutableVarData.merge(
                kwargs.get("_var_data", self._var_data), merge_var_data
            ),
        )
        return type(self)(**field_values)

    @classmethod
    def create(
        cls,
        value: Any,
        _var_is_local: bool | None = None,
        _var_is_string: bool | None = None,
        _var_data: VarData | None = None,
    ) -> ImmutableVar | Var | None:
        """Create a var from a value.

        Args:
            value: The value to create the var from.
            _var_is_local: Whether the var is local. Deprecated.
            _var_is_string: Whether the var is a string literal. Deprecated.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.

        Raises:
            VarTypeError: If the value is JSON-unserializable.
            TypeError: If _var_is_local or _var_is_string is not None.
        """
        if _var_is_local is not None:
            raise TypeError(
                "The _var_is_local argument is not supported for ImmutableVar."
            )

        if _var_is_string is not None:
            raise TypeError(
                "The _var_is_string argument is not supported for ImmutableVar."
            )

        from reflex.utils import format

        # Check for none values.
        if value is None:
            return None

        # If the value is already a var, do nothing.
        if isinstance(value, Var):
            return value

        # Try to pull the imports and hooks from contained values.
        if not isinstance(value, str):
            _var_data = VarData.merge(*_extract_var_data(value), _var_data)

        # Try to serialize the value.
        type_ = type(value)
        if type_ in types.JSONType:
            name = value
        else:
            name, _serialized_type = serializers.serialize(value, get_type=True)
        if name is None:
            raise VarTypeError(
                f"No JSON serializer found for var {value} of type {type_}."
            )
        name = name if isinstance(name, str) else format.json_dumps(name)

        return cls(
            _var_name=name,
            _var_type=type_,
            _var_data=(
                ImmutableVarData(
                    state=_var_data.state,
                    imports=_var_data.imports,
                    hooks=_var_data.hooks,
                )
                if _var_data
                else None
            ),
        )

    @classmethod
    def create_safe(
        cls,
        value: Any,
        _var_is_local: bool | None = None,
        _var_is_string: bool | None = None,
        _var_data: VarData | None = None,
    ) -> Var | ImmutableVar:
        """Create a var from a value, asserting that it is not None.

        Args:
            value: The value to create the var from.
            _var_is_local: Whether the var is local. Deprecated.
            _var_is_string: Whether the var is a string literal. Deprecated.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        var = cls.create(
            value,
            _var_is_local=_var_is_local,
            _var_is_string=_var_is_string,
            _var_data=_var_data,
        )
        assert var is not None
        return var

    def __format__(self, format_spec: str) -> str:
        """Format the var into a Javascript equivalent to an f-string.

        Args:
            format_spec: The format specifier (Ignored for now).

        Returns:
            The formatted var.
        """
        hashed_var = hash(self)

        _global_vars[hashed_var] = self

        # Encode the _var_data into the formatted output for tracking purposes.
        return f"{REFLEX_VAR_OPENING_TAG}{hashed_var}{REFLEX_VAR_CLOSING_TAG}{self._var_name}"


class StringVar(ImmutableVar):
    """Base class for immutable string vars."""


class NumberVar(ImmutableVar):
    """Base class for immutable number vars."""


class BooleanVar(ImmutableVar):
    """Base class for immutable boolean vars."""


class ObjectVar(ImmutableVar):
    """Base class for immutable object vars."""


class ArrayVar(ImmutableVar):
    """Base class for immutable array vars."""


class FunctionVar(ImmutableVar):
    """Base class for immutable function vars."""

    def __call__(self, *args: Var) -> ArgsFunctionOperation:
        """Call the function with the given arguments.

        Args:
            *args: The arguments to call the function with.

        Returns:
            The function call operation.
        """
        return ArgsFunctionOperation(
            ("...args",),
            VarOperationCall(self, *args, ImmutableVar.create_safe("...args")),
        )

    def call(self, *args: Var) -> VarOperationCall:
        """Call the function with the given arguments.

        Args:
            *args: The arguments to call the function with.

        Returns:
            The function call operation.
        """
        return VarOperationCall(self, *args)


class FunctionStringVar(FunctionVar):
    """Base class for immutable function vars from a string."""

    def __init__(self, func: str, _var_data: VarData | None = None) -> None:
        """Initialize the function var.

        Args:
            func: The function to call.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(FunctionVar, self).__init__(
            _var_name=func,
            _var_type=Callable,
            _var_data=ImmutableVarData.merge(_var_data),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class VarOperationCall(ImmutableVar):
    """Base class for immutable vars that are the result of a function call."""

    _func: Optional[FunctionVar] = dataclasses.field(default=None)
    _args: Tuple[Union[Var, Any], ...] = dataclasses.field(default_factory=tuple)

    def __init__(
        self, func: FunctionVar, *args: Var | Any, _var_data: VarData | None = None
    ):
        """Initialize the function call var.

        Args:
            func: The function to call.
            *args: The arguments to call the function with.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(VarOperationCall, self).__init__(
            _var_name="",
            _var_type=Callable,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_func", func)
        object.__setattr__(self, "_args", args)
        object.__delattr__(self, "_var_name")

    def __getattr__(self, name):
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the var.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._func)}({', '.join([str(LiteralVar.create(arg)) for arg in self._args])}))"

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self._func._get_all_var_data() if self._func is not None else None,
            *[var._get_all_var_data() for var in self._args],
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __post_init__(self):
        """Post-initialize the var."""
        pass


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArgsFunctionOperation(FunctionVar):
    """Base class for immutable function defined via arguments and return expression."""

    _args_names: Tuple[str, ...] = dataclasses.field(default_factory=tuple)
    _return_expr: Union[Var, Any] = dataclasses.field(default=None)

    def __init__(
        self,
        args_names: Tuple[str, ...],
        return_expr: Var | Any,
        _var_data: VarData | None = None,
    ) -> None:
        """Initialize the function with arguments var.

        Args:
            args_names: The names of the arguments.
            return_expr: The return expression of the function.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ArgsFunctionOperation, self).__init__(
            _var_name=f"",
            _var_type=Callable,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_args_names", args_names)
        object.__setattr__(self, "_return_expr", return_expr)
        object.__delattr__(self, "_var_name")

    def __getattr__(self, name):
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the var.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"(({', '.join(self._args_names)}) => ({str(LiteralVar.create(self._return_expr))}))"

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self._return_expr._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __post_init__(self):
        """Post-initialize the var."""


class LiteralVar(ImmutableVar):
    """Base class for immutable literal vars."""

    @classmethod
    def create(
        cls,
        value: Any,
        _var_data: VarData | None = None,
    ) -> Var:
        """Create a var from a value.

        Args:
            value: The value to create the var from.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.

        Raises:
            TypeError: If the value is not a supported type for LiteralVar.
        """
        if isinstance(value, Var):
            if _var_data is None:
                return value
            return value._replace(merge_var_data=_var_data)

        if value is None:
            return ImmutableVar.create_safe("null", _var_data=_var_data)

        if isinstance(value, Base):
            return LiteralObjectVar(
                value.dict(), _var_type=type(value), _var_data=_var_data
            )

        constructor = type_mapping.get(type(value))

        if constructor is None:
            raise TypeError(f"Unsupported type {type(value)} for LiteralVar.")

        return constructor(value, _var_data=_var_data)

    def __post_init__(self):
        """Post-initialize the var."""


# Compile regex for finding reflex var tags.
_decode_var_pattern_re = (
    rf"{constants.REFLEX_VAR_OPENING_TAG}(.*?){constants.REFLEX_VAR_CLOSING_TAG}"
)
_decode_var_pattern = re.compile(_decode_var_pattern_re, flags=re.DOTALL)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralStringVar(LiteralVar):
    """Base class for immutable literal string vars."""

    _var_value: str = dataclasses.field(default="")

    def __init__(
        self,
        _var_value: str,
        _var_data: VarData | None = None,
    ):
        """Initialize the string var.

        Args:
            _var_value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LiteralStringVar, self).__init__(
            _var_name=f'"{_var_value}"',
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_var_value", _var_value)

    @classmethod
    def create(
        cls,
        value: str,
        _var_data: VarData | None = None,
    ) -> LiteralStringVar | ConcatVarOperation:
        """Create a var from a string value.

        Args:
            value: The value to create the var from.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        if REFLEX_VAR_OPENING_TAG in value:
            strings_and_vals: list[Var | str] = []
            offset = 0

            # Initialize some methods for reading json.
            var_data_config = VarData().__config__

            def json_loads(s):
                try:
                    return var_data_config.json_loads(s)
                except json.decoder.JSONDecodeError:
                    return var_data_config.json_loads(
                        var_data_config.json_loads(f'"{s}"')
                    )

            # Find all tags.
            while m := _decode_var_pattern.search(value):
                start, end = m.span()
                if start > 0:
                    strings_and_vals.append(value[:start])

                serialized_data = m.group(1)

                if serialized_data[1:].isnumeric():
                    # This is a global immutable var.
                    var = _global_vars[int(serialized_data)]
                    strings_and_vals.append(var)
                    value = value[(end + len(var._var_name)) :]
                else:
                    data = json_loads(serialized_data)
                    string_length = data.pop("string_length", None)
                    var_data = VarData.parse_obj(data)

                    # Use string length to compute positions of interpolations.
                    if string_length is not None:
                        realstart = start + offset
                        var_data.interpolations = [
                            (realstart, realstart + string_length)
                        ]
                        strings_and_vals.append(
                            ImmutableVar.create_safe(
                                value[end : (end + string_length)], _var_data=var_data
                            )
                        )
                        value = value[(end + string_length) :]

                offset += end - start

            if value:
                strings_and_vals.append(value)

            return ConcatVarOperation(*strings_and_vals, _var_data=_var_data)

        return LiteralStringVar(
            value,
            _var_data=_var_data,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ConcatVarOperation(StringVar):
    """Representing a concatenation of literal string vars."""

    _var_value: Tuple[Union[Var, str], ...] = dataclasses.field(default_factory=tuple)

    def __init__(self, *value: Var | str, _var_data: VarData | None = None):
        """Initialize the operation of concatenating literal string vars.

        Args:
            value: The values to concatenate.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ConcatVarOperation, self).__init__(
            _var_name="", _var_data=ImmutableVarData.merge(_var_data), _var_type=str
        )
        object.__setattr__(self, "_var_value", value)
        object.__delattr__(self, "_var_name")

    def __getattr__(self, name):
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the var.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return (
            "("
            + "+".join(
                [
                    str(element) if isinstance(element, Var) else f'"{element}"'
                    for element in self._var_value
                ]
            )
            + ")"
        )

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            *[
                var._get_all_var_data()
                for var in self._var_value
                if isinstance(var, Var)
            ],
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __post_init__(self):
        """Post-initialize the var."""
        pass


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralBooleanVar(LiteralVar):
    """Base class for immutable literal boolean vars."""

    _var_value: bool = dataclasses.field(default=False)

    def __init__(
        self,
        _var_value: bool,
        _var_data: VarData | None = None,
    ):
        """Initialize the boolean var.

        Args:
            _var_value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LiteralBooleanVar, self).__init__(
            _var_name="true" if _var_value else "false",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_var_value", _var_value)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralNumberVar(LiteralVar):
    """Base class for immutable literal number vars."""

    _var_value: float | int = dataclasses.field(default=0)

    def __init__(
        self,
        _var_value: float | int,
        _var_data: VarData | None = None,
    ):
        """Initialize the number var.

        Args:
            _var_value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LiteralNumberVar, self).__init__(
            _var_name=str(_var_value),
            _var_type=type(_var_value),
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_var_value", _var_value)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralObjectVar(LiteralVar):
    """Base class for immutable literal object vars."""

    _var_value: Dict[Union[Var, Any], Union[Var, Any]] = dataclasses.field(
        default_factory=dict
    )

    def __init__(
        self,
        _var_value: dict[Var | Any, Var | Any],
        _var_type: Type = dict,
        _var_data: VarData | None = None,
    ):
        """Initialize the object var.

        Args:
            _var_value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LiteralObjectVar, self).__init__(
            _var_name="",
            _var_type=_var_type,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(
            self,
            "_var_value",
            _var_value,
        )
        object.__delattr__(self, "_var_name")

    def __getattr__(self, name):
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the var.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return (
            "{ "
            + ", ".join(
                [
                    f"[{str(LiteralVar.create(key))}] : {str(LiteralVar.create(value))}"
                    for key, value in self._var_value.items()
                ]
            )
            + " }"
        )

    @cached_property
    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            *[
                value._get_all_var_data()
                for key, value in self._var_value
                if isinstance(value, Var)
            ],
            *[
                key._get_all_var_data()
                for key, value in self._var_value
                if isinstance(key, Var)
            ],
            self._var_data,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralArrayVar(LiteralVar):
    """Base class for immutable literal array vars."""

    _var_value: Union[
        List[Union[Var, Any]], Set[Union[Var, Any]], Tuple[Union[Var, Any], ...]
    ] = dataclasses.field(default_factory=list)

    def __init__(
        self,
        _var_value: list[Var | Any] | tuple[Var | Any] | set[Var | Any],
        _var_data: VarData | None = None,
    ):
        """Initialize the array var.

        Args:
            _var_value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LiteralArrayVar, self).__init__(
            _var_name="",
            _var_data=ImmutableVarData.merge(_var_data),
            _var_type=list,
        )
        object.__setattr__(self, "_var_value", _var_value)
        object.__delattr__(self, "_var_name")

    def __getattr__(self, name):
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the var.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return (
            "["
            + ", ".join(
                [str(LiteralVar.create(element)) for element in self._var_value]
            )
            + "]"
        )

    @cached_property
    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            *[
                var._get_all_var_data()
                for var in self._var_value
                if isinstance(var, Var)
            ],
            self._var_data,
        )


type_mapping = {
    str: LiteralStringVar,
    int: LiteralNumberVar,
    float: LiteralNumberVar,
    bool: LiteralBooleanVar,
    dict: LiteralObjectVar,
    list: LiteralArrayVar,
    tuple: LiteralArrayVar,
    set: LiteralArrayVar,
}
