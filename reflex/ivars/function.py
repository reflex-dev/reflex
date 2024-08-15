"""Immutable function vars."""

from __future__ import annotations

import dataclasses
import sys
from functools import cached_property
from typing import Any, Callable, Optional, Tuple, Type, Union

from reflex.utils.types import GenericType
from reflex.vars import ImmutableVarData, Var, VarData

from .base import CachedVarOperation, ImmutableVar, LiteralVar


class FunctionVar(ImmutableVar[Callable]):
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
            VarOperationCall.create(self, *args, ImmutableVar.create_safe("...args")),
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
            _var_name=func,
            _var_type=_var_type,
            _var_data=ImmutableVarData.merge(_var_data),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class VarOperationCall(CachedVarOperation, ImmutableVar):
    """Base class for immutable vars that are the result of a function call."""

    _func: Optional[FunctionVar] = dataclasses.field(default=None)
    _args: Tuple[Union[Var, Any], ...] = dataclasses.field(default_factory=tuple)

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._func)}({', '.join([str(LiteralVar.create(arg)) for arg in self._args])}))"

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
            _var_name="",
            _var_type=_var_type,
            _var_data=ImmutableVarData.merge(_var_data),
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

    @cached_property
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
            _var_name="",
            _var_type=_var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _args_names=args_names,
            _return_expr=return_expr,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToFunctionOperation(CachedVarOperation, FunctionVar):
    """Base class of converting a var to a function."""

    _original_var: Var = dataclasses.field(
        default_factory=lambda: LiteralVar.create(None)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return str(self._original_var)

    @classmethod
    def create(
        cls,
        original_var: Var,
        _var_type: GenericType = Callable,
        _var_data: VarData | None = None,
    ) -> ToFunctionOperation:
        """Create a new function var.

        Args:
            original_var: The original var to convert to a function.
            _var_type: The type of the function.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The function var.
        """
        return cls(
            _var_name="",
            _var_type=_var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _original_var=original_var,
        )


JSON_STRINGIFY = FunctionStringVar.create("JSON.stringify")
