"""Integration tests for dependency tracking with computed vars."""

from __future__ import annotations

import logging

import pytest
from reflex_base import constants

import reflex as rx
from reflex.state import BaseState, State

_INCOMPLETE_DEPS_MARK = "cannot follow"
"""Substring of the warning raised when auto-tracking has to widen a computed var."""


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


def test_super_computed_var_dependencies():
    """A getter reaching the parent through super() depends on what the parent reads."""

    class SuperVarParent(State):
        base: int = 0

        def doubled(self) -> int:
            return self.base * 2

    class SuperVarState(SuperVarParent):
        bonus: int = 0

        @rx.var
        def total(self) -> int:
            return super().doubled() + self.bonus

    computed = SuperVarState.computed_vars["total"]

    assert computed._deps(objclass=SuperVarState) == {
        SuperVarState.get_full_name(): {"base", "bonus"}
    }


def test_explicit_super_start_class_computed_var_dependencies():
    """A getter naming super()'s starting class depends on the implementation it reaches."""

    class ExplicitSuperParent(State):
        base: int = 0

        def doubled(self) -> int:
            return self.base * 2

    class ExplicitSuperMiddle(ExplicitSuperParent):
        skipped: int = 0

        def doubled(self) -> int:
            return self.skipped

    class ExplicitSuperState(ExplicitSuperMiddle):
        bonus: int = 0

        @rx.var
        def total(self) -> int:
            return super(ExplicitSuperMiddle, self).doubled() + self.bonus

    computed = ExplicitSuperState.computed_vars["total"]

    # `skipped` belongs to the override this super() names, so it runs past.
    assert computed._deps(objclass=ExplicitSuperState) == {
        ExplicitSuperState.get_full_name(): {"base", "bonus"}
    }


def test_nested_argument_computed_var_dependencies():
    """A getter that hands itself to a nested function tracks the fields it reads."""

    class NestedArgState(State):
        base: int = 0
        bonus: int = 0

        @rx.var
        def total(self) -> int:
            def scaled(st) -> int:
                return st.base * 2

            return scaled(self) + self.bonus

    computed = NestedArgState.computed_vars["total"]

    assert computed._deps(objclass=NestedArgState) == {
        NestedArgState.get_full_name(): {"base", "bonus"}
    }


def test_aliased_self_computed_var_dependencies():
    """A getter that aliases self tracks the fields read through the alias."""

    class AliasedSelfState(State):
        base: int = 0

        @rx.var
        def total(self) -> int:
            st = self
            return st.base * 2

    computed = AliasedSelfState.computed_vars["total"]

    assert computed._deps(objclass=AliasedSelfState) == {
        AliasedSelfState.get_full_name(): {"base"}
    }


def test_untrackable_getter_depends_on_the_whole_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the getter cannot be followed, every var of its state invalidates it, once warned."""
    with caplog.at_level(logging.WARNING, logger="reflex_base.vars.base"):
        # A BaseState root: widened edges here must not land on the shared tree.
        class EscapingState(BaseState):
            base: int = 0
            bonus: int = 0

            @rx.var
            def total(self) -> int:
                return getattr(self, "base") + self.bonus  # noqa: B009

    deps = EscapingState.computed_vars["total"]._deps(objclass=EscapingState)

    assert deps == {
        # The routing fields count too: a getter this unfollowable may have read them.
        EscapingState.get_full_name(): {"base", "bonus", *constants.ROUTER_VARS}
    }
    assert len([r for r in caplog.records if _INCOMPLETE_DEPS_MARK in r.message]) == 1


def test_widening_covers_the_client_vars_read_through_self() -> None:
    """A getter that could have read the routing or hydration of its own state waits for them."""

    # A substate of the app root, home of the client vars; no computed var of its own.
    class WidenedFrameState(State):
        base: int = 0

    def getter(self) -> int:
        return 0

    widened = rx.var(getter)._widen_deps(WidenedFrameState, {}, (WidenedFrameState,))

    names = widened[WidenedFrameState.get_full_name()]
    assert "base" in names
    assert set(constants.ROUTER_VARS) <= names
    assert "is_hydrated" in names
    # `router` is a switchboard over those fields rather than a var with a field of
    # its own, so naming it would read back as the deprecated deps=["router"].
    assert names == set(WidenedFrameState.vars) - {
        constants.ROUTER,
        constants.ROUTER_DATA,
    }


def test_widening_for_another_state_leaves_out_the_client_vars() -> None:
    """Only a state read through `self` can have been read through the client vars."""

    class WidenedClientState(State):
        base: int = 0

    class WidenedOtherState(BaseState):
        value: int = 0

    def getter(self) -> int:
        return 0

    widened = rx.var(getter)._widen_deps(WidenedClientState, {}, (WidenedOtherState,))

    names = widened[WidenedOtherState.get_full_name()]
    assert names == {"value"}
    assert names.isdisjoint(BaseState._NON_DATA_VAR_NAMES)


def test_widened_router_deps_are_not_the_deprecated_string(caplog) -> None:
    """Widening depends on the routing fields themselves, so no deprecation is read back."""
    with caplog.at_level(logging.WARNING):
        # A BaseState root, so its routing vars are its own and the edges it registers
        # stay inside this test instead of marking up the shared app tree.
        class WidenedRouterState(BaseState):
            base: int = 0

            @rx.var
            def total(self) -> int:
                return getattr(self, "base")  # noqa: B009

    deps = WidenedRouterState.computed_vars["total"]._deps(objclass=WidenedRouterState)
    assert constants.ROUTER_PAGE in deps[WidenedRouterState.get_full_name()]

    # The edge lands on the state the routing field is defined on, which for a var
    # reading `self` is the state whose data escaped the analysis.
    assert (
        WidenedRouterState.get_full_name(),
        "total",
    ) in WidenedRouterState._var_dependencies[constants.ROUTER_PAGE]
    assert not [r for r in caplog.records if 'deps=["router"]' in r.message]


def test_widening_includes_the_backend_fields() -> None:
    """Widening covers the fields that stay off the frontend, since they dirty all the same."""

    class WidenedBackendState(BaseState):
        _hidden: int = 0
        shown: int = 0

        @rx.var
        def total(self) -> int:
            return getattr(self, "_hidden") + self.shown  # noqa: B009

    deps = WidenedBackendState.computed_vars["total"]._deps(
        objclass=WidenedBackendState
    )

    # Neither field is readable from the getter's bytecode, so both must invalidate.
    assert deps == {
        WidenedBackendState.get_full_name(): {
            "_hidden",
            "shown",
            *constants.ROUTER_VARS,
        }
    }


def test_incomplete_deps_warning_is_not_repeated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The warning about widened dependencies is raised once per computed var.

    Args:
        caplog: The captured log records.
    """
    with caplog.at_level(logging.WARNING, logger="reflex_base.vars.base"):

        class TwiceWarnedState(BaseState):
            base: int = 0

            @rx.var
            def total(self) -> int:
                return getattr(self, "base")  # noqa: B009

    computed = TwiceWarnedState.computed_vars["total"]
    for _ in range(3):
        computed._deps(objclass=TwiceWarnedState)

    assert len([r for r in caplog.records if _INCOMPLETE_DEPS_MARK in r.message]) == 1


def test_ordinary_computed_vars_are_not_widened_or_warned(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Getters the tracker understands keep their exact dependency set and stay quiet."""
    with caplog.at_level(logging.WARNING, logger="reflex_base.vars.base"):

        class QuietState(State):
            base: int = 0
            flag: bool = True
            other: int = 1

            @rx.var
            def total(self) -> int:
                return self.base if self.flag else self.other

    assert not [r for r in caplog.records if _INCOMPLETE_DEPS_MARK in r.message]
    assert QuietState.computed_vars["total"]._deps(objclass=QuietState) == {
        QuietState.get_full_name(): {"base", "flag", "other"}
    }


def test_explicit_deps_are_never_widened() -> None:
    """auto_deps=False means the deps the author wrote, exactly."""

    class ExplicitDepState(State):
        base: int = 0
        other: int = 0

        @rx.var(deps=["base"], auto_deps=False)
        def total(self) -> int:
            return getattr(self, "base") + self.other  # noqa: B009

    assert ExplicitDepState.computed_vars["total"]._deps(objclass=ExplicitDepState) == {
        ExplicitDepState.get_full_name(): {"base"}
    }


def test_uncached_computed_var_registers_no_dependencies() -> None:
    """cache=False vars recompute on access, so they are not registered as dependents."""

    # A BaseState root, so its always-dirty var does not mark up the shared tree.
    class UncachedEscapeState(BaseState):
        base: int = 0

        @rx.var(cache=False)
        def total(self) -> int:
            return getattr(self, "base")  # noqa: B009

    assert all(
        "total" not in {cvar_name for _, cvar_name in dependents}
        for dependents in UncachedEscapeState._var_dependencies.values()
    )
