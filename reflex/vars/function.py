"""Immutable function vars."""

from __future__ import annotations

import dataclasses
import sys
from typing import Any, Callable, Optional, Sequence, Tuple, Type, Union

from reflex.utils import format
from reflex.utils.types import GenericType

from .base import CachedVarOperation, LiteralVar, Var, VarData, cached_property_no_lock


class FunctionVar(Var[Callable], python_types=Callable):
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


@dataclasses.dataclass(frozen=True)
class DestructuredArg:
    """Class for destructured arguments."""

    fields: Tuple[str, ...] = tuple()
    rest: Optional[str] = None

    def to_javascript(self) -> str:
        """Convert the destructured argument to JavaScript.

        Returns:
            The destructured argument in JavaScript.
        """
        return format.wrap(
            ", ".join(self.fields) + (f", ...{self.rest}" if self.rest else ""),
            "{",
            "}",
        )


@dataclasses.dataclass(
    frozen=True,
)
class FunctionArgs:
    """Class for function arguments."""

    args: Tuple[Union[str, DestructuredArg], ...] = tuple()
    rest: Optional[str] = None


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArgsFunctionOperation(CachedVarOperation, FunctionVar):
    """Base class for immutable function defined via arguments and return expression."""

    _args: FunctionArgs = dataclasses.field(default_factory=FunctionArgs)
    _return_expr: Union[Var, Any] = dataclasses.field(default=None)
    _explicit_return: bool = dataclasses.field(default=False)

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        arg_names_str = ", ".join(
            [
                arg if isinstance(arg, str) else arg.to_javascript()
                for arg in self._args.args
            ]
        ) + (f", ...{self._args.rest}" if self._args.rest else "")

        return_expr_str = str(LiteralVar.create(self._return_expr))

        # Wrap return expression in curly braces if explicit return syntax is used.
        return_expr_str_wrapped = (
            format.wrap(return_expr_str, "{", "}")
            if self._explicit_return
            else return_expr_str
        )

        return f"(({arg_names_str}) => {return_expr_str_wrapped})"

    @classmethod
    def create(
        cls,
        args_names: Sequence[Union[str, DestructuredArg]],
        return_expr: Var | Any,
        rest: str | None = None,
        explicit_return: bool = False,
        _var_type: GenericType = Callable,
        _var_data: VarData | None = None,
    ) -> ArgsFunctionOperation:
        """Create a new function var.

        Args:
            args_names: The names of the arguments.
            return_expr: The return expression of the function.
            rest: The name of the rest argument.
            explicit_return: Whether to use explicit return syntax.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The function var.
        """
        return cls(
            _js_expr="",
            _var_type=_var_type,
            _var_data=_var_data,
            _args=FunctionArgs(args=tuple(args_names), rest=rest),
            _return_expr=return_expr,
            _explicit_return=explicit_return,
        )


JSON_STRINGIFY = FunctionStringVar.create("JSON.stringify")
ARRAY_ISARRAY = FunctionStringVar.create("Array.isArray")
PROTOTYPE_TO_STRING = FunctionStringVar.create(
    "((__to_string) => __to_string.toString())"
)
