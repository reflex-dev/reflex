"""Tests for ``reflex.utils.telemetry_accounting``."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from reflex_base.plugins.sitemap import SitemapPlugin

import reflex as rx
from reflex.state import (
    BaseState,
    FrontendEventExceptionState,
    OnLoadInternalState,
    State,
    UpdateVarsInternalState,
)
from reflex.utils import telemetry_accounting
from reflex.utils.telemetry_context import TelemetryContext


class _TelAcctRoot(BaseState):
    """Root state for accounting tests."""

    a: int = 0
    b: str = ""
    _backend_one: int = 0

    @rx.event
    def set_a(self, value: int):
        """Set a.

        Args:
            value: New value.
        """
        self.a = value

    @rx.var
    def doubled(self) -> int:
        """Doubled value of a.

        Returns:
            ``a * 2``.
        """
        return self.a * 2


class _TelAcctChild(_TelAcctRoot):
    """Child state for accounting tests."""

    c: int = 0


class _TelAcctGrandchild(_TelAcctChild):
    """Grandchild state for accounting tests."""

    d: int = 0


def test_sanitize_exception_strips_message_and_path():
    """Sanitization keeps only the class name, dropping any sensitive message."""
    exc = ValueError("/secret/path: bad value 'topsecret'")
    assert telemetry_accounting._sanitize_exception(exc) == {"type": "ValueError"}


def test_count_components_walks_nested_tree():
    """Component counts include every node in nested trees, keyed by class name."""
    tree = rx.box(rx.box(rx.box()))
    counts = telemetry_accounting._count_components([tree])
    assert counts[type(tree).__name__] == 3


def test_collect_state_stats_root_depth_zero():
    """A root state has depth 0 and reports the counts straight off the class."""
    stats = telemetry_accounting._collect_state_stats(_TelAcctRoot)
    assert stats == {
        "event_handlers_count": len(_TelAcctRoot.event_handlers),
        "vars_count": len(_TelAcctRoot.vars),
        "backend_vars_count": len(_TelAcctRoot.backend_vars),
        "computed_vars_count": len(_TelAcctRoot.computed_vars),
        "depth_from_root": 0,
    }


def test_collect_state_stats_depth_hierarchy():
    """Depth increases with each parent-to-child step."""
    assert (
        telemetry_accounting._collect_state_stats(_TelAcctChild)["depth_from_root"] == 1
    )
    assert (
        telemetry_accounting._collect_state_stats(_TelAcctGrandchild)["depth_from_root"]
        == 2
    )


def test_walk_states_yields_root_and_descendants():
    """The walker reaches every descendant transitively."""
    walked = set(telemetry_accounting._walk_states(_TelAcctRoot))
    assert {_TelAcctRoot, _TelAcctChild, _TelAcctGrandchild} <= walked


def test_collect_compile_event_payload_shape(mocker: MockerFixture):
    """The payload exposes every documented field with the expected types."""
    fake_plugin = MagicMock()
    fake_plugin.__class__.__name__ = "FakePlugin"
    mocker.patch(
        "reflex.utils.telemetry_accounting.get_config",
        return_value=mocker.Mock(
            plugins=[fake_plugin], disable_plugins=[SitemapPlugin]
        ),
    )

    app = SimpleNamespace(
        _state=_TelAcctRoot,
        _pages={"/": rx.box(rx.text("hello"))},
    )
    ctx = TelemetryContext(trigger="cli_compile")
    ctx.features_used["radix"] = True

    payload = telemetry_accounting._collect_compile_event_payload(
        app,  # pyright: ignore[reportArgumentType]
        ctx,
    )

    assert payload["plugins_enabled"] == ["FakePlugin"]
    assert payload["plugins_disabled"] == ["SitemapPlugin"]
    assert payload["pages_count"] == 1
    assert payload["component_counts"]
    assert any(s["depth_from_root"] == 0 for s in payload["states"])
    assert payload["features_used"] == {"radix": True}
    assert payload["duration_ms"] >= 0
    assert payload["trigger"] == "cli_compile"
    assert payload["exception"] is None


def test_collect_compile_event_payload_with_exception(mocker: MockerFixture):
    """An attached exception lands in the payload as a sanitized type-only dict."""
    mocker.patch(
        "reflex.utils.telemetry_accounting.get_config",
        return_value=mocker.Mock(plugins=[], disable_plugins=[]),
    )

    app = SimpleNamespace(_state=None, _pages={})
    ctx = TelemetryContext()
    ctx.set_exception(RuntimeError("oops"))

    payload = telemetry_accounting._collect_compile_event_payload(
        app,  # pyright: ignore[reportArgumentType]
        ctx,
    )
    assert payload["exception"] == {"type": "RuntimeError"}
    assert payload["pages_count"] == 0
    assert payload["states"] == []


def test_collect_compile_event_payload_snapshots_features_used(mocker: MockerFixture):
    """features_used in the payload is a snapshot, immune to later mutation."""
    mocker.patch(
        "reflex.utils.telemetry_accounting.get_config",
        return_value=mocker.Mock(plugins=[], disable_plugins=[]),
    )
    app = SimpleNamespace(_state=None, _pages={})
    ctx = TelemetryContext()
    ctx.features_used["x"] = 1

    payload = telemetry_accounting._collect_compile_event_payload(
        app,  # pyright: ignore[reportArgumentType]
        ctx,
    )
    ctx.features_used["x"] = 999
    ctx.features_used["y"] = 2
    assert payload["features_used"] == {"x": 1}


def test_walk_states_skips_framework_internal_substates():
    """Framework-internal substates are excluded; user states still appear."""

    class _UserWalkState(rx.State):
        x: int = 0

    walked = list(telemetry_accounting._walk_states(State))
    walked_names = {cls.__name__ for cls in walked}

    assert UpdateVarsInternalState not in walked
    assert OnLoadInternalState not in walked
    assert FrontendEventExceptionState not in walked
    assert "SharedStateBaseInternal" not in walked_names
    assert State not in walked
    assert _UserWalkState in walked


def test_memo_wrapper_class_records_wrapped_component_type():
    """The dynamic memo subclass exposes the user-authored component class."""
    import importlib

    from reflex_components_radix.themes.components.button import Button

    memo_module = importlib.import_module("reflex.experimental.memo")

    wrapper_cls = memo_module._get_experimental_memo_component_class(
        "Button_button_deadbeefcafebabe",
        Button,
    )
    assert wrapper_cls._wrapped_component_type is Button


def test_count_components_buckets_memo_wrapper_by_wrapped_type():
    """Memo wrappers count under their wrapped component class name."""
    from reflex_components_radix.themes.components.button import Button

    class _StubMemoWrapper:
        _wrapped_component_type = Button
        children = ()

    counts = telemetry_accounting._count_components(
        [_StubMemoWrapper()],  # pyright: ignore[reportArgumentType]
    )

    assert counts == {"Button": 1}
