"""Tests for dependency tracking functionality."""

from __future__ import annotations

import pytest
from reflex_base.utils.exceptions import VarValueError
from reflex_base.vars.dep_tracking import (
    DependencyTracker,
    UntrackedLocalVarError,
    get_cell_value,
)

import reflex as rx
import tests.units.states.upload as tus_upload
from reflex.state import State


class DependencyTestState(State):
    """Test state for dependency tracking tests."""

    count: rx.Field[int] = rx.field(default=0)
    name: rx.Field[str] = rx.field(default="test")
    items: rx.Field[list[str]] = rx.field(default_factory=list)
    board: rx.Field[list[list[int]]] = rx.field(default_factory=list)


class AnotherTestState(State):
    """Another test state for cross-state dependencies."""

    value: rx.Field[int] = rx.field(default=42)
    text: rx.Field[str] = rx.field(default="hello")


def test_simple_attribute_access():
    """Test tracking simple attribute access on self."""

    def simple_func(self: DependencyTestState):
        return self.count

    tracker = DependencyTracker(simple_func, DependencyTestState)

    expected_deps = {DependencyTestState.get_full_name(): {"count"}}
    assert tracker.dependencies == expected_deps


def test_multiple_attribute_access():
    """Test tracking multiple attribute access on self."""

    def multi_attr_func(self: DependencyTestState):
        return self.count + len(self.name) + len(self.items)

    tracker = DependencyTracker(multi_attr_func, DependencyTestState)

    expected_deps = {DependencyTestState.get_full_name(): {"count", "name", "items"}}
    assert tracker.dependencies == expected_deps


def test_method_call_dependencies():
    """Test tracking dependencies from method calls."""

    class StateWithMethod(State):
        value: int = 0

        def helper_method(self):
            return self.value * 2

        def func_with_method_call(self):
            return self.helper_method()

    tracker = DependencyTracker(StateWithMethod.func_with_method_call, StateWithMethod)

    # Should track dependencies from both the method call and the method itself
    expected_deps = {StateWithMethod.get_full_name(): {"value"}}
    assert tracker.dependencies == expected_deps


def test_nested_function_dependencies():
    """Test tracking dependencies in nested functions."""

    def func_with_nested(self: DependencyTestState):
        def inner():
            return self.count

        return inner()

    tracker = DependencyTracker(func_with_nested, DependencyTestState)

    expected_deps = {DependencyTestState.get_full_name(): {"count"}}
    assert tracker.dependencies == expected_deps


def test_list_comprehension_dependencies():
    """Test tracking dependencies in list comprehensions."""

    def func_with_comprehension(self: DependencyTestState):
        return [x for x in self.items if len(x) > self.count]

    tracker = DependencyTracker(func_with_comprehension, DependencyTestState)

    expected_deps = {DependencyTestState.get_full_name(): {"items", "count"}}
    assert tracker.dependencies == expected_deps


def test_list_comprehension_dependencies_2():
    """Test tracking dependencies in list comprehensions."""

    def func_with_comprehension(self: DependencyTestState):
        return [[self.board[r][c] for r in range(3)] for c in range(5)]

    tracker = DependencyTracker(func_with_comprehension, DependencyTestState)

    expected_deps = {DependencyTestState.get_full_name(): {"board"}}
    assert tracker.dependencies == expected_deps


def test_invalid_attribute_access():
    """Test that accessing invalid attributes raises VarValueError."""

    def invalid_func(self: DependencyTestState):
        return self.parent_state

    with pytest.raises(
        VarValueError, match="cannot access arbitrary state via `parent_state`"
    ):
        DependencyTracker(invalid_func, DependencyTestState)


def test_get_state_functionality():
    """Test tracking dependencies when using get_state."""

    async def func_with_get_state(self: DependencyTestState):
        other_state = await self.get_state(AnotherTestState)
        return other_state.value

    tracker = DependencyTracker(func_with_get_state, DependencyTestState)

    expected_deps = {AnotherTestState.get_full_name(): {"value"}}
    assert tracker.dependencies == expected_deps


def test_get_state_functionality_direct():
    """Test tracking dependencies when using get_state without assigning to interim local variable."""

    async def func_with_get_state_direct(self: DependencyTestState):
        return (await self.get_state(AnotherTestState)).value

    tracker = DependencyTracker(func_with_get_state_direct, DependencyTestState)

    expected_deps = {AnotherTestState.get_full_name(): {"value"}}
    assert tracker.dependencies == expected_deps


def test_get_state_with_local_var_error():
    """Test that get_state with local variables raises appropriate error."""

    async def invalid_get_state_func(self: DependencyTestState):
        state_cls = AnotherTestState
        return (await self.get_state(state_cls)).value

    with pytest.raises(
        UntrackedLocalVarError, match="'state_cls' is not tracked in the current scope"
    ):
        DependencyTracker(invalid_get_state_func, DependencyTestState)


def test_get_state_with_import_from():
    """Test that get_state with function-local `from ... import ...` finds correct dependency."""

    async def get_state_import_from(self: DependencyTestState):
        from tests.units.states.mutation import MutableTestState

        return (await self.get_state(MutableTestState)).hashmap

    from tests.units.states.mutation import MutableTestState

    tracker = DependencyTracker(get_state_import_from, DependencyTestState)
    expected_deps = {MutableTestState.get_full_name(): {"hashmap"}}
    assert tracker.dependencies == expected_deps


def test_get_state_with_import_from_multiple():
    """Test that get_state with function-local `from ... import ...` finds correct dependency."""

    async def get_state_import_from(self: DependencyTestState):
        from tests.units.states.upload import ChildFileUploadState, SubUploadState

        return (await self.get_state(SubUploadState)).img, (
            await self.get_state(ChildFileUploadState)
        ).img_list

    tracker = DependencyTracker(get_state_import_from, DependencyTestState)
    expected_deps = {
        tus_upload.SubUploadState.get_full_name(): {"img"},
        tus_upload.ChildFileUploadState.get_full_name(): {"img_list"},
    }
    assert tracker.dependencies == expected_deps


def test_get_state_with_import_from_as():
    """Test that get_state with function-local `from ... import ... as ...` finds correct dependency."""

    async def get_state_import_from_as(self: DependencyTestState):
        from tests.units.states.mutation import MutableTestState as mts

        return (await self.get_state(mts)).hashmap

    from tests.units.states.mutation import MutableTestState

    tracker = DependencyTracker(get_state_import_from_as, DependencyTestState)
    expected_deps = {MutableTestState.get_full_name(): {"hashmap"}}
    assert tracker.dependencies == expected_deps


def test_get_state_with_import():
    """Test that get_state with function-local `import ...` finds correct dependency."""

    async def get_state_import(self: DependencyTestState):
        import tests.units.states.mutation

        return (
            await self.get_state(tests.units.states.mutation.MutableTestState)
        ).hashmap

    from tests.units.states.mutation import MutableTestState

    tracker = DependencyTracker(get_state_import, DependencyTestState)
    expected_deps = {MutableTestState.get_full_name(): {"hashmap"}}
    assert tracker.dependencies == expected_deps


def test_get_state_with_import_as():
    """Test that get_state with function-local `import ... as ...` finds correct dependency."""

    async def get_state_import_as(self: DependencyTestState):
        import tests.units.states.mutation as mutation

        return (await self.get_state(mutation.MutableTestState)).hashmap

    from tests.units.states.mutation import MutableTestState

    tracker = DependencyTracker(get_state_import_as, DependencyTestState)
    expected_deps = {MutableTestState.get_full_name(): {"hashmap"}}
    assert tracker.dependencies == expected_deps


def test_get_state_with_import_from_method():
    """Test that get_state with function-local `from ... import ...` finds correct dependency through a method call."""

    async def get_state_import_from(self: DependencyTestState):
        from tests.units.states.mutation import MutableTestState

        return (await self.get_state(MutableTestState))._get_array()

    from tests.units.states.mutation import MutableTestState

    tracker = DependencyTracker(get_state_import_from, DependencyTestState)
    expected_deps = {MutableTestState.get_full_name(): {"array"}}
    assert tracker.dependencies == expected_deps


def test_get_state_access_imported_global_module():
    """Test tracking simple attribute access on self."""

    async def get_state_imported_global(self: DependencyTestState):
        return (await self.get_state(tus_upload.SubUploadState)).img

    tracker = DependencyTracker(get_state_imported_global, DependencyTestState)
    expected_deps = {tus_upload.SubUploadState.get_full_name(): {"img"}}
    assert tracker.dependencies == expected_deps


def test_nested_function():
    """Test tracking dependencies in nested functions."""

    def func_with_nested(self: DependencyTestState):
        async def inner():  # noqa: RUF029
            _ = self.board

        return self.count

    tracker = DependencyTracker(func_with_nested, DependencyTestState)

    expected_deps = {DependencyTestState.get_full_name(): {"board", "count"}}
    assert tracker.dependencies == expected_deps


def test_get_var_value_functionality():
    """Test tracking dependencies when using get_var_value."""

    async def func_with_get_var_value(self: DependencyTestState):
        return await self.get_var_value(DependencyTestState.count)

    tracker = DependencyTracker(func_with_get_var_value, DependencyTestState)
    expected_deps = {DependencyTestState.get_full_name(): {"count"}}
    assert tracker.dependencies == expected_deps


def test_get_var_value_tracks_all_composed_fields():
    """Composed get_var_value arguments register every state field they read."""
    composed_var = DependencyTestState.count + DependencyTestState.items.length()

    async def composed(self: DependencyTestState):
        """Read a composite expression.

        Returns:
            The combined field value.
        """
        return await self.get_var_value(composed_var)

    tracker = DependencyTracker(composed, DependencyTestState)
    assert tracker.dependencies == {
        DependencyTestState.get_full_name(): {"count", "items"}
    }


def test_get_var_value_multiple_lines_functionality():
    """Test tracking dependencies when using get_var_value spread out on multiple lines."""

    async def func_with_get_var_value(self: DependencyTestState):
        return await self.get_var_value(
            DependencyTestState.
            # annoying comment
            count
        )

    tracker = DependencyTracker(func_with_get_var_value, DependencyTestState)
    expected_deps = {DependencyTestState.get_full_name(): {"count"}}
    assert tracker.dependencies == expected_deps


def test_get_var_value_with_import_from():
    """Test that get_var_value with function-local `from ... import ...` finds correct dependency."""

    async def get_state_import_from(self: DependencyTestState):
        from tests.units.states.mutation import MutableTestState

        return await self.get_var_value(MutableTestState.hashmap)  # pyright: ignore[reportArgumentType]

    from tests.units.states.mutation import MutableTestState

    tracker = DependencyTracker(get_state_import_from, DependencyTestState)
    expected_deps = {MutableTestState.get_full_name(): {"hashmap"}}
    assert tracker.dependencies == expected_deps


def test_merge_deps():
    """Test merging dependencies from multiple trackers."""

    def func1(self: DependencyTestState):
        return self.count

    def func2(self: DependencyTestState):
        return self.name

    tracker1 = DependencyTracker(func1, DependencyTestState)
    tracker2 = DependencyTracker(func2, DependencyTestState)

    tracker1._merge_deps(tracker2)

    expected_deps = {DependencyTestState.get_full_name(): {"count", "name"}}
    assert tracker1.dependencies == expected_deps


def test_get_globals_with_function():
    """Test _get_globals method with a function."""

    def test_func(self: DependencyTestState):
        return self.count

    tracker = DependencyTracker(test_func, DependencyTestState)
    globals_dict = tracker._get_globals()

    assert isinstance(globals_dict, dict)
    assert "DependencyTestState" in globals_dict
    assert "State" in globals_dict


def test_get_globals_with_code_object():
    """Test _get_globals method with a code object."""

    def test_func(self: DependencyTestState):
        return self.count

    code_obj = test_func.__code__
    tracker = DependencyTracker(code_obj, DependencyTestState)
    globals_dict = tracker._get_globals()

    assert not globals_dict


def test_get_closure_with_function():
    """Test _get_closure method with a function that has closure."""
    outer_var = "test"

    def func_with_closure(self: DependencyTestState):
        return self.count + len(outer_var)

    tracker = DependencyTracker(func_with_closure, DependencyTestState)
    closure_dict = tracker._get_closure()

    assert isinstance(closure_dict, dict)
    assert "outer_var" in closure_dict
    assert closure_dict["outer_var"] == "test"


def test_get_closure_with_code_object():
    """Test _get_closure method with a code object."""

    def test_func(self: DependencyTestState):
        return self.count

    code_obj = test_func.__code__
    tracker = DependencyTracker(code_obj, DependencyTestState)
    closure_dict = tracker._get_closure()

    assert not closure_dict


def test_property_dependencies():
    """Test tracking dependencies through property access."""

    class StateWithProperty(State):
        _value: int = 0

        def computed_value(self) -> int:
            return self._value * 2

        def func_with_property(self):
            return self.computed_value

    tracker = DependencyTracker(StateWithProperty.func_with_property, StateWithProperty)

    # Should track dependencies from the property getter
    expected_deps = {StateWithProperty.get_full_name(): {"_value"}}
    assert tracker.dependencies == expected_deps


def test_hybrid_property_dependencies():
    """Test tracking dependencies through hybrid_property access (without custom .var)."""
    from reflex.experimental import hybrid_property

    class StateWithHybridProperty(State):
        first_name: str = "John"
        last_name: str = "Doe"

        @hybrid_property
        def full_name(self) -> str:
            return f"{self.first_name} {self.last_name}"

        def func_using_hybrid_property(self):
            return self.full_name

    tracker = DependencyTracker(
        StateWithHybridProperty.func_using_hybrid_property, StateWithHybridProperty
    )

    # Should recurse into the hybrid_property's fget and track its underlying deps.
    expected_deps = {
        StateWithHybridProperty.get_full_name(): {"first_name", "last_name"}
    }
    assert tracker.dependencies == expected_deps


def test_hybrid_property_with_custom_var_dependencies():
    """Test tracking dependencies through hybrid_property access when a custom .var is set.

    The dep tracker must still recurse into the Python fget (not the frontend var function),
    since computed vars use the backend implementation at runtime.
    """
    from reflex.experimental import hybrid_property
    from reflex.vars.base import Var

    class StateWithHybridPropertyVar(State):
        last_name: str = "Doe"
        unrelated: str = "ignored"

        @hybrid_property
        def has_last_name(self) -> str:
            return "yes" if self.last_name else "no"

        @has_last_name.var
        def _has_last_name_var(cls) -> Var[str]:
            # Reference an unrelated field here to confirm the tracker uses fget, not this.
            return cls.unrelated  # pyright: ignore[reportReturnType]

        def func_using_hybrid_property(self):
            return self.has_last_name

    tracker = DependencyTracker(
        StateWithHybridPropertyVar.func_using_hybrid_property,
        StateWithHybridPropertyVar,
    )

    expected_deps = {StateWithHybridPropertyVar.get_full_name(): {"last_name"}}
    assert tracker.dependencies == expected_deps


def test_no_dependencies():
    """Test functions with no state dependencies."""

    def func_no_deps(self: DependencyTestState):
        return 42

    tracker = DependencyTracker(func_no_deps, DependencyTestState)

    assert not tracker.dependencies


def test_complex_expression_dependencies():
    """Test tracking dependencies in complex expressions."""

    def complex_func(self: DependencyTestState):
        return (self.count * 2 + len(self.name)) if self.items else 0

    tracker = DependencyTracker(complex_func, DependencyTestState)

    expected_deps = {DependencyTestState.get_full_name(): {"count", "name", "items"}}
    assert tracker.dependencies == expected_deps


def test_equality_expression_dependencies():
    """Test tracking dependencies in equality expressions.

    With the state attribute on the right hand side, python generates
    LOAD_FAST_LOAD_FAST family instructions.
    """

    def equality_func(self: DependencyTestState):
        my_val = 2
        return my_val == self.count

    tracker = DependencyTracker(equality_func, DependencyTestState)
    expected_deps = {DependencyTestState.get_full_name(): {"count"}}
    assert tracker.dependencies == expected_deps


def test_equality_expression_dependencies_lhs():
    """Test tracking dependencies in equality expressions (state on left hand side)."""

    def equality_func(self: DependencyTestState):
        my_val = 2
        return self.count == my_val

    tracker = DependencyTracker(equality_func, DependencyTestState)
    expected_deps = {DependencyTestState.get_full_name(): {"count"}}
    assert tracker.dependencies == expected_deps


def test_equality_expression_dependencies_get_state():
    """Test tracking dependencies in equality expressions with retrieved state."""

    async def equality_func_get_state(self: DependencyTestState):
        another_state = await self.get_state(AnotherTestState)
        my_val = 2
        return my_val == another_state.value

    tracker = DependencyTracker(equality_func_get_state, DependencyTestState)

    expected_deps = {AnotherTestState.get_full_name(): {"value"}}
    assert tracker.dependencies == expected_deps


def test_get_cell_value_with_valid_cell():
    """Test get_cell_value with a valid cell containing a value."""
    # Create a closure to get a cell object
    value = "test_value"

    def outer():
        def inner():
            return value

        return inner

    inner_func = outer()

    assert inner_func.__closure__ is not None

    cell = inner_func.__closure__[0]
    result = get_cell_value(cell)
    assert result == "test_value"


def test_cross_state_dependencies_complex():
    """Test complex cross-state dependency scenarios."""

    class StateA(State):
        value_a: int = 1

    class StateB(State):
        value_b: int = 2

    async def complex_cross_state_func(self: DependencyTestState):
        state_a = await self.get_state(StateA)
        state_b = await self.get_state(StateB)
        return state_a.value_a + state_b.value_b

    tracker = DependencyTracker(complex_cross_state_func, DependencyTestState)

    expected_deps = {
        StateA.get_full_name(): {"value_a"},
        StateB.get_full_name(): {"value_b"},
    }
    assert tracker.dependencies == expected_deps


def test_dependencies_with_computed_var():
    """Test that computed vars are handled correctly in dependency tracking."""

    class StateWithComputedVar(State):
        base_value: int = 0

        @rx.var
        def computed_value(self) -> int:
            return self.base_value * 2

    def func_using_computed_var(self: StateWithComputedVar):
        return self.computed_value

    tracker = DependencyTracker(func_using_computed_var, StateWithComputedVar)

    # Should track the computed var, not its dependencies
    expected_deps = {StateWithComputedVar.get_full_name(): {"computed_value"}}
    assert tracker.dependencies == expected_deps


def _reads_state_and_more(state, extra=None):
    """Read a field through a parameter, from outside the state class.

    Args:
        state: The state to read from.
        extra: An unrelated argument.

    Returns:
        The count and the extra.
    """
    return state.count + (extra or 0)


class _PlainThing:
    """An object that is not state, with an attribute to read."""

    field = 1


class SuperParentState(State):
    """Parent state exposing a method and a property to its substates."""

    value: int = 0

    def parent_method(self) -> int:
        """Double the value.

        Returns:
            Twice the value.
        """
        return self.value * 2

    @property
    def parent_property(self) -> int:
        """The value plus one.

        Returns:
            One more than the value.
        """
        return self.value + 1


class SuperChildState(SuperParentState):
    """Substate whose methods reach the parent through super()."""

    other: int = 0

    def func_with_super_call(self) -> int:
        """Reach the parent's method through super().

        Returns:
            The parent's result plus this state's own field.
        """
        return super().parent_method() + self.other

    def func_with_super_attr(self) -> int:
        """Reach the parent's property through super().

        Returns:
            The parent's property plus this state's own field.
        """
        return super().parent_property + self.other


def test_super_method_call_dependencies():
    """Test tracking dependencies through a method called on super()."""
    tracker = DependencyTracker(SuperChildState.func_with_super_call, SuperChildState)

    expected_deps = {SuperChildState.get_full_name(): {"value", "other"}}
    assert tracker.dependencies == expected_deps
    assert not tracker.unresolved


def test_super_property_dependencies():
    """Test tracking dependencies through a property accessed on super()."""
    tracker = DependencyTracker(SuperChildState.func_with_super_attr, SuperChildState)

    expected_deps = {SuperChildState.get_full_name(): {"value", "other"}}
    assert tracker.dependencies == expected_deps
    assert not tracker.unresolved


class SuperSupersededChildState(SuperParentState):
    """Substate whose own override is exactly what its super() call skips."""

    extra: int = 0

    def parent_method(self) -> int:
        """Read this class's own field, never calling super().

        Returns:
            The extra.
        """
        return self.extra

    @property
    def parent_property(self) -> int:
        """Read this class's own field, never calling super().

        Returns:
            One more than the extra.
        """
        return self.extra + 1

    def func_supering_method(self) -> int:
        """Call the method this class overrides, through super().

        Returns:
            The parent's result.
        """
        return super().parent_method()

    def func_supering_property(self) -> int:
        """Read the property this class overrides, through super().

        Returns:
            The parent's property.
        """
        return super().parent_property


@pytest.mark.parametrize(
    "func",
    [
        SuperSupersededChildState.func_supering_method,
        SuperSupersededChildState.func_supering_property,
    ],
    ids=["method", "property"],
)
def test_super_skips_the_subclass_override(func):
    """super() runs the parent's implementation, so its reads are the dependencies.

    Args:
        func: The getter reaching the parent's member through super().
    """
    tracker = DependencyTracker(func, SuperSupersededChildState)

    assert tracker.dependencies == {
        SuperSupersededChildState.get_full_name(): {"value"}
    }
    assert not tracker.unresolved


def test_super_resolves_from_the_class_the_caller_is_defined_in():
    """A method inherited past an override resolves super() from its own class."""

    class GrandparentState(SuperParentState):
        def inherited(self) -> int:
            """Reach the parent through super() from the grandparent's own body.

            Returns:
                The parent's result.
            """
            return super().parent_method()

    class GrandchildState(GrandparentState):
        extra: int = 0

        def parent_method(self) -> int:
            """Read this class's own field, never calling super().

            Returns:
                The extra.
            """
            return self.extra

        def func_calling_inherited(self) -> int:
            """Call the grandparent's method, which reaches the parent by super().

            Returns:
                The inherited result.
            """
            return self.inherited()

    tracker = DependencyTracker(GrandchildState.func_calling_inherited, GrandchildState)

    assert tracker.dependencies == {GrandchildState.get_full_name(): {"value"}}
    assert not tracker.unresolved


def test_explicit_super_start_class_skips_the_class_it_names():
    """`super(Below, self)` runs the implementation after Below, not after the caller."""

    class MiddleState(SuperParentState):
        extra: int = 0

        def parent_method(self) -> int:
            """Read this class's own field, which the explicit super() skips.

            Returns:
                The extra.
            """
            return self.extra

    class ExplicitSuperState(MiddleState):
        def func_naming_the_class_to_skip(self) -> int:
            """Reach past the class in between by naming it to super().

            Returns:
                The parent's result.
            """
            return super(MiddleState, self).parent_method()

    tracker = DependencyTracker(
        ExplicitSuperState.func_naming_the_class_to_skip, ExplicitSuperState
    )

    assert tracker.dependencies == {ExplicitSuperState.get_full_name(): {"value"}}
    assert not tracker.unresolved


def test_unresolvable_super_start_class_is_unresolved():
    """A super() whose starting class cannot be named cannot say which member runs."""

    class OpaqueSuperState(SuperParentState):
        def func_naming_a_non_ancestor(self) -> int:
            """Name something that is none of this state's ancestors.

            Returns:
                Whatever the implementation it reaches returns.
            """
            # Never runs: what it would reach is what the analysis cannot say.
            return super(_PlainThing, self).parent_method()  # pyright: ignore[reportArgumentType]

    tracker = DependencyTracker(
        OpaqueSuperState.func_naming_a_non_ancestor, OpaqueSuperState
    )

    assert tracker.dependencies == {}
    assert tracker.unresolved == {OpaqueSuperState}


def test_super_start_class_held_by_a_local_is_unresolved():
    """A super() whose starting class sits in a local cannot be named from bytecode."""

    class MiddleOperandState(SuperParentState):
        extra: int = 0

        def parent_method(self) -> int:
            """Read this class's own field, which the explicit super() skips.

            Returns:
                The extra.
            """
            return self.extra

    class LocalOperandState(MiddleOperandState):
        def func_naming_a_local_class(self) -> int:
            """Reach the parent through a class held in a local variable.

            Returns:
                Whatever the implementation it reaches returns.
            """
            middle = MiddleOperandState
            return super(middle, self).parent_method()

    tracker = DependencyTracker(
        LocalOperandState.func_naming_a_local_class, LocalOperandState
    )

    # The compiler hands the class and the state over in one instruction, whose two
    # names this cannot tell apart from any other pair of locals.
    assert tracker.dependencies == {}
    assert tracker.unresolved == {LocalOperandState}


def test_self_recursion_marks_unresolved():
    """A method that calls itself cannot be scanned to a bound, so it widens."""

    class RecursiveState(SuperParentState):
        extra: int = 0

        def recurse(self) -> int:
            """Call itself, reading a field on the way.

            Returns:
                The value plus whatever the next call returns.
            """
            return self.value + self.recurse()

        def func_calling_recursion(self) -> int:
            """Call the self-recursive method.

            Returns:
                The recursive result.
            """
            return self.recurse() + self.extra

    tracker = DependencyTracker(RecursiveState.func_calling_recursion, RecursiveState)

    assert tracker.unresolved == {RecursiveState}
    # Widening is up to _deps(); the analysis itself still reports what it found.
    assert RecursiveState.get_full_name() in tracker.dependencies


def test_nested_function_argument_dependencies():
    """Test tracking dependencies in a nested function called with the state."""

    def func_with_nested_arg(self: DependencyTestState):
        def inner(st):
            return st.count

        return inner(self)

    tracker = DependencyTracker(func_with_nested_arg, DependencyTestState)

    expected_deps = {DependencyTestState.get_full_name(): {"count"}}
    assert tracker.dependencies == expected_deps
    assert not tracker.unresolved


def test_nested_lambda_argument_dependencies():
    """Test tracking dependencies in a lambda called with the state."""

    def func_with_lambda_arg(self: DependencyTestState):
        scaled = lambda st: st.count * 2  # noqa: E731

        return scaled(self)

    tracker = DependencyTracker(func_with_lambda_arg, DependencyTestState)

    expected_deps = {DependencyTestState.get_full_name(): {"count"}}
    assert tracker.dependencies == expected_deps
    assert not tracker.unresolved


def test_nested_function_argument_with_fetched_state_dependencies():
    """A nested function called with a fetched state tracks that state's fields."""

    async def func_with_nested_arg(self: DependencyTestState):
        other = await self.get_state(AnotherTestState)

        def inner(st):
            return st.value

        return inner(other)

    tracker = DependencyTracker(func_with_nested_arg, DependencyTestState)

    assert tracker.dependencies == {AnotherTestState.get_full_name(): {"value"}}
    assert not tracker.unresolved


def test_aliased_self_dependencies():
    """Test tracking dependencies through a local alias of self."""

    def func_with_alias(self: DependencyTestState):
        st = self
        return st.count

    tracker = DependencyTracker(func_with_alias, DependencyTestState)

    expected_deps = {DependencyTestState.get_full_name(): {"count"}}
    assert tracker.dependencies == expected_deps
    assert not tracker.unresolved


def func_returning_self_untouched(self: DependencyTestState):
    """Hold self in a local without reading through it.

    Returns:
        A constant.
    """
    st = self  # noqa: F841
    return 1


def test_aliased_self_without_reads_has_no_dependencies():
    """Aliasing self is not a dependency; reading through the alias is."""
    tracker = DependencyTracker(func_returning_self_untouched, DependencyTestState)

    assert not tracker.dependencies
    assert not tracker.unresolved


def func_with_rebound_local_function(self: DependencyTestState):
    """Call a local name that has since been rebound to another function.

    Args:
        self: The state.

    Returns:
        The rebound helper's result.
    """

    def inner(st):
        return st.count

    inner = _reads_state_and_more  # noqa: F811  # pyright: ignore[reportAssignmentType]
    return inner(self)


def test_rebound_local_function_is_unresolved():
    """A local function name rebound to something else cannot be read from its old body."""
    tracker = DependencyTracker(func_with_rebound_local_function, DependencyTestState)

    assert tracker.unresolved == {DependencyTestState}


def func_with_state_as_default_argument(self: DependencyTestState):
    """Capture the state as a lambda default and read through it when called.

    Args:
        self: The state.

    Returns:
        The count read through the captured state.
    """
    read = lambda st=self: st.count  # noqa: E731
    return read()


def test_state_captured_as_a_default_argument_is_unresolved():
    """A state packed into a default argument leaves the analysis like any other value."""
    tracker = DependencyTracker(
        func_with_state_as_default_argument, DependencyTestState
    )

    assert tracker.unresolved == {DependencyTestState}


def func_with_module_level_helper(self: DependencyTestState):
    """Read the state through a module level helper.

    Args:
        self: The state.

    Returns:
        The helper's result.
    """
    return _reads_state_and_more(self)


def func_with_module_level_helper_and_extra_arg(self: DependencyTestState, extra: int):
    """Read the state through a module level helper, passing another argument too.

    Args:
        self: The state.
        extra: An unrelated argument.

    Returns:
        The helper's result.
    """
    return _reads_state_and_more(self, extra)


def func_with_module_level_helper_and_field_arg(self: DependencyTestState):
    """Read the state through a module level helper, passing a field read after it.

    Args:
        self: The state.

    Returns:
        The helper's result.
    """
    return _reads_state_and_more(self, self.count)


def func_with_module_level_helper_by_keyword(self: DependencyTestState):
    """Read the state through a module level helper called by keyword.

    Args:
        self: The state.

    Returns:
        The helper's result.
    """
    return _reads_state_and_more(state=self)


def func_with_getattr(self: DependencyTestState):
    """Read a field whose name is computed.

    Returns:
        The field value.
    """
    return getattr(self, "count")  # noqa: B009


def func_with_self_in_container(self: DependencyTestState):
    """Read a field through the state boxed in a list.

    Returns:
        The field value.
    """
    return [self][0].count


def func_returning_self(self: DependencyTestState):
    """Hand the state itself back to the caller.

    Returns:
        The state.
    """
    return self


def func_comparing_self(self: DependencyTestState, other):
    """Compare the state against another object.

    Args:
        self: The state.
        other: Another object.

    Returns:
        Whether the two are the same object.
    """
    return self is other


@pytest.mark.parametrize(
    "func",
    [
        func_with_module_level_helper,
        func_with_module_level_helper_and_extra_arg,
        func_with_module_level_helper_and_field_arg,
        func_with_module_level_helper_by_keyword,
        func_with_getattr,
        func_with_self_in_container,
        func_returning_self,
        func_comparing_self,
    ],
    ids=[
        "helper(self)",
        "helper(self, extra)",
        "helper(self, self.count)",
        "helper(st=self)",
        "getattr(self, ...)",
        "[self][0].count",
        "return self",
        "self is other",
    ],
)
def test_state_leaving_the_analysis_is_unresolved(func):
    """A state value consumed as a value, not read through, cannot be followed.

    Args:
        func: The function whose state reads escape the analysis.
    """
    tracker = DependencyTracker(func, DependencyTestState)

    assert tracker.unresolved == {DependencyTestState}


def func_with_plain_locals(self: DependencyTestState, thing: _PlainThing):
    """Read nothing but locals, a comprehension, and a plain object's attribute.

    Args:
        self: The state.
        thing: An object that is not state.

    Returns:
        A number.
    """
    total = 3
    names = ["a", "b"]
    return (
        total + len(names) + thing.field + sum(1 for name in names if len(name) > total)
    )


def func_with_self_and_self_comparison(self: DependencyTestState):
    """Compare two fields of the same state.

    Returns:
        Whether the fields are equal.
    """
    return self.count == self.name


def func_with_container_of_field_values(self: DependencyTestState):
    """Build a container out of field values.

    Returns:
        The container.
    """
    return [self.count, self.name, {"n": self.items}]


def func_with_class_name(self: DependencyTestState):
    """Read the state's class name, which is not state data.

    Returns:
        The class name.
    """
    return self.__class__.__name__


async def func_with_get_state_and_call(self: DependencyTestState):
    """Read another state and pass its field to a function.

    Returns:
        The other state's value, doubled.
    """
    other = await self.get_state(AnotherTestState)
    return len(other.text) + max(1, other.value)


def func_with_lambda_passed_as_argument(self: DependencyTestState):
    """Sort state fields with a lambda that is an argument, not a stored function.

    Returns:
        How many items there are, plus the shortest one's length.
    """
    ordered = sorted(self.items, key=lambda item: len(item))
    return len(ordered) + self.count


@pytest.mark.parametrize(
    "func",
    [
        func_with_plain_locals,
        func_with_self_and_self_comparison,
        func_with_container_of_field_values,
        func_with_class_name,
        func_with_get_state_and_call,
        func_with_lambda_passed_as_argument,
    ],
    ids=[
        "locals_and_object",
        "self.field == self.field",
        "container_of_values",
        "__class__.__name__",
        "get_state_and_calls",
        "lambda_as_argument",
    ],
)
def test_ordinary_getters_are_not_marked_unresolved(func):
    """Reading values, rather than the state itself, keeps the dependency set precise.

    Args:
        func: The function to analyse.
    """
    tracker = DependencyTracker(func, DependencyTestState)

    assert not tracker.unresolved


def test_ordinary_getters_keep_their_dependencies():
    """The forms covered above still report exactly the fields they read."""
    assert DependencyTracker(
        func_with_self_and_self_comparison, DependencyTestState
    ).dependencies == {DependencyTestState.get_full_name(): {"count", "name"}}
    assert DependencyTracker(
        func_with_container_of_field_values, DependencyTestState
    ).dependencies == {DependencyTestState.get_full_name(): {"count", "name", "items"}}
    assert not DependencyTracker(func_with_class_name, DependencyTestState).dependencies
    assert DependencyTracker(
        func_with_get_state_and_call, DependencyTestState
    ).dependencies == {AnotherTestState.get_full_name(): {"text", "value"}}
    assert DependencyTracker(
        func_with_lambda_passed_as_argument, DependencyTestState
    ).dependencies == {DependencyTestState.get_full_name(): {"count", "items"}}


class MethodArgumentState(State):
    """State with a method that takes a field of its own as an argument."""

    name: str = ""

    def prefixed_length(self, prefix: str) -> int:
        """Count the name with the prefix in front of it.

        Args:
            prefix: What the caller puts in front of the name.

        Returns:
            The length of the name plus the prefix.
        """
        return len(prefix) + len(self.name)


def func_with_field_passed_to_own_method(self: MethodArgumentState) -> int:
    """Read a field, then hand it to this state's own method as an argument.

    Args:
        self: The state.

    Returns:
        The method's result.
    """
    return self.prefixed_length(self.name)


def test_field_passed_to_a_method_is_not_a_state_escape():
    """The state loaded again for an argument was read through, not handed over."""
    tracker = DependencyTracker(
        func_with_field_passed_to_own_method, MethodArgumentState
    )

    assert not tracker.unresolved
    assert tracker.dependencies == {MethodArgumentState.get_full_name(): {"name"}}
