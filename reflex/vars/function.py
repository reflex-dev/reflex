"""Immutable function vars."""

from __future__ import annotations

import dataclasses
import sys
from typing import Any, Callable, ClassVar, Optional, Tuple, Type, Union

from reflex.utils.types import GenericType

from .base import (
    CachedVarOperation,
    LiteralVar,
    ToOperation,
    Var,
    VarData,
    cached_property_no_lock,
)


class FunctionVar(Var[Callable]):
    """Base class for immutable function vars."""

    def __call__(self, *args: Var | Any) -> ArgsFunctionOperation:
        """Call the function with the given arguments.

        Args:
            *args: The arguments to call the function with.

        Returns:
            The function call operation.
        """
        return ArgsFunctionOperation.create(
            ("...args",),
            VarOperationCall.create(self, *args, Var(_js_expr="...args")),
        )

    def call(self, *args: Var | Any) -> VarOperationCall:
        """Call the function with the given arguments.

        Args:
            *args: The arguments to call the function with.

        Returns:
            The function call operation.
        """
        return VarOperationCall.create(self, *args)


class FunctionStringVar(FunctionVar):
    """Base class for immutable function vars from a string."""

    @classmethod
    def create(
        cls,
        func: str,
        _var_type: Type[Callable] = Callable,
        _var_data: VarData | None = None,
    ) -> FunctionStringVar:
        """Create a new function var from a string.

        Args:
            func: The function to call.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The function var.
        """
        return cls(
            _js_expr=func,
            _var_type=_var_type,
            _var_data=_var_data,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class VarOperationCall(CachedVarOperation, Var):
    """Base class for immutable vars that are the result of a function call."""

    _func: Optional[FunctionVar] = dataclasses.field(default=None)
    _args: Tuple[Union[Var, Any], ...] = dataclasses.field(default_factory=tuple)

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._func)}({', '.join([str(LiteralVar.create(arg)) for arg in self._args])}))"

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get all the var data associated with the var.

        Returns:
            All the var data associated with the var.
        """
        return VarData.merge(
            self._func._get_all_var_data() if self._func is not None else None,
            *[LiteralVar.create(arg)._get_all_var_data() for arg in self._args],
            self._var_data,
        )

    @classmethod
    def create(
        cls,
        func: FunctionVar,
        *args: Var | Any,
        _var_type: GenericType = Any,
        _var_data: VarData | None = None,
    ) -> VarOperationCall:
        """Create a new function call var.

        Args:
            func: The function to call.
            *args: The arguments to call the function with.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The function call var.
        """
        return cls(
            _js_expr="",
            _var_type=_var_type,
            _var_data=_var_data,
            _func=func,
            _args=args,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArgsFunctionOperation(CachedVarOperation, FunctionVar):
    """Base class for immutable function defined via arguments and return expression."""

    _args_names: Tuple[str, ...] = dataclasses.field(default_factory=tuple)
    _return_expr: Union[Var, Any] = dataclasses.field(default=None)

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"(({', '.join(self._args_names)}) => ({str(LiteralVar.create(self._return_expr))}))"

    @classmethod
    def create(
        cls,
        args_names: Tuple[str, ...],
        return_expr: Var | Any,
        _var_type: GenericType = Callable,
        _var_data: VarData | None = None,
    ) -> ArgsFunctionOperation:
        """Create a new function var.

        Args:
            args_names: The names of the arguments.
            return_expr: The return expression of the function.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The function var.
        """
        return cls(
            _js_expr="",
            _var_type=_var_type,
            _var_data=_var_data,
            _args_names=args_names,
            _return_expr=return_expr,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToFunctionOperation(ToOperation, FunctionVar):
    """Base class of converting a var to a function."""

    _original: Var = dataclasses.field(default_factory=lambda: LiteralVar.create(None))

    _default_var_type: ClassVar[GenericType] = Callable


JSON_STRINGIFY = FunctionStringVar.create("JSON.stringify")
