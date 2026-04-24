"""Tests for RegistrationContext."""

from textwrap import dedent

import pytest
from reflex_base.config import Config, get_config, reload_config
from reflex_base.registry import RegisteredEventHandler, RegistrationContext
from reflex_base.utils.exceptions import StateValueError

from reflex.testing import chdir


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


def test_clean_context_has_no_config(clean_registration_context: RegistrationContext):
    """A fresh RegistrationContext starts with config=None.

    Args:
        clean_registration_context: A fresh, empty registration context.
    """
    assert clean_registration_context.config is None


def _write_rxconfig(path, app_name: str) -> None:
    (path / "rxconfig.py").write_text(
        dedent(
            f"""
            import reflex as rx
            config = rx.Config(app_name="{app_name}")
            """
        )
    )


def test_get_config_caches_on_context(
    tmp_path, clean_registration_context: RegistrationContext
):
    """get_config loads rxconfig once and caches the result on the context.

    Args:
        tmp_path: Pytest tmp dir fixture.
        clean_registration_context: A fresh, empty registration context.
    """
    _write_rxconfig(tmp_path, "ctx_app")
    with chdir(tmp_path):
        assert clean_registration_context.config is None
        first = get_config()
        assert first is clean_registration_context.config
        assert first.app_name == "ctx_app"
        assert get_config() is first


def test_reload_config_forces_fresh_load(
    tmp_path, clean_registration_context: RegistrationContext
):
    """reload_config re-reads rxconfig.py and replaces the cached instance.

    Args:
        tmp_path: Pytest tmp dir fixture.
        clean_registration_context: A fresh, empty registration context.
    """
    _write_rxconfig(tmp_path, "before")
    with chdir(tmp_path):
        first = get_config()
        assert first.app_name == "before"

        _write_rxconfig(tmp_path, "after")
        second = reload_config()
        assert second is not first
        assert second.app_name == "after"
        assert clean_registration_context.config is second
        assert get_config() is second


def test_two_contexts_hold_independent_configs(tmp_path):
    """Different RegistrationContexts can cache different configs in one process.

    Args:
        tmp_path: Pytest tmp dir fixture.
    """
    app_a = tmp_path / "app_a"
    app_a.mkdir()
    _write_rxconfig(app_a, "app_a")

    app_b = tmp_path / "app_b"
    app_b.mkdir()
    _write_rxconfig(app_b, "app_b")

    with RegistrationContext() as ctx_a, chdir(app_a):
        config_a = get_config()

    with RegistrationContext() as ctx_b, chdir(app_b):
        config_b = get_config()

    assert config_a.app_name == "app_a"
    assert config_b.app_name == "app_b"
    assert config_a is not config_b
    assert ctx_a.config is config_a
    assert ctx_b.config is config_b


def test_get_config_outside_context_auto_attaches():
    """Calling get_config with no active context attaches one automatically."""
    import contextvars

    def _run() -> Config:
        with pytest.raises(LookupError):
            RegistrationContext.get()
        cfg = get_config()
        assert RegistrationContext.get().config is cfg
        return cfg

    # Run in a fresh Context so the ContextVar starts unset.
    config = contextvars.Context().run(_run)
    assert isinstance(config, Config)


def test_decorated_pages_isolated_between_contexts():
    """@page registrations in one context do not leak to another."""
    from reflex.page import page

    def a_page():
        return None

    def b_page():
        return None

    with RegistrationContext() as ctx_a:
        page(route="/a")(a_page)
        assert len(ctx_a.decorated_pages) == 1
        assert ctx_a.decorated_pages[0][0] is a_page

    with RegistrationContext() as ctx_b:
        page(route="/b")(b_page)
        assert len(ctx_b.decorated_pages) == 1
        assert ctx_b.decorated_pages[0][0] is b_page

    assert ctx_a.decorated_pages != ctx_b.decorated_pages


def test_custom_components_isolated_between_contexts():
    """@custom_component registrations in one context do not leak to another."""
    from reflex_base.components.component import custom_component

    import reflex as rx

    def _tag_component_fn(prop1: str, prop2: int) -> rx.Component:
        return rx.text(prop1)

    with RegistrationContext() as ctx_a:
        custom_component(_tag_component_fn)
        assert "TagComponentFn" in ctx_a.custom_components

    with RegistrationContext() as ctx_b:
        assert ctx_b.custom_components == {}


def test_memo_definitions_isolated_between_contexts():
    """@rx._x.memo registrations in one context do not leak to another."""
    import reflex as rx

    with RegistrationContext() as ctx_a:

        @rx._x.memo
        def greet(name: rx.Var[str]) -> rx.Var[str]:
            return name.to(str)

        assert "greet" in ctx_a.memo_definitions

    with RegistrationContext() as ctx_b:
        assert ctx_b.memo_definitions == {}


def test_bundled_libraries_isolated_between_contexts():
    """bundle_library appends to the current context only."""
    from reflex_base.components.dynamic import bundle_library

    with RegistrationContext() as ctx_a:
        initial_len = len(ctx_a.bundled_libraries)
        bundle_library("some-extra-lib")
        assert "some-extra-lib" in ctx_a.bundled_libraries
        assert len(ctx_a.bundled_libraries) == initial_len + 1

    with RegistrationContext() as ctx_b:
        assert "some-extra-lib" not in ctx_b.bundled_libraries
