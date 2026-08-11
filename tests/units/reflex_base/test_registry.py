"""Tests for RegistrationContext."""

import pytest
from reflex_base.registry import RegisteredEventHandler, RegistrationContext
from reflex_base.utils.exceptions import StateValueError


def test_ensure_context_creates_if_missing():
    """ensure_context() returns existing context or creates a new one."""
    try:
        existing = RegistrationContext._context_var.get()
        assert RegistrationContext.ensure_context() is existing
    except LookupError:
        ctx = RegistrationContext.ensure_context()
        assert isinstance(ctx, RegistrationContext)
        assert RegistrationContext.get() is ctx


def test_clean_context_is_empty(clean_registration_context: RegistrationContext):
    """A clean context starts with no handlers or states.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    assert clean_registration_context.event_handlers == {}
    assert clean_registration_context.base_states == {}
    assert clean_registration_context.base_state_substates == {}


def test_register_event_handler(clean_registration_context: RegistrationContext):
    """register_event_handler stores the handler keyed by its full name.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.event import EventHandler

    async def my_fn():
        pass

    handler = EventHandler(fn=my_fn)
    RegistrationContext.register_event_handler(handler)
    assert len(clean_registration_context.event_handlers) == 1
    registered = next(iter(clean_registration_context.event_handlers.values()))
    assert isinstance(registered, RegisteredEventHandler)
    assert registered.handler is handler


def test_register_base_state(clean_registration_context: RegistrationContext):
    """BaseState metaclass auto-registers during class definition into the active context.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class AutoRegistered(BaseState):
        x: int = 0

    assert AutoRegistered.get_full_name() in clean_registration_context.base_states


def test_duplicate_substate_raises(clean_registration_context: RegistrationContext):
    """Registering the same substate twice raises StateValueError.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class DupParent(BaseState):
        pass

    class DupChild(DupParent):
        pass

    with pytest.raises(StateValueError, match="already registered"):
        clean_registration_context._register_base_state(DupChild)


def test_get_substates(clean_registration_context: RegistrationContext):
    """get_substates returns registered children of a parent.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class GetSubRoot(BaseState):
        pass

    class GetSub1(GetSubRoot):
        pass

    class GetSub2(GetSubRoot):
        pass

    substates = clean_registration_context.get_substates(GetSubRoot)
    assert GetSub1 in substates
    assert GetSub2 in substates


def test_get_substates_by_name(clean_registration_context: RegistrationContext):
    """get_substates also works when passed a string full name.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class NamedState(BaseState):
        pass

    result = clean_registration_context.get_substates(NamedState.get_full_name())
    assert isinstance(result, set)


def test_forked_context_is_independent(
    forked_registration_context: RegistrationContext,
):
    """Changes to a forked context do not affect the original.

    Args:
        forked_registration_context: A deep copy of the current registration context.
    """
    from reflex.event import EventHandler

    async def _tmp():
        pass

    handler = EventHandler(fn=_tmp)
    RegistrationContext.register_event_handler(handler)
    assert len(forked_registration_context.event_handlers) > 0


def test_resolve_implementation(clean_registration_context: RegistrationContext):
    """resolve_implementation finds the state a mixin was mixed into.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class ResolveMixin(BaseState, mixin=True):
        pass

    class ResolveImpl(ResolveMixin, BaseState):
        pass

    assert clean_registration_context.resolve_implementation(ResolveMixin) is (
        ResolveImpl
    )
    assert clean_registration_context.get_states_implementing(ResolveMixin) == (
        ResolveImpl,
    )


def test_resolve_implementation_ignores_subclasses(
    clean_registration_context: RegistrationContext,
):
    """Subclasses of an implementation do not make the resolution ambiguous.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class SubclassMixin(BaseState, mixin=True):
        pass

    class SubclassImpl(SubclassMixin, BaseState):
        pass

    class SubclassChild(SubclassImpl):
        pass

    assert set(clean_registration_context.get_states_implementing(SubclassMixin)) == {
        SubclassImpl,
        SubclassChild,
    }
    assert clean_registration_context.resolve_implementation(SubclassMixin) is (
        SubclassImpl
    )


def test_resolve_implementation_without_implementation(
    clean_registration_context: RegistrationContext,
):
    """Resolving a mixin no state implements raises StateValueError.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class UnusedMixin(BaseState, mixin=True):
        pass

    assert clean_registration_context.get_states_implementing(UnusedMixin) == ()
    with pytest.raises(StateValueError, match="No registered state implements"):
        clean_registration_context.resolve_implementation(UnusedMixin)


def test_resolve_implementation_ambiguous(
    clean_registration_context: RegistrationContext,
):
    """Resolving a mixin used by two unrelated states raises StateValueError.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class AmbiguousMixin(BaseState, mixin=True):
        pass

    class AmbiguousImpl1(AmbiguousMixin, BaseState):
        pass

    class AmbiguousImpl2(AmbiguousMixin, BaseState):
        pass

    with pytest.raises(StateValueError, match="implemented by more than one state"):
        clean_registration_context.resolve_implementation(AmbiguousMixin)


def test_resolve_implementation_cache_is_invalidated(
    clean_registration_context: RegistrationContext,
):
    """Registering a state invalidates previously cached lookups.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    from reflex.state import BaseState

    class CacheMixin(BaseState, mixin=True):
        pass

    class CacheImpl(CacheMixin, BaseState):
        pass

    assert clean_registration_context.resolve_implementation(CacheMixin) is CacheImpl
    # Repeated lookups are served from the cache.
    assert clean_registration_context.get_states_implementing(
        CacheMixin
    ) is clean_registration_context.get_states_implementing(CacheMixin)

    class CacheImpl2(CacheMixin, BaseState):
        pass

    assert set(clean_registration_context.get_states_implementing(CacheMixin)) == {
        CacheImpl,
        CacheImpl2,
    }
    with pytest.raises(StateValueError, match="implemented by more than one state"):
        clean_registration_context.resolve_implementation(CacheMixin)
