"""Immutable function vars."""

from __future__ import annotations

import dataclasses
import sys
from functools import cached_property
from typing import Any, Callable, Optional, Tuple, Type, Union

from reflex.experimental.vars.base import ImmutableVar, LiteralVar
from reflex.vars import ImmutableVarData, Var, VarData


class FunctionVar(ImmutableVar[Callable]):
    """Base class for immutable function vars."""

    def __call__(self, *args: Var | Any) -> ArgsFunctionOperation:
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

    def call(self, *args: Var | Any) -> VarOperationCall:
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
            _var_type=Any,
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


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToFunctionOperation(FunctionVar):
    """Base class of converting a var to a function."""

    _original_var: Var = dataclasses.field(
        default_factory=lambda: LiteralVar.create(None)
    )

    def __init__(
        self,
        original_var: Var,
        _var_type: Type[Callable] = Callable,
        _var_data: VarData | None = None,
    ) -> None:
        """Initialize the function with arguments var.

        Args:
            original_var: The original var to convert to a function.
            _var_type: The type of the function.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ToFunctionOperation, self).__init__(
            _var_name=f"",
            _var_type=_var_type,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_original_var", original_var)
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
        return str(self._original_var)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self._original_var._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data
