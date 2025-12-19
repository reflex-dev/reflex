"""Tests for dependency tracking functionality."""

from __future__ import annotations

import sys

import pytest

import reflex as rx
import tests.units.states.upload as tus_upload
from reflex.state import State
from reflex.utils.exceptions import VarValueError
from reflex.vars.dep_tracking import (
    DependencyTracker,
    UntrackedLocalVarError,
    get_cell_value,
)


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
            if self.board:
                pass

        return self.count

    tracker = DependencyTracker(func_with_nested, DependencyTestState)

    expected_deps = {DependencyTestState.get_full_name(): {"board", "count"}}
    assert tracker.dependencies == expected_deps


@pytest.mark.skipif(
    sys.version_info < (3, 11), reason="Requires Python 3.11+ for positions"
)
def test_get_var_value_functionality():
    """Test tracking dependencies when using get_var_value."""

    async def func_with_get_var_value(self: DependencyTestState):
        return await self.get_var_value(DependencyTestState.count)

    tracker = DependencyTracker(func_with_get_var_value, DependencyTestState)
    expected_deps = {DependencyTestState.get_full_name(): {"count"}}
    assert tracker.dependencies == expected_deps


@pytest.mark.skipif(
    sys.version_info < (3, 11), reason="Requires Python 3.11+ for positions"
)
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


@pytest.mark.skipif(
    sys.version_info < (3, 11), reason="Requires Python 3.11+ for positions"
)
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
