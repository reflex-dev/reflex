"""Unit tests for state and event handler minification."""

from __future__ import annotations

import pytest

from reflex.environment import MinifyMode, environment
from reflex.event import EVENT_ID_MARKER
from reflex.state import (
    BaseState,
    FrontendEventExceptionState,
    OnLoadInternalState,
    State,
    UpdateVarsInternalState,
    _int_to_minified_name,
    _minified_name_to_int,
)
from reflex.utils.exceptions import StateValueError


@pytest.fixture
def reset_minify_mode():
    """Reset minify modes to DISABLED after each test."""
    original_states = environment.REFLEX_MINIFY_STATES.get()
    original_events = environment.REFLEX_MINIFY_EVENTS.get()
    yield
    environment.REFLEX_MINIFY_STATES.set(original_states)
    environment.REFLEX_MINIFY_EVENTS.set(original_events)


class TestIntToMinifiedName:
    """Tests for _int_to_minified_name function."""

    def test_zero(self):
        """Test that 0 maps to 'a'."""
        assert _int_to_minified_name(0) == "a"

    def test_single_char(self):
        """Test single character mappings."""
        assert _int_to_minified_name(1) == "b"
        assert _int_to_minified_name(25) == "z"
        assert _int_to_minified_name(26) == "A"
        assert _int_to_minified_name(51) == "Z"
        assert _int_to_minified_name(52) == "$"
        assert _int_to_minified_name(53) == "_"

    def test_two_chars(self):
        """Test two character mappings (base 54)."""
        # 54 = 1*54 + 0 -> 'ba'
        assert _int_to_minified_name(54) == "ba"
        # 55 = 1*54 + 1 -> 'bb'
        assert _int_to_minified_name(55) == "bb"

    def test_unique_names(self):
        """Test that a large range of IDs produce unique names."""
        names = set()
        for i in range(10000):
            name = _int_to_minified_name(i)
            assert name not in names, f"Duplicate name {name} for id {i}"
            names.add(name)


class TestStateIdValidation:
    """Tests for state_id validation in __init_subclass__."""

    def test_state_with_explicit_id(self):
        """Test that a state can be created with an explicit state_id."""

        class TestState(BaseState, state_id=100):
            pass

        assert TestState._state_id == 100

    def test_state_without_id(self):
        """Test that a state can be created without state_id."""

        class TestState(BaseState):
            pass

        assert TestState._state_id is None

    def test_duplicate_state_id_among_siblings_raises(self):
        """Test that duplicate state_id among siblings raises StateValueError."""

        class ParentState(BaseState, state_id=200):
            pass

        class FirstChild(ParentState, state_id=10):
            pass

        with pytest.raises(StateValueError, match="Duplicate state_id=10"):

            class SecondChild(ParentState, state_id=10):
                pass

    def test_same_state_id_across_branches_allowed(self):
        """Test that the same state_id can be used in different branches."""

        class Root(BaseState, state_id=210):
            pass

        class BranchA(Root, state_id=1):
            pass

        class BranchB(Root, state_id=2):
            pass

        class LeafA(BranchA, state_id=5):
            pass

        class LeafB(BranchB, state_id=5):  # same state_id=5, different parent -- OK!
            pass

        # Both should succeed - state_id is per-parent (sibling uniqueness)
        assert LeafA._state_id == 5
        assert LeafB._state_id == 5
        # But they have different full names
        assert LeafA.get_parent_state() is BranchA
        assert LeafB.get_parent_state() is BranchB


class TestGetNameMinification:
    """Tests for get_name with minification modes."""

    def test_disabled_mode_uses_full_name(self, reset_minify_mode):
        """Test DISABLED mode always uses full name even with state_id."""
        environment.REFLEX_MINIFY_STATES.set(MinifyMode.DISABLED)

        class TestState(BaseState, state_id=300):
            pass

        # Clear the lru_cache to get fresh result
        TestState.get_name.cache_clear()

        name = TestState.get_name()
        # Should be full name, not minified
        assert "test_state" in name.lower()
        assert name != _int_to_minified_name(300)

    def test_enabled_mode_with_id_uses_minified(self, reset_minify_mode):
        """Test ENABLED mode with state_id uses minified name."""
        environment.REFLEX_MINIFY_STATES.set(MinifyMode.ENABLED)

        class TestState(BaseState, state_id=301):
            pass

        # Clear the lru_cache to get fresh result
        TestState.get_name.cache_clear()

        name = TestState.get_name()
        assert name == _int_to_minified_name(301)

    def test_enabled_mode_without_id_uses_full_name(self, reset_minify_mode):
        """Test ENABLED mode without state_id uses full name."""
        environment.REFLEX_MINIFY_STATES.set(MinifyMode.ENABLED)

        class TestState(BaseState):
            pass

        # Clear the lru_cache to get fresh result
        TestState.get_name.cache_clear()

        name = TestState.get_name()
        # Should contain the class name
        assert "test_state" in name.lower()

    def test_enforce_mode_without_id_raises(self, reset_minify_mode):
        """Test ENFORCE mode without state_id raises error during class definition."""
        environment.REFLEX_MINIFY_STATES.set(MinifyMode.ENFORCE)

        # Error is raised during class definition because get_name() is called
        # during __init_subclass__
        with pytest.raises(StateValueError, match="missing required state_id"):

            class TestState(BaseState):
                pass

    def test_enforce_mode_with_id_uses_minified(self, reset_minify_mode):
        """Test ENFORCE mode with state_id uses minified name."""
        environment.REFLEX_MINIFY_STATES.set(MinifyMode.ENFORCE)

        class TestState(BaseState, state_id=302):
            pass

        # Clear the lru_cache to get fresh result
        TestState.get_name.cache_clear()

        name = TestState.get_name()
        assert name == _int_to_minified_name(302)


class TestMixinState:
    """Tests for mixin states."""

    def test_mixin_no_state_id_required(self, reset_minify_mode):
        """Test that mixin states don't require state_id even in ENFORCE mode."""
        environment.REFLEX_MINIFY_STATES.set(MinifyMode.ENFORCE)

        class MixinState(BaseState, mixin=True):
            pass

        # Mixin states should not raise even without state_id
        assert MixinState._state_id is None
        # Mixin states have _mixin = True set, so get_name isn't typically called
        # but the class should be created without error

    def test_mixin_with_state_id_raises(self):
        """Test that mixin states cannot have state_id."""
        with pytest.raises(StateValueError, match="cannot have a state_id"):

            class MixinWithId(BaseState, mixin=True, state_id=999):
                pass


class TestEventIdValidation:
    """Tests for event_id validation in __init_subclass__."""

    def test_event_with_explicit_id(self):
        """Test that an event handler can be created with an explicit event_id."""
        import reflex as rx

        class TestState(BaseState, state_id=400):
            @rx.event(event_id=0)
            def my_handler(self):
                pass

        assert 0 in TestState._event_id_to_name
        assert TestState._event_id_to_name[0] == "my_handler"

    def test_event_without_id(self):
        """Test that an event handler can be created without event_id."""
        import reflex as rx

        class TestState(BaseState, state_id=401):
            @rx.event
            def my_handler(self):
                pass

        # Should not be in the registry
        assert 0 not in TestState._event_id_to_name

    def test_duplicate_event_id_within_state_raises(self):
        """Test that duplicate event_id within same state raises StateValueError."""
        import reflex as rx

        with pytest.raises(StateValueError, match="Duplicate event_id=0"):

            class TestState(BaseState, state_id=402):
                @rx.event(event_id=0)
                def handler1(self):
                    pass

                @rx.event(event_id=0)
                def handler2(self):
                    pass

    def test_same_event_id_across_states_allowed(self):
        """Test that same event_id can be used in different state classes."""
        import reflex as rx

        class StateA(BaseState, state_id=403):
            @rx.event(event_id=0)
            def handler(self):
                pass

        class StateB(BaseState, state_id=404):
            @rx.event(event_id=0)
            def handler(self):
                pass

        # Both should succeed - event_id is per-state
        assert StateA._event_id_to_name[0] == "handler"
        assert StateB._event_id_to_name[0] == "handler"

    def test_event_id_stored_on_function(self):
        """Test that event_id is stored as EVENT_ID_MARKER on the function."""
        import reflex as rx

        @rx.event(event_id=42)
        def standalone_handler(self):
            pass

        assert hasattr(standalone_handler, EVENT_ID_MARKER)
        assert getattr(standalone_handler, EVENT_ID_MARKER) == 42


class TestEventHandlerMinification:
    """Tests for event handler name minification in get_event_handler_parts."""

    def test_disabled_mode_uses_full_name(self, reset_minify_mode):
        """Test DISABLED mode uses full event name even with event_id."""
        import reflex as rx
        from reflex.utils.format import get_event_handler_parts

        environment.REFLEX_MINIFY_EVENTS.set(MinifyMode.DISABLED)

        class TestState(BaseState, state_id=500):
            @rx.event(event_id=0)
            def my_handler(self):
                pass

        handler = TestState.event_handlers["my_handler"]
        _, event_name = get_event_handler_parts(handler)

        # Should use full name, not minified
        assert event_name == "my_handler"

    def test_enabled_mode_with_id_uses_minified(self, reset_minify_mode):
        """Test ENABLED mode with event_id uses minified name."""
        import reflex as rx
        from reflex.utils.format import get_event_handler_parts

        environment.REFLEX_MINIFY_EVENTS.set(MinifyMode.ENABLED)

        class TestState(BaseState, state_id=501):
            @rx.event(event_id=5)
            def my_handler(self):
                pass

        TestState.get_name.cache_clear()
        handler = TestState.event_handlers["my_handler"]
        _, event_name = get_event_handler_parts(handler)

        # Should use minified name
        assert event_name == _int_to_minified_name(5)
        assert event_name == "f"

    def test_enabled_mode_without_id_uses_full_name(self, reset_minify_mode):
        """Test ENABLED mode without event_id uses full name."""
        import reflex as rx
        from reflex.utils.format import get_event_handler_parts

        environment.REFLEX_MINIFY_EVENTS.set(MinifyMode.ENABLED)

        class TestState(BaseState, state_id=502):
            @rx.event
            def my_handler(self):
                pass

        TestState.get_name.cache_clear()
        handler = TestState.event_handlers["my_handler"]
        _, event_name = get_event_handler_parts(handler)

        # Should use full name
        assert event_name == "my_handler"

    def test_enforce_mode_without_event_id_raises(self, reset_minify_mode):
        """Test ENFORCE mode without event_id raises error during class definition."""
        import reflex as rx

        environment.REFLEX_MINIFY_EVENTS.set(MinifyMode.ENFORCE)

        with pytest.raises(StateValueError, match="missing required event_id"):

            class TestState(BaseState, state_id=503):
                @rx.event
                def my_handler(self):
                    pass

    def test_enforce_mode_with_event_id_works(self, reset_minify_mode):
        """Test ENFORCE mode with event_id creates state successfully."""
        import reflex as rx
        from reflex.utils.format import get_event_handler_parts

        environment.REFLEX_MINIFY_EVENTS.set(MinifyMode.ENFORCE)

        class TestState(BaseState, state_id=504):
            @rx.event(event_id=0)
            def my_handler(self):
                pass

        TestState.get_name.cache_clear()
        handler = TestState.event_handlers["my_handler"]
        _, event_name = get_event_handler_parts(handler)

        # Should use minified name
        assert event_name == _int_to_minified_name(0)
        assert event_name == "a"


class TestMixinEventHandlers:
    """Tests for event handlers from mixin states."""

    def test_mixin_event_id_preserved(self, reset_minify_mode):
        """Test that event_id from mixin handlers is preserved when inherited."""
        import reflex as rx
        from reflex.utils.format import get_event_handler_parts

        environment.REFLEX_MINIFY_EVENTS.set(MinifyMode.ENABLED)

        class MixinState(BaseState, mixin=True):
            @rx.event(event_id=10)
            def mixin_handler(self):
                pass

        # Need to inherit from both mixin AND a non-mixin base (BaseState)
        # to create a non-mixin concrete state
        class ConcreteState(MixinState, BaseState, state_id=600):
            @rx.event(event_id=0)
            def own_handler(self):
                pass

        ConcreteState.get_name.cache_clear()

        # Both handlers should have their event_ids preserved
        assert 10 in ConcreteState._event_id_to_name
        assert ConcreteState._event_id_to_name[10] == "mixin_handler"
        assert 0 in ConcreteState._event_id_to_name
        assert ConcreteState._event_id_to_name[0] == "own_handler"

        # Check minified names
        mixin_handler = ConcreteState.event_handlers["mixin_handler"]
        own_handler = ConcreteState.event_handlers["own_handler"]

        _, mixin_name = get_event_handler_parts(mixin_handler)
        _, own_name = get_event_handler_parts(own_handler)

        assert mixin_name == _int_to_minified_name(10)  # "k"
        assert own_name == _int_to_minified_name(0)  # "a"

    def test_mixin_event_id_conflict_raises(self, reset_minify_mode):
        """Test that conflicting event_ids from mixin and concrete state raises error."""
        import reflex as rx

        environment.REFLEX_MINIFY_EVENTS.set(MinifyMode.ENABLED)

        class MixinState(BaseState, mixin=True):
            @rx.event(event_id=0)
            def mixin_handler(self):
                pass

        with pytest.raises(StateValueError, match="Duplicate event_id=0"):
            # Need to inherit from both mixin AND a non-mixin base (BaseState)
            class ConcreteState(MixinState, BaseState, state_id=601):
                @rx.event(event_id=0)
                def own_handler(self):
                    pass


class TestMinifiedNameToInt:
    """Tests for _minified_name_to_int reverse conversion."""

    def test_single_char(self):
        """Test single character conversion."""
        assert _minified_name_to_int("a") == 0
        assert _minified_name_to_int("b") == 1
        assert _minified_name_to_int("z") == 25
        assert _minified_name_to_int("A") == 26
        assert _minified_name_to_int("Z") == 51

    def test_roundtrip(self):
        """Test that int -> minified -> int roundtrip works."""
        for i in range(1000):
            minified = _int_to_minified_name(i)
            result = _minified_name_to_int(minified)
            assert result == i, f"Roundtrip failed for {i}: {minified} -> {result}"

    def test_invalid_char_raises(self):
        """Test that invalid characters raise ValueError."""
        with pytest.raises(ValueError, match="Invalid character"):
            _minified_name_to_int("!")

    def test_state_has_state_id_zero(self):
        """Test that the root State class has state_id=0."""
        assert State._state_id == 0
        assert State.__module__ == "reflex.state"
        assert State.__name__ == "State"

    def test_next_sibling_state_id(self):
        """Test finding next available state_id among siblings."""

        class Parent(BaseState, state_id=700):
            pass

        class Child0(Parent, state_id=0):
            pass

        class Child1(Parent, state_id=1):
            pass

        # Find first gap starting from 0 among Parent's children
        used_ids = {
            child._state_id
            for child in Parent.class_subclasses
            if child._state_id is not None
        }
        next_id = 0
        while next_id in used_ids:
            next_id += 1

        assert next_id == 2


class TestInternalStateIds:
    """Tests for internal state classes having correct state_id values."""

    def test_state_has_id_0(self):
        """Test that the base State class has state_id=0."""
        assert State._state_id == 0

    def test_frontend_exception_state_has_id_0(self):
        """Test that FrontendEventExceptionState has state_id=0."""
        assert FrontendEventExceptionState._state_id == 0

    def test_update_vars_internal_state_has_id_1(self):
        """Test that UpdateVarsInternalState has state_id=1."""
        assert UpdateVarsInternalState._state_id == 1

    def test_on_load_internal_state_has_id_2(self):
        """Test that OnLoadInternalState has state_id=2."""
        assert OnLoadInternalState._state_id == 2

    def test_internal_states_minified_names(self, reset_minify_mode):
        """Test that internal states get correct minified names when enabled."""
        environment.REFLEX_MINIFY_STATES.set(MinifyMode.ENABLED)

        # Clear the lru_cache to get fresh results
        State.get_name.cache_clear()
        FrontendEventExceptionState.get_name.cache_clear()
        UpdateVarsInternalState.get_name.cache_clear()
        OnLoadInternalState.get_name.cache_clear()

        # State (id=0) -> "a"
        assert State.get_name() == "a"
        # FrontendEventExceptionState (id=0) -> "a"
        assert FrontendEventExceptionState.get_name() == "a"
        # UpdateVarsInternalState (id=1) -> "b"
        assert UpdateVarsInternalState.get_name() == "b"
        # OnLoadInternalState (id=2) -> "c"
        assert OnLoadInternalState.get_name() == "c"

    def test_internal_states_full_names_when_disabled(self, reset_minify_mode):
        """Test that internal states use full names when minification is disabled."""
        environment.REFLEX_MINIFY_STATES.set(MinifyMode.DISABLED)

        # Clear the lru_cache to get fresh results
        State.get_name.cache_clear()
        FrontendEventExceptionState.get_name.cache_clear()
        UpdateVarsInternalState.get_name.cache_clear()
        OnLoadInternalState.get_name.cache_clear()

        # Should contain the class name pattern
        assert "state" in State.get_name().lower()
        assert "frontend" in FrontendEventExceptionState.get_name().lower()
        assert "update" in UpdateVarsInternalState.get_name().lower()
        assert "on_load" in OnLoadInternalState.get_name().lower()
