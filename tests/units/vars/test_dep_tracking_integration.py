"""Integration tests for dependency tracking with computed vars."""

from __future__ import annotations

import sys

import pytest

import reflex as rx
from reflex.state import State


class IntegrationTestState(State):
    """State for integration testing with dependency tracker."""

    count: int = 0
    name: str = "test"
    items: list[str] = []

    @rx.var
    def computed_count(self) -> int:
        """A computed var that depends on count.

        Returns:
            The double of the count.
        """
        return self.count * 2

    @rx.var
    def computed_name_length(self) -> int:
        """A computed var that depends on name.

        Returns:
            The length of the name.
        """
        return len(self.name)

    @rx.var
    def complex_computed(self) -> str:
        """A computed var with complex dependencies.

        Returns:
            A string combining name, count, and items length.
        """
        return f"{self.name}_{self.count}_{len(self.items)}"

    def helper_method(self) -> int:
        """A helper method that accesses state.

        Returns:
            The sum of count and the length of name.
        """
        return self.count + len(self.name)


class OtherIntegrationState(State):
    """Another state for cross-state dependency testing."""

    value: int = 42

    @rx.var
    def doubled_value(self) -> int:
        """A computed var that depends on value.

        Returns:
            The double of the value.
        """
        return self.value * 2


def test_computed_var_dependencies():
    """Test that computed vars automatically track dependencies correctly."""
    # Test the _deps method which uses DependencyTracker internally
    computed_count = IntegrationTestState.computed_vars["computed_count"]
    deps = computed_count._deps(objclass=IntegrationTestState)

    expected_deps = {IntegrationTestState.get_full_name(): {"count"}}
    assert deps == expected_deps


def test_complex_computed_var_dependencies():
    """Test complex computed var with multiple dependencies."""
    complex_computed = IntegrationTestState.computed_vars["complex_computed"]
    deps = complex_computed._deps(objclass=IntegrationTestState)

    expected_deps = {IntegrationTestState.get_full_name(): {"name", "count", "items"}}
    assert deps == expected_deps


def test_multiple_computed_vars():
    """Test that different computed vars track their own dependencies."""
    computed_count = IntegrationTestState.computed_vars["computed_count"]
    computed_name_length = IntegrationTestState.computed_vars["computed_name_length"]

    count_deps = computed_count._deps(objclass=IntegrationTestState)
    name_deps = computed_name_length._deps(objclass=IntegrationTestState)

    assert count_deps == {IntegrationTestState.get_full_name(): {"count"}}
    assert name_deps == {IntegrationTestState.get_full_name(): {"name"}}


def test_method_dependencies_integration():
    """Test tracking dependencies through method calls in computed vars."""

    class StateWithMethodDeps(State):
        value: int = 0

        def helper_method(self):
            return self.value

        @rx.var
        def computed_with_method(self) -> int:
            return self.helper_method() * 2

    computed = StateWithMethodDeps.computed_vars["computed_with_method"]
    deps = computed._deps(objclass=StateWithMethodDeps)

    expected_deps = {StateWithMethodDeps.get_full_name(): {"value"}}
    assert deps == expected_deps


def test_cross_state_dependencies():
    """Test dependencies across different state classes."""

    class StateWithCrossDeps(State):
        @rx.var
        async def cross_state_computed(self) -> int:
            other = await self.get_state(OtherIntegrationState)
            return other.value + 10

    computed = StateWithCrossDeps.computed_vars["cross_state_computed"]
    deps = computed._deps(objclass=StateWithCrossDeps)

    expected_deps = {OtherIntegrationState.get_full_name(): {"value"}}
    assert deps == expected_deps


@pytest.mark.skipif(
    sys.version_info < (3, 11), reason="Requires Python 3.11+ for positions"
)
def test_cross_state_get_var_value_dependencies():
    """Track dependencies when get_var_value reads a var from another state."""

    class StateWithCrossVarValueDeps(State):
        @rx.var
        async def cross_state_var_value(self) -> int:
            return await self.get_var_value(OtherIntegrationState.value)  # pyright: ignore[reportArgumentType]

    computed = StateWithCrossVarValueDeps.computed_vars["cross_state_var_value"]
    deps = computed._deps(objclass=StateWithCrossVarValueDeps)

    expected_deps = {OtherIntegrationState.get_full_name(): {"value"}}
    assert deps == expected_deps
    assert (
        StateWithCrossVarValueDeps.get_full_name(),
        "cross_state_var_value",
    ) in OtherIntegrationState._var_dependencies["value"]


def test_nested_function_in_computed_var():
    """Test that nested functions within computed vars track dependencies."""

    class StateWithNested(State):
        items: list[str] = []
        multiplier: int = 2

        @rx.var
        def nested_computed(self) -> int:
            def inner():
                return len(self.items) * self.multiplier

            return inner()

    computed = StateWithNested.computed_vars["nested_computed"]
    deps = computed._deps(objclass=StateWithNested)

    expected_deps = {StateWithNested.get_full_name(): {"items", "multiplier"}}
    assert deps == expected_deps


def test_list_comprehension_in_computed_var():
    """Test that list comprehensions in computed vars track dependencies."""

    class StateWithComprehension(State):
        items: list[str] = []
        min_length: int = 3

        @rx.var
        def filtered_items(self) -> list[str]:
            return [item for item in self.items if len(item) >= self.min_length]

    computed = StateWithComprehension.computed_vars["filtered_items"]
    deps = computed._deps(objclass=StateWithComprehension)

    expected_deps = {StateWithComprehension.get_full_name(): {"items", "min_length"}}
    assert deps == expected_deps


def test_property_access_in_computed_var():
    """Test that property access in computed vars tracks dependencies."""

    class StateWithProperty(State):
        _internal_value: int = 0

        @property
        def value_property(self):
            return self._internal_value * 2

        @rx.var
        def computed_with_property(self) -> int:
            return self.value_property + 1

    computed = StateWithProperty.computed_vars["computed_with_property"]
    deps = computed._deps(objclass=StateWithProperty)

    expected_deps = {StateWithProperty.get_full_name(): {"_internal_value"}}
    assert deps == expected_deps


def test_no_dependencies_computed_var():
    """Test computed vars with no state dependencies."""

    class StateWithNoDeps(State):
        @rx.var
        def constant_computed(self) -> int:
            return 42

    computed = StateWithNoDeps.computed_vars["constant_computed"]
    deps = computed._deps(objclass=StateWithNoDeps)

    # Should have no dependencies
    assert deps == {}


def test_conditional_dependencies():
    """Test computed vars with conditional dependencies."""

    class StateWithConditional(State):
        flag: bool = True
        value_a: int = 10
        value_b: int = 20

        @rx.var
        def conditional_computed(self) -> int:
            return self.value_a if self.flag else self.value_b

    computed = StateWithConditional.computed_vars["conditional_computed"]
    deps = computed._deps(objclass=StateWithConditional)

    # Should track all potentially accessed attributes
    expected_deps = {
        StateWithConditional.get_full_name(): {"flag", "value_a", "value_b"}
    }
    assert deps == expected_deps


def test_error_handling_in_dependency_tracking():
    """Test that dependency tracking handles errors gracefully."""

    class StateWithError(State):
        value: int = 0

        @rx.var
        def computed_with_error(self) -> int:
            # This should still track 'value' even if there are other issues
            return self.value

    computed = StateWithError.computed_vars["computed_with_error"]
    deps = computed._deps(objclass=StateWithError)

    expected_deps = {StateWithError.get_full_name(): {"value"}}
    assert deps == expected_deps


def test_computed_var_dependency_on_inherited_mixin_computed_vars():
    """Track inherited mixin computed var deps for both async and sync vars."""

    class AuthMixin(State, mixin=True):
        @rx.var
        async def userinfo(self) -> dict[str, str]:
            return {"sub": "user-1"}

        @rx.var
        def user_id(self) -> str:
            return "user-1"

    class AuthState(AuthMixin, State):
        pass

    class AuthSubstate(AuthState):
        @rx.var
        async def is_authenticated(self) -> bool:
            return bool(await self.userinfo)

        @rx.var
        def has_user_id(self) -> bool:
            return bool(self.user_id)

    async_computed = AuthSubstate.computed_vars["is_authenticated"]
    async_deps = async_computed._deps(objclass=AuthSubstate)
    sync_computed = AuthSubstate.computed_vars["has_user_id"]
    sync_deps = sync_computed._deps(objclass=AuthSubstate)

    assert async_deps == {AuthState.get_full_name(): {"userinfo"}}
    assert sync_deps == {AuthState.get_full_name(): {"user_id"}}
    assert AuthState._var_dependencies["userinfo"] == {
        (AuthSubstate.get_full_name(), "is_authenticated")
    }
    assert AuthState._var_dependencies["user_id"] == {
        (AuthSubstate.get_full_name(), "has_user_id")
    }


def test_computed_var_dependency_on_inherited_concrete_computed_vars():
    """Track inherited concrete parent computed var deps for async and sync vars."""

    class AuthParentState(State):
        @rx.var
        async def userinfo(self) -> dict[str, str]:
            return {"sub": "user-1"}

        @rx.var
        def user_id(self) -> str:
            return "user-1"

    class AuthSubstate(AuthParentState):
        @rx.var
        async def is_authenticated(self) -> bool:
            return bool(await self.userinfo)

        @rx.var
        def has_user_id(self) -> bool:
            return bool(self.user_id)

    async_computed = AuthSubstate.computed_vars["is_authenticated"]
    async_deps = async_computed._deps(objclass=AuthSubstate)
    sync_computed = AuthSubstate.computed_vars["has_user_id"]
    sync_deps = sync_computed._deps(objclass=AuthSubstate)

    assert async_deps == {AuthParentState.get_full_name(): {"userinfo"}}
    assert sync_deps == {AuthParentState.get_full_name(): {"user_id"}}
    assert AuthParentState._var_dependencies["userinfo"] == {
        (AuthSubstate.get_full_name(), "is_authenticated")
    }
    assert AuthParentState._var_dependencies["user_id"] == {
        (AuthSubstate.get_full_name(), "has_user_id")
    }
