"""Collection of base classes."""

from __future__ import annotations

import contextlib
import dataclasses
import dis
import enum
import importlib
import inspect
import sys
from types import CellType, CodeType, FunctionType, ModuleType
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
    GETTING_STATE_POST_AWAIT = enum.auto()
    GETTING_VAR = enum.auto()
    GETTING_IMPORT = enum.auto()


class UntrackedLocalVarError(VarValueError):
    """Raised when a local variable is referenced, but it is not tracked in the current scope."""


def assert_base_state(
    local_value: Any,
    local_name: str | None = None,
) -> type[BaseState]:
    """Assert that a local variable is a BaseState subclass.

    Args:
        local_value: The value of the local variable to check.
        local_name: The name of the local variable to check.

    Returns:
        The local variable value if it is a BaseState subclass.

    Raises:
        VarValueError: If the object is not a BaseState subclass.
    """
    from reflex.state import BaseState

    if not isinstance(local_value, type) or not issubclass(local_value, BaseState):
        msg = f"Cannot determine dependencies in fetched state {local_name!r}: {local_value!r} is not a BaseState."
        raise VarValueError(msg)
    return local_value


@dataclasses.dataclass
class DependencyTracker:
    """State machine for identifying state attributes that are accessed by a function."""

    func: FunctionType | CodeType = dataclasses.field()
    state_cls: type[BaseState] = dataclasses.field()

    dependencies: dict[str, set[str]] = dataclasses.field(default_factory=dict)

    scan_status: ScanStatus = dataclasses.field(default=ScanStatus.SCANNING)
    top_of_stack: str | None = dataclasses.field(default=None)

    tracked_locals: dict[str, type[BaseState] | ModuleType] = dataclasses.field(
        default_factory=dict
    )

    _getting_state_class: type[BaseState] | ModuleType | None = dataclasses.field(
        default=None
    )
    _get_var_value_positions: dis.Positions | None = dataclasses.field(default=None)
    _last_import_name: str | None = dataclasses.field(default=None)

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

    def get_tracked_local(self, local_name: str) -> type[BaseState] | ModuleType:
        """Get the value of a local name tracked in the current function scope.

        Args:
            local_name: The name of the local variable to fetch.

        Returns:
            The value of local name tracked in the current scope (a referenced
            BaseState subclass or imported module).

        Raises:
            UntrackedLocalVarError: If the local variable is not being tracked.
        """
        try:
            local_value = self.tracked_locals[local_name]
        except KeyError as ke:
            msg = f"{local_name!r} is not tracked in the current scope."
            raise UntrackedLocalVarError(msg) from ke
        return local_value

    def load_attr_or_method(self, instruction: dis.Instruction) -> None:
        """Handle loading an attribute or method from the object on top of the stack.

        This method directly tracks attributes and recursively merges
        dependencies from analyzing the dependencies of any methods called.

        Args:
            instruction: The dis instruction to process.

        Raises:
            VarValueError: if the attribute is an disallowed name or attribute
                does not reference a BaseState.
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
            if sys.version_info >= (3, 11):
                self._get_var_value_positions = instruction.positions
            self.scan_status = ScanStatus.GETTING_VAR
            return

        # Reset status back to SCANNING after attribute is accessed.
        self.scan_status = ScanStatus.SCANNING
        if not self.top_of_stack:
            return
        target_obj = self.get_tracked_local(self.top_of_stack)
        try:
            target_state = assert_base_state(target_obj, local_name=self.top_of_stack)
        except VarValueError:
            # If the target state is not a BaseState, we cannot track dependencies on it.
            return
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
        if isinstance(self.func, CodeType):
            msg = "Dependency detection cannot identify get_state class from a code object."
            raise VarValueError(msg)
        if instruction.opname in ("LOAD_FAST", "LOAD_FAST_BORROW"):
            self._getting_state_class = self.get_tracked_local(
                local_name=instruction.argval,
            )
        elif instruction.opname == "LOAD_GLOBAL":
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
        elif instruction.opname in ("LOAD_ATTR", "LOAD_METHOD"):
            self._getting_state_class = getattr(
                self._getting_state_class,
                instruction.argval,
            )
        elif instruction.opname == "GET_AWAITABLE":
            # Now inside the `await` machinery, subsequent instructions
            # operate on the result of the `get_state` call.
            self.scan_status = ScanStatus.GETTING_STATE_POST_AWAIT
            if self._getting_state_class is not None:
                self.top_of_stack = "_"
                self.tracked_locals[self.top_of_stack] = self._getting_state_class
                self._getting_state_class = None

    def handle_getting_state_post_await(self, instruction: dis.Instruction) -> None:
        """Handle bytecode analysis after `get_state` was called in the function.

        This function is called _after_ awaiting self.get_state to capture the
        local variable holding the state instance or directly record access to
        attributes accessed on the result of get_state.

        Args:
            instruction: The dis instruction to process.

        Raises:
            VarValueError: if the state class cannot be determined from the instruction.
        """
        if instruction.opname == "STORE_FAST" and self.top_of_stack:
            # Storing the result of get_state in a local variable.
            self.tracked_locals[instruction.argval] = self.tracked_locals.pop(
                self.top_of_stack
            )
            self.top_of_stack = None
            self.scan_status = ScanStatus.SCANNING
        elif instruction.opname in ("LOAD_ATTR", "LOAD_METHOD"):
            # Attribute access on an inline `get_state`, not assigned to a variable.
            self.load_attr_or_method(instruction)

    def _eval_var(self, positions: dis.Positions) -> Var:
        """Evaluate instructions from the wrapped function to get the Var object.

        Args:
            positions: The disassembly positions of the get_var_value call.

        Returns:
            The Var object.

        Raises:
            VarValueError: if the source code for the var cannot be determined.
        """
        # Get the original source code and eval it to get the Var.
        module = inspect.getmodule(self.func)
        if module is None or self._get_var_value_positions is None:
            msg = f"Cannot determine the source code for the var in {self.func!r}."
            raise VarValueError(msg)
        start_line = self._get_var_value_positions.end_lineno
        start_column = self._get_var_value_positions.end_col_offset
        end_line = positions.end_lineno
        end_column = positions.end_col_offset
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
            snipped_source = "".join([
                *source[0][start_column:],
                *source[1:-1],
                *source[-1][:end_column],
            ])
        else:
            snipped_source = source[0][start_column:end_column]
        # Evaluate the string in the context of the function's globals, closure and tracked local scope.
        return eval(
            f"({snipped_source})",
            self._get_globals(),
            {**self._get_closure(), **self.tracked_locals},
        )

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
        if instruction.opname == "CALL":
            if instruction.positions is None:
                msg = f"Cannot determine the source code for the var in {self.func!r}."
                raise VarValueError(msg)
            the_var = self._eval_var(instruction.positions)
            the_var_data = the_var._get_all_var_data()
            if the_var_data is None:
                msg = f"Cannot determine the source code for the var in {self.func!r}."
                raise VarValueError(msg)
            self.dependencies.setdefault(the_var_data.state, set()).add(
                the_var_data.field_name
            )
            self.scan_status = ScanStatus.SCANNING

    def _populate_dependencies(self) -> None:
        """Update self.dependencies based on the disassembly of self.func.

        Save references to attributes accessed on "self" or other fetched states.

        Recursively called when the function makes a method call on "self" or
        define comprehensions or nested functions that may reference "self".
        """
        for instruction in dis.get_instructions(self.func):
            if self.scan_status == ScanStatus.GETTING_STATE:
                self.handle_getting_state(instruction)
            elif self.scan_status == ScanStatus.GETTING_STATE_POST_AWAIT:
                self.handle_getting_state_post_await(instruction)
            elif self.scan_status == ScanStatus.GETTING_VAR:
                self.handle_getting_var(instruction)
            elif (
                instruction.opname
                in (
                    "LOAD_FAST",
                    "LOAD_DEREF",
                    "LOAD_FAST_BORROW",
                    "LOAD_FAST_CHECK",
                    "LOAD_FAST_AND_CLEAR",
                )
                and instruction.argval in self.tracked_locals
            ):
                # bytecode loaded the class instance to the top of stack, next load instruction
                # is referencing an attribute on self
                self.top_of_stack = instruction.argval
                self.scan_status = ScanStatus.GETTING_ATTR
            elif (
                instruction.opname
                in (
                    "LOAD_FAST_LOAD_FAST",
                    "LOAD_FAST_BORROW_LOAD_FAST_BORROW",
                    "STORE_FAST_LOAD_FAST",
                )
                and instruction.argval[-1] in self.tracked_locals
            ):
                # Double LOAD_FAST family instructions load multiple values onto the stack,
                # the last value in the argval list is the top of the stack.
                self.top_of_stack = instruction.argval[-1]
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
            elif instruction.opname == "IMPORT_NAME" and instruction.argval is not None:
                self.scan_status = ScanStatus.GETTING_IMPORT
                self._last_import_name = instruction.argval
                importlib.import_module(instruction.argval)
                top_module_name = instruction.argval.split(".")[0]
                self.tracked_locals[instruction.argval] = sys.modules[top_module_name]
                self.top_of_stack = instruction.argval
            elif instruction.opname == "IMPORT_FROM":
                if not self._last_import_name:
                    msg = f"Cannot find package associated with import {instruction.argval} in {self.func!r}."
                    raise VarValueError(msg)
                if instruction.argval in self._last_import_name.split("."):
                    # `import ... as ...` case:
                    # import from interim package, update tracked_locals for the last imported name.
                    self.tracked_locals[self._last_import_name] = getattr(
                        self.tracked_locals[self._last_import_name], instruction.argval
                    )
                    continue
                # Importing a name from a package/module.
                if self._last_import_name is not None and self.top_of_stack:
                    # The full import name does NOT end up in scope for a `from ... import`.
                    self.tracked_locals.pop(self._last_import_name)
                self.tracked_locals[instruction.argval] = getattr(
                    importlib.import_module(self._last_import_name),
                    instruction.argval,
                )
                # If we see a STORE_FAST, we can assign the top of stack to an aliased name.
                self.top_of_stack = instruction.argval
            elif (
                self.scan_status == ScanStatus.GETTING_IMPORT
                and instruction.opname == "STORE_FAST"
                and self.top_of_stack is not None
            ):
                self.tracked_locals[instruction.argval] = self.tracked_locals.pop(
                    self.top_of_stack
                )
                self.top_of_stack = None
