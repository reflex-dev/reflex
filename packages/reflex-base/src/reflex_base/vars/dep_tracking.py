"""Collection of base classes."""

from __future__ import annotations

import contextlib
import dataclasses
import dis
import enum
import importlib
import inspect
import sys
from types import CellType, CodeType, FunctionType, MemberDescriptorType, ModuleType
from typing import TYPE_CHECKING, Any, ClassVar, cast

from reflex_base.utils.exceptions import VarValueError

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


def is_dependency(state_cls: type[BaseState], name: str) -> bool:
    """Whether a computed var can depend on an attribute of a state.

    Args:
        state_cls: The state class.
        name: The attribute name.

    Returns:
        True for vars, and for other data descriptors (like a user-defined one
        that marks itself dirty) except properties and slots.
    """
    if name in state_cls.vars:
        return True
    attr = inspect.getattr_static(state_cls, name, None)
    return hasattr(type(attr), "__set__") and not isinstance(
        attr, (property, MemberDescriptorType)
    )


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


def get_defining_class(qual_name: str, state_cls: type[BaseState]) -> type[Any] | None:
    """Find the class whose body a scanned callable is defined in.

    That class is what a `super()` call inside it resolves after, which is not the
    state being read: a substate's getter skips the substate's own overrides.

    Args:
        qual_name: The qualified name of the scanned callable or code object.
        state_cls: The state the callable reads, which the class is part of.

    Returns:
        The outermost class of the qualified name that is in the state's own
        method resolution order, or None if the scan cannot tell which class
        the body belongs to.
    """
    # The last part names the callable itself, and `<locals>`/`<lambda>` separate the
    # scopes of a nested definition; a class defined in a function body carries that
    # function's name ahead of its own, so this scans from the outside in.
    for part in qual_name.split(".")[:-1]:
        match = next((cls for cls in state_cls.__mro__ if cls.__name__ == part), None)
        if match is not None:
            return match
    return None


@dataclasses.dataclass
class DependencyTracker:
    """State machine for identifying state attributes that are accessed by a function."""

    func: FunctionType | CodeType = dataclasses.field()
    state_cls: type[BaseState] = dataclasses.field()

    dependencies: dict[str, set[str]] = dataclasses.field(default_factory=dict)
    # States whose data left the analysis, so which of their vars are read is not
    # known; ComputedVar._deps() widens the dependency set for them.
    unresolved: set[type[BaseState]] = dataclasses.field(default_factory=set)

    scan_status: ScanStatus = dataclasses.field(default=ScanStatus.SCANNING)
    top_of_stack: str | None = dataclasses.field(default=None)

    tracked_locals: dict[str, type[BaseState] | ModuleType] = dataclasses.field(
        default_factory=dict
    )
    local_functions: dict[str, CodeType] = dataclasses.field(default_factory=dict)

    _getting_state_class: type[BaseState] | ModuleType | None = dataclasses.field(
        default=None
    )
    _get_var_value_positions: dis.Positions | None = dataclasses.field(default=None)
    _last_import_name: str | None = dataclasses.field(default=None)
    # Code objects already on this recursion path, so one that resolves back stops.
    _seen: set[CodeType] = dataclasses.field(default_factory=set)
    # A state in the lower slot of a two-value load, seen only by an op taking both.
    _state_below: type[BaseState] | None = dataclasses.field(default=None)
    # A locally defined function a call is about to make.
    _pending_callee: CodeType | None = dataclasses.field(default=None)
    # A code object between being loaded and being stored as a function.
    _pending_function: CodeType | None = dataclasses.field(default=None)
    # Whether a super object is being built from the state: through 3.11 the call
    # building it is not an escape, and the load after it is a super() load.
    _pending_super: bool = dataclasses.field(default=False)
    # The class whose body is being scanned, which is what a super() call inside it
    # resolves after — not the state itself, whose overrides super() skips.
    _home_cls: type[Any] | None = dataclasses.field(default=None, repr=False)

    INVALID_NAMES: ClassVar[list[str]] = ["parent_state", "substates", "get_substate"]

    LOCAL_LOAD_OPS: ClassVar[frozenset[str]] = frozenset({
        "LOAD_FAST",
        "LOAD_DEREF",
        "LOAD_FAST_BORROW",
        "LOAD_FAST_CHECK",
        "LOAD_FAST_AND_CLEAR",
    })

    DOUBLE_LOAD_OPS: ClassVar[frozenset[str]] = frozenset({
        "LOAD_FAST_LOAD_FAST",
        "LOAD_FAST_BORROW_LOAD_FAST_BORROW",
        "STORE_FAST_LOAD_FAST",
    })

    CALL_OPS: ClassVar[frozenset[str]] = frozenset({
        "CALL",
        "CALL_KW",
        "CALL_FUNCTION_EX",
    })

    # Instructions that consume the stack value as a value instead of reading an
    # attribute off it: a state reaching one may have been read whole.
    ESCAPING_OPS: ClassVar[frozenset[str]] = CALL_OPS | frozenset({
        "BUILD_LIST",
        "BUILD_TUPLE",
        "BUILD_SET",
        "BUILD_MAP",
        "BUILD_STRING",
        "LIST_EXTEND",
        "SET_UPDATE",
        "DICT_UPDATE",
        "DICT_MERGE",
        "LIST_APPEND",
        "SET_ADD",
        "MAP_ADD",
        "STORE_ATTR",
        "STORE_SUBSCR",
        "STORE_DEREF",
        "STORE_GLOBAL",
        "STORE_NAME",
        "BINARY_SUBSCR",
        "BINARY_OP",
        "COMPARE_OP",
        "IS_OP",
        "CONTAINS_OP",
        "UNPACK_SEQUENCE",
        "UNPACK_EX",
        "FORMAT_VALUE",
        "RETURN_VALUE",
        "YIELD_VALUE",
    })

    def __post_init__(self):
        """After initializing, populate the dependencies dict."""
        with contextlib.suppress(AttributeError):
            # unbox functools.partial
            self.func = cast(FunctionType, self.func.func)  # pyright: ignore[reportAttributeAccessIssue]
        with contextlib.suppress(AttributeError):
            # unbox EventHandler
            self.func = cast(FunctionType, self.func.fn)  # pyright: ignore[reportAttributeAccessIssue,reportFunctionMemberAccess]

        self._home_cls = get_defining_class(
            (
                self.func.co_qualname
                if isinstance(self.func, CodeType)
                else getattr(self.func, "__qualname__", "")
            ),
            self.state_cls,
        )

        code: CodeType | None = None
        if isinstance(self.func, CodeType):
            code = self.func
        elif isinstance(self.func, FunctionType):
            code = self.func.__code__
            with contextlib.suppress(AttributeError, IndexError):
                # the first argument to the function is the name of "self" arg
                self.tracked_locals[code.co_varnames[0]] = self.state_cls

        if code is not None:
            if code in self._seen:
                # Already analyzing this code up the chain, so only its state
                # as a whole bounds what it reads.
                self.unresolved.add(self.state_cls)
                return
            # Own the set, so a nested tracker cannot extend its parent's path.
            self._seen = {*self._seen, code}

        self._populate_dependencies()

    def _merge_deps(self, tracker: DependencyTracker) -> None:
        """Merge dependencies from another DependencyTracker.

        Args:
            tracker: The DependencyTracker to merge dependencies from.
        """
        for state_name, dep_name in tracker.dependencies.items():
            self.dependencies.setdefault(state_name, set()).update(dep_name)
        self.unresolved.update(tracker.unresolved)

    def _track_nested(
        self,
        func: FunctionType | CodeType,
        state_cls: type[BaseState],
        tracked_locals: dict[str, type[BaseState] | ModuleType] | None = None,
    ) -> None:
        """Analyze a callable reached from this one, merging in what it learned.

        Args:
            func: The function or code object to analyze.
            state_cls: The state its "self" argument, if it takes one, refers to.
            tracked_locals: The locals of the nested scope; a copy of this
                tracker's by default, so an alias bound there stays out of siblings.
        """
        self._merge_deps(
            type(self)(
                func=func,
                state_cls=state_cls,
                tracked_locals=(
                    dict(self.tracked_locals)
                    if tracked_locals is None
                    else tracked_locals
                ),
                local_functions=dict(self.local_functions),
                _seen=self._seen,
            )
        )

    def get_tracked_state(self, local_name: str | None) -> type[BaseState] | None:
        """Get the state a local name tracked in the current scope refers to.

        Args:
            local_name: The name of the local variable to fetch.

        Returns:
            The BaseState subclass the local refers to, or None if the name is
            untracked or refers to an imported module instead.
        """
        from reflex.state import BaseState

        value = self.tracked_locals.get(local_name) if local_name else None
        if isinstance(value, type) and issubclass(value, BaseState):
            return value
        return None

    def load_attr_or_method(
        self,
        name: str,
        positions: dis.Positions | None = None,
        target_state: type[BaseState] | None = None,
        lookup: type[Any] | None = None,
    ) -> None:
        """Handle loading an attribute or method from the object on top of the stack.

        This method directly tracks attributes and recursively merges
        dependencies from analyzing the dependencies of any methods called.

        Args:
            name: The attribute or method being loaded.
            positions: Where the load appears in the source, for `get_var_value`.
            target_state: The state it is loaded from; whatever the top of the
                stack refers to, if not given.
            lookup: The class to resolve the name against, when that is not the
                state itself: the class a `super()` call starts its search from.

        Raises:
            VarValueError: if the attribute is an disallowed name or attribute
                does not reference a BaseState.
        """
        from .base import ComputedVar

        if name in self.INVALID_NAMES:
            msg = f"Cached var {self!s} cannot access arbitrary state via `{name}`."
            raise VarValueError(msg)
        if name == "get_state":
            # Special case: arbitrary state access requested.
            self.scan_status = ScanStatus.GETTING_STATE
            return
        if name == "get_var_value":
            # Special case: arbitrary var access requested.
            self._get_var_value_positions = positions
            self.scan_status = ScanStatus.GETTING_VAR
            return

        # Reset status back to SCANNING after attribute is accessed.
        self.scan_status = ScanStatus.SCANNING
        if target_state is None:
            if not self.top_of_stack:
                return
            target_obj = self.get_tracked_local(self.top_of_stack)
            try:
                target_state = assert_base_state(
                    target_obj,
                    local_name=self.top_of_stack,
                )
            except VarValueError:
                # If the target state is not a BaseState, we cannot track dependencies on it.
                return
        # Look up the raw descriptor first via inspect.getattr_static so we can detect
        # property-like descriptors (e.g. HybridProperty) that override __get__ to return
        # something other than themselves when accessed via the class.
        resolved_from = lookup if lookup is not None else target_state
        try:
            static_obj = inspect.getattr_static(resolved_from, name)
        except AttributeError:
            static_obj = None

        if isinstance(static_obj, property) and not isinstance(static_obj, ComputedVar):
            # recurse into property fget functions
            ref_obj = static_obj.fget
        else:
            try:
                ref_obj = getattr(resolved_from, name)
            except AttributeError:
                # Not found on this state class, maybe it is a dynamic attribute that will be picked up later.
                ref_obj = None
        if isinstance(ref_obj, type) and name not in target_state.vars:
            # A class reached through the state (`self.__class__`): no state data
            # to depend on, and no getter body to analyze.
            return
        if callable(ref_obj):
            # recurse into callable attributes
            self._track_nested(cast(FunctionType, ref_obj), target_state)
        elif is_dependency(target_state, name):
            self.dependencies.setdefault(target_state.get_full_name(), set()).add(name)

    def _load_super_attr(self, name: str, positions: dis.Positions | None) -> None:
        """Read a member off the super object being built from this state.

        Whichever implementation super() would reach is analyzed, against the state
        itself; if that implementation cannot be resolved, the state is left
        unresolved and `_deps()` widens over its vars.

        Args:
            name: The member loaded through super().
            positions: Where the load appears in the source, for `get_var_value`.
        """
        mro = self.state_cls.__mro__
        home = self._home_cls
        # super() runs the first implementation after the class the caller's body is
        # in, not whatever the state class overrides it with, though what that reads
        # is still the state's own data.
        after = mro[mro.index(home) + 1 :] if home is not None and home in mro else ()
        for cls in after:
            if name in cls.__dict__:
                self.load_attr_or_method(name, positions, self.state_cls, cls)
                return
        # Either the caller's class is not resolvable or super() finds nothing, so
        # which implementation would run is more than this can say.
        self.scan_status = ScanStatus.SCANNING
        self.unresolved.add(self.state_cls)

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
            self.load_attr_or_method(instruction.argval, instruction.positions)

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
            for state_name, field_names in the_var._dependency_fields().items():
                self.dependencies.setdefault(state_name, set()).update(field_names)
            self.scan_status = ScanStatus.SCANNING

    def _packing_closure(
        self, instructions: tuple[dis.Instruction, ...], index: int
    ) -> bool:
        """Whether the instruction at index builds a nested function's closure.

        A state captured in a closure is not lost: the nested function is analyzed
        with the same locals.

        Args:
            instructions: The disassembly being scanned.
            index: Where the instruction sits in it.

        Returns:
            True if the built container becomes a function's closure.
        """
        for following in instructions[index + 1 : index + 6]:
            # Only the closure flag keeps the state alive inside a function to be
            # analyzed; a tuple of default arguments is just another value. Through
            # 3.11 the flags ride on MAKE_FUNCTION, after on a SET_FUNCTION_ATTRIBUTE,
            # so whichever of the two carries them decides.
            if (
                following.opname in ("MAKE_FUNCTION", "SET_FUNCTION_ATTRIBUTE")
                and following.arg is not None
            ):
                return bool(following.arg & 0x08)
            if following.opname in self.ESCAPING_OPS:
                return False
        return False

    def _populate_dependencies(self) -> None:
        """Update self.dependencies based on the disassembly of self.func.

        Save references to attributes accessed on "self" or other fetched states.

        Recursively called when the function makes a method call on "self" or
        define comprehensions or nested functions that may reference "self".
        """
        instructions = tuple(dis.get_instructions(self.func))
        for index, instruction in enumerate(instructions):
            if self.scan_status == ScanStatus.GETTING_STATE:
                self.handle_getting_state(instruction)
            elif self.scan_status == ScanStatus.GETTING_STATE_POST_AWAIT:
                self.handle_getting_state_post_await(instruction)
            elif self.scan_status == ScanStatus.GETTING_VAR:
                self.handle_getting_var(instruction)
            elif (
                instruction.opname in self.LOCAL_LOAD_OPS
                and instruction.argval in self.tracked_locals
            ):
                # bytecode loaded the class instance to the top of stack, next load instruction
                # is referencing an attribute on self
                if (
                    self.scan_status == ScanStatus.GETTING_ATTR
                    and (shadowed := self.get_tracked_state(self.top_of_stack))
                    is not None
                ):
                    # `helper(self, self.b)`: this load covers the state already on
                    # the stack, which the attribute load can no longer reach.
                    self._state_below = shadowed
                self.top_of_stack = instruction.argval
                self.scan_status = ScanStatus.GETTING_ATTR
            elif (
                instruction.opname in self.DOUBLE_LOAD_OPS
                and instruction.argval[-1] in self.tracked_locals
            ):
                # Double LOAD_FAST family instructions load multiple values onto the stack,
                # the last value in the argval list is the top of the stack.
                self.top_of_stack = instruction.argval[-1]
                self.scan_status = ScanStatus.GETTING_ATTR
                self._state_below = self.get_tracked_state(instruction.argval[0])
            elif (
                instruction.opname in self.DOUBLE_LOAD_OPS
                and (below := self.get_tracked_state(instruction.argval[0])) is not None
            ):
                # The state sits below the top of the stack, out of reach of an
                # attribute load.
                self._state_below = below
            elif instruction.opname == "LOAD_GLOBAL" and instruction.argval == "super":
                # A super object is about to be built from this state; through 3.11
                # that is a plain call, not an escape.
                self._pending_super = True
            elif instruction.opname == "LOAD_SUPER_ATTR":
                # super() was handed this state, so its attribute is read through it.
                self._pending_super = False
                self._load_super_attr(instruction.argval, instruction.positions)
                self.top_of_stack = None
            elif self.scan_status == ScanStatus.GETTING_ATTR and instruction.opname in (
                "LOAD_ATTR",
                "LOAD_METHOD",
            ):
                # Through 3.11 the load right after `super(__class__, self)` reads
                # off the super object, not off the state itself.
                pending_super = self._pending_super
                self._pending_super = False
                if pending_super:
                    self._load_super_attr(instruction.argval, instruction.positions)
                else:
                    self.load_attr_or_method(instruction.argval, instruction.positions)
                self.top_of_stack = None
            elif (
                instruction.opname in self.LOCAL_LOAD_OPS
                and (local_function := self.local_functions.get(instruction.argval))
                is not None
            ):
                # A locally defined function is on the stack, so a call can bind
                # its parameters to a state.
                self._pending_callee = local_function
            elif (
                self.scan_status == ScanStatus.GETTING_ATTR
                and instruction.opname == "CALL"
                and instruction.arg == 1
                and self._pending_callee is not None
                and self._pending_callee.co_argcount
                and (arg_state := self.get_tracked_state(self.top_of_stack)) is not None
            ):
                # `helper(self)`: the state reaches the callee through its first
                # parameter.
                callee = self._pending_callee
                self._pending_callee = None
                self.scan_status = ScanStatus.SCANNING
                self.top_of_stack = None
                self._track_nested(
                    callee,
                    arg_state,
                    tracked_locals={
                        **self.tracked_locals,
                        callee.co_varnames[0]: arg_state,
                    },
                )
            elif instruction.opname in self.CALL_OPS and self._pending_super:
                # Through 3.11 `super()` is a plain `super(__class__, self)` call.
                # The state stays pending, so the load after it resolves as a super()
                # load, and this call itself is not an escape.
                self._state_below = None
            elif instruction.opname in self.ESCAPING_OPS:
                escaped = (
                    self.get_tracked_state(self.top_of_stack)
                    if self.scan_status == ScanStatus.GETTING_ATTR
                    else None
                ) or self._state_below
                if self.scan_status == ScanStatus.GETTING_ATTR:
                    self.scan_status = ScanStatus.SCANNING
                    self.top_of_stack = None
                if escaped is not None and not self._packing_closure(
                    instructions, index
                ):
                    # The state itself, not a value read from it, was consumed.
                    self.unresolved.add(escaped)
                self._pending_super = False
                self._pending_callee = None
                self._pending_function = None
                self._state_below = None
            elif instruction.opname == "LOAD_CONST" and isinstance(
                instruction.argval, CodeType
            ):
                # recurse into nested functions / comprehensions, which can reference
                # instance attributes from the outer scope
                self._pending_function = instruction.argval
                self._track_nested(instruction.argval, self.state_cls)
            elif instruction.opname == "IMPORT_NAME":
                if instruction.argval is None:
                    continue
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
            elif instruction.opname == "STORE_FAST":
                if self._pending_function is not None:
                    # The value stored is a function defined in this scope.
                    self.local_functions[instruction.argval] = self._pending_function
                    self._pending_function = None
                else:
                    # The name holds something else now, so a call through it can no
                    # longer be followed into the old body.
                    self.local_functions.pop(instruction.argval, None)
                    if (
                        self.scan_status == ScanStatus.GETTING_ATTR
                        and (aliased := self.get_tracked_state(self.top_of_stack))
                        is not None
                    ):
                        # `alias = self`: keep tracking reads through the alias.
                        self.tracked_locals[instruction.argval] = aliased
                        self.scan_status = ScanStatus.SCANNING
                        self.top_of_stack = None
                self._pending_callee = None
                # A stored value stands on its own, not a super bound for a load.
                self._pending_super = False
