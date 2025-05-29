"""Collection of base classes."""

from __future__ import annotations

import contextlib
import dataclasses
import dis
import enum
import inspect
from types import CellType, CodeType, FunctionType
from typing import TYPE_CHECKING, Any, ClassVar, cast

from reflex.utils.exceptions import VarValueError

if TYPE_CHECKING:
    from reflex.state import BaseState

    from .base import Var


CellEmpty = object()


def get_cell_value(cell: CellType) -> Any:
    """Get the value of a cell object.

    Args:
        cell: The cell object to get the value from. (func.__closure__ objects)

    Returns:
        The value from the cell or CellEmpty if a ValueError is raised.
    """
    try:
        return cell.cell_contents
    except ValueError:
        return CellEmpty


class ScanStatus(enum.Enum):
    """State of the dis instruction scanning loop."""

    SCANNING = enum.auto()
    GETTING_ATTR = enum.auto()
    GETTING_STATE = enum.auto()
    GETTING_VAR = enum.auto()


@dataclasses.dataclass
class DependencyTracker:
    """State machine for identifying state attributes that are accessed by a function."""

    func: FunctionType | CodeType = dataclasses.field()
    state_cls: type[BaseState] = dataclasses.field()

    dependencies: dict[str, set[str]] = dataclasses.field(default_factory=dict)

    scan_status: ScanStatus = dataclasses.field(default=ScanStatus.SCANNING)
    top_of_stack: str | None = dataclasses.field(default=None)

    tracked_locals: dict[str, type[BaseState]] = dataclasses.field(default_factory=dict)

    _getting_state_class: type[BaseState] | None = dataclasses.field(default=None)
    _getting_var_instructions: list[dis.Instruction] = dataclasses.field(
        default_factory=list
    )

    INVALID_NAMES: ClassVar[list[str]] = ["parent_state", "substates", "get_substate"]

    def __post_init__(self):
        """After initializing, populate the dependencies dict."""
        with contextlib.suppress(AttributeError):
            # unbox functools.partial
            self.func = cast(FunctionType, self.func.func)  # pyright: ignore[reportAttributeAccessIssue]
        with contextlib.suppress(AttributeError):
            # unbox EventHandler
            self.func = cast(FunctionType, self.func.fn)  # pyright: ignore[reportAttributeAccessIssue,reportFunctionMemberAccess]

        if isinstance(self.func, FunctionType):
            with contextlib.suppress(AttributeError, IndexError):
                # the first argument to the function is the name of "self" arg
                self.tracked_locals[self.func.__code__.co_varnames[0]] = self.state_cls

        self._populate_dependencies()

    def _merge_deps(self, tracker: DependencyTracker) -> None:
        """Merge dependencies from another DependencyTracker.

        Args:
            tracker: The DependencyTracker to merge dependencies from.
        """
        for state_name, dep_name in tracker.dependencies.items():
            self.dependencies.setdefault(state_name, set()).update(dep_name)

    def load_attr_or_method(self, instruction: dis.Instruction) -> None:
        """Handle loading an attribute or method from the object on top of the stack.

        This method directly tracks attributes and recursively merges
        dependencies from analyzing the dependencies of any methods called.

        Args:
            instruction: The dis instruction to process.

        Raises:
            VarValueError: if the attribute is an disallowed name.
        """
        from .base import ComputedVar

        if instruction.argval in self.INVALID_NAMES:
            msg = f"Cached var {self!s} cannot access arbitrary state via `{instruction.argval}`."
            raise VarValueError(msg)
        if instruction.argval == "get_state":
            # Special case: arbitrary state access requested.
            self.scan_status = ScanStatus.GETTING_STATE
            return
        if instruction.argval == "get_var_value":
            # Special case: arbitrary var access requested.
            self.scan_status = ScanStatus.GETTING_VAR
            return

        # Reset status back to SCANNING after attribute is accessed.
        self.scan_status = ScanStatus.SCANNING
        if not self.top_of_stack:
            return
        target_state = self.tracked_locals[self.top_of_stack]
        try:
            ref_obj = getattr(target_state, instruction.argval)
        except AttributeError:
            # Not found on this state class, maybe it is a dynamic attribute that will be picked up later.
            ref_obj = None

        if isinstance(ref_obj, property) and not isinstance(ref_obj, ComputedVar):
            # recurse into property fget functions
            ref_obj = ref_obj.fget
        if callable(ref_obj):
            # recurse into callable attributes
            self._merge_deps(
                type(self)(func=cast(FunctionType, ref_obj), state_cls=target_state)
            )
        elif (
            instruction.argval in target_state.backend_vars
            or instruction.argval in target_state.vars
        ):
            # var access
            self.dependencies.setdefault(target_state.get_full_name(), set()).add(
                instruction.argval
            )

    def _get_globals(self) -> dict[str, Any]:
        """Get the globals of the function.

        Returns:
            The var names and values in the globals of the function.
        """
        if isinstance(self.func, CodeType):
            return {}
        return self.func.__globals__  # pyright: ignore[reportAttributeAccessIssue]

    def _get_closure(self) -> dict[str, Any]:
        """Get the closure of the function, with unbound values omitted.

        Returns:
            The var names and values in the closure of the function.
        """
        if isinstance(self.func, CodeType):
            return {}
        return {
            var_name: get_cell_value(cell)
            for var_name, cell in zip(
                self.func.__code__.co_freevars,  # pyright: ignore[reportAttributeAccessIssue]
                self.func.__closure__ or (),
                strict=False,
            )
            if get_cell_value(cell) is not CellEmpty
        }

    def handle_getting_state(self, instruction: dis.Instruction) -> None:
        """Handle bytecode analysis when `get_state` was called in the function.

        If the wrapped function is getting an arbitrary state and saving it to a
        local variable, this method associates the local variable name with the
        state class in self.tracked_locals.

        When an attribute/method is accessed on a tracked local, it will be
        associated with this state.

        Args:
            instruction: The dis instruction to process.

        Raises:
            VarValueError: if the state class cannot be determined from the instruction.
        """
        from reflex.state import BaseState

        if instruction.opname == "LOAD_FAST":
            msg = f"Dependency detection cannot identify get_state class from local var {instruction.argval}."
            raise VarValueError(msg)
        if isinstance(self.func, CodeType):
            msg = "Dependency detection cannot identify get_state class from a code object."
            raise VarValueError(msg)
        if instruction.opname == "LOAD_GLOBAL":
            # Special case: referencing state class from global scope.
            try:
                self._getting_state_class = self._get_globals()[instruction.argval]
            except (ValueError, KeyError) as ve:
                msg = f"Cached var {self!s} cannot access arbitrary state `{instruction.argval}`, not found in globals."
                raise VarValueError(msg) from ve
        elif instruction.opname == "LOAD_DEREF":
            # Special case: referencing state class from closure.
            try:
                self._getting_state_class = self._get_closure()[instruction.argval]
            except (ValueError, KeyError) as ve:
                msg = f"Cached var {self!s} cannot access arbitrary state `{instruction.argval}`, is it defined yet?"
                raise VarValueError(msg) from ve
        elif instruction.opname == "STORE_FAST":
            # Storing the result of get_state in a local variable.
            if not isinstance(self._getting_state_class, type) or not issubclass(
                self._getting_state_class, BaseState
            ):
                msg = f"Cached var {self!s} cannot determine dependencies in fetched state `{instruction.argval}`."
                raise VarValueError(msg)
            self.tracked_locals[instruction.argval] = self._getting_state_class
            self.scan_status = ScanStatus.SCANNING
            self._getting_state_class = None

    def _eval_var(self) -> Var:
        """Evaluate instructions from the wrapped function to get the Var object.

        Returns:
            The Var object.

        Raises:
            VarValueError: if the source code for the var cannot be determined.
        """
        # Get the original source code and eval it to get the Var.
        module = inspect.getmodule(self.func)
        positions0 = self._getting_var_instructions[0].positions
        positions1 = self._getting_var_instructions[-1].positions
        if module is None or positions0 is None or positions1 is None:
            msg = f"Cannot determine the source code for the var in {self.func!r}."
            raise VarValueError(msg)
        start_line = positions0.lineno
        start_column = positions0.col_offset
        end_line = positions1.end_lineno
        end_column = positions1.end_col_offset
        if (
            start_line is None
            or start_column is None
            or end_line is None
            or end_column is None
        ):
            msg = f"Cannot determine the source code for the var in {self.func!r}."
            raise VarValueError(msg)
        source = inspect.getsource(module).splitlines(True)[start_line - 1 : end_line]
        # Create a python source string snippet.
        if len(source) > 1:
            snipped_source = "".join(
                [
                    *source[0][start_column:],
                    *(source[1:-2] if len(source) > 2 else []),
                    *source[-1][: end_column - 1],
                ]
            )
        else:
            snipped_source = source[0][start_column : end_column - 1]
        # Evaluate the string in the context of the function's globals and closure.
        return eval(f"({snipped_source})", self._get_globals(), self._get_closure())

    def handle_getting_var(self, instruction: dis.Instruction) -> None:
        """Handle bytecode analysis when `get_var_value` was called in the function.

        This only really works if the expression passed to `get_var_value` is
        evaluable in the function's global scope or closure, so getting the var
        value from a var saved in a local variable or in the class instance is
        not possible.

        Args:
            instruction: The dis instruction to process.

        Raises:
            VarValueError: if the source code for the var cannot be determined.
        """
        if instruction.opname == "CALL" and self._getting_var_instructions:
            if self._getting_var_instructions:
                the_var = self._eval_var()
                the_var_data = the_var._get_all_var_data()
                if the_var_data is None:
                    msg = f"Cannot determine the source code for the var in {self.func!r}."
                    raise VarValueError(msg)
                self.dependencies.setdefault(the_var_data.state, set()).add(
                    the_var_data.field_name
                )
            self._getting_var_instructions.clear()
            self.scan_status = ScanStatus.SCANNING
        else:
            self._getting_var_instructions.append(instruction)

    def _populate_dependencies(self) -> None:
        """Update self.dependencies based on the disassembly of self.func.

        Save references to attributes accessed on "self" or other fetched states.

        Recursively called when the function makes a method call on "self" or
        define comprehensions or nested functions that may reference "self".
        """
        for instruction in dis.get_instructions(self.func):
            if self.scan_status == ScanStatus.GETTING_STATE:
                self.handle_getting_state(instruction)
            elif self.scan_status == ScanStatus.GETTING_VAR:
                self.handle_getting_var(instruction)
            elif (
                instruction.opname in ("LOAD_FAST", "LOAD_DEREF")
                and instruction.argval in self.tracked_locals
            ):
                # bytecode loaded the class instance to the top of stack, next load instruction
                # is referencing an attribute on self
                self.top_of_stack = instruction.argval
                self.scan_status = ScanStatus.GETTING_ATTR
            elif self.scan_status == ScanStatus.GETTING_ATTR and instruction.opname in (
                "LOAD_ATTR",
                "LOAD_METHOD",
            ):
                self.load_attr_or_method(instruction)
                self.top_of_stack = None
            elif instruction.opname == "LOAD_CONST" and isinstance(
                instruction.argval, CodeType
            ):
                # recurse into nested functions / comprehensions, which can reference
                # instance attributes from the outer scope
                self._merge_deps(
                    type(self)(
                        func=instruction.argval,
                        state_cls=self.state_cls,
                        tracked_locals=self.tracked_locals,
                    )
                )
