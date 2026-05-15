"""Tests for ``reflex.utils.telemetry_accounting``."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from reflex_base.plugins.sitemap import SitemapPlugin

import reflex as rx
from reflex.istate.storage import Cookie, LocalStorage, SessionStorage
from reflex.state import (
    BaseState,
    FrontendEventExceptionState,
    OnLoadInternalState,
    State,
    UpdateVarsInternalState,
)
from reflex.utils import telemetry_accounting
from reflex.utils.telemetry_context import TelemetryContext


@pytest.fixture(autouse=True)
def _reset_recorded_features():
    """Reset the process-level feature counter between tests."""
    telemetry_accounting._recorded_features.clear()
    yield
    telemetry_accounting._recorded_features.clear()


def _fake_config(**overrides):
    """Build a Mock config pre-populated with sane defaults for the collector.

    Args:
        **overrides: Config attribute overrides.

    Returns:
        A ``SimpleNamespace`` standing in for the resolved Reflex config.
    """
    defaults = {
        "plugins": [],
        "disable_plugins": [],
        "state_manager_mode": SimpleNamespace(value="memory"),
        "cors_allowed_origins": ("*",),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_app(**overrides):
    """Build a SimpleNamespace app with the attributes the collector touches.

    Args:
        **overrides: App attribute overrides.

    Returns:
        A ``SimpleNamespace`` standing in for a compiled ``App``.
    """
    defaults = {
        "_state": None,
        "_pages": {},
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


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
        return_value=_fake_config(
            plugins=[fake_plugin], disable_plugins=[SitemapPlugin]
        ),
    )

    app = _fake_app(
        _state=_TelAcctRoot,
        _pages={"/": rx.box(rx.text("hello"))},
    )
    ctx = TelemetryContext(trigger="cli_compile")

    payload = telemetry_accounting._collect_compile_event_payload(
        app,  # pyright: ignore[reportArgumentType]
        ctx,
    )

    assert payload["plugins_enabled"] == ["FakePlugin"]
    assert payload["plugins_disabled"] == ["SitemapPlugin"]
    assert payload["pages_count"] == 1
    assert payload["component_counts"]
    assert any(s["depth_from_root"] == 0 for s in payload["states"])
    assert payload["duration_ms"] >= 0
    assert payload["trigger"] == "cli_compile"
    assert payload["exception"] is None


def test_collect_compile_event_payload_with_exception(mocker: MockerFixture):
    """An attached exception lands in the payload as a sanitized type-only dict."""
    mocker.patch(
        "reflex.utils.telemetry_accounting.get_config",
        return_value=_fake_config(),
    )

    app = _fake_app()
    ctx = TelemetryContext()
    ctx.set_exception(RuntimeError("oops"))

    payload = telemetry_accounting._collect_compile_event_payload(
        app,  # pyright: ignore[reportArgumentType]
        ctx,
    )
    assert payload["exception"] == {"type": "RuntimeError"}
    assert payload["pages_count"] == 0
    assert payload["states"] == []


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


def test_increment_feature_writes_to_active_context():
    """``increment_feature`` bumps the active context's counter."""
    ctx = TelemetryContext()
    with ctx:
        telemetry_accounting.increment_feature("upload_count")
        telemetry_accounting.increment_feature("upload_count")
        telemetry_accounting.increment_feature("upload_count", by=3)
    assert ctx.features_used["upload_count"] == 5


def test_increment_feature_falls_back_to_persistent_when_no_context():
    """Outside a compile, ``increment_feature`` writes to the persistent dict."""
    telemetry_accounting.increment_feature("cookie_count")
    telemetry_accounting.increment_feature("cookie_count")
    assert telemetry_accounting._recorded_features["cookie_count"] == 2


def test_collect_features_used_emits_every_known_key(mocker: MockerFixture):
    """All names in ``_KNOWN_FEATURES`` ship at 0 even with no signals."""
    mocker.patch(
        "reflex.utils.telemetry_accounting.get_config",
        return_value=_fake_config(),
    )
    ctx = TelemetryContext()
    features = telemetry_accounting._collect_features_used(ctx, [])
    for name in telemetry_accounting._KNOWN_FEATURES:
        assert name in features, name


def test_collect_features_used_promotes_persistent_counters(mocker: MockerFixture):
    """Import-time ``increment_feature`` calls land in the snapshot."""
    mocker.patch(
        "reflex.utils.telemetry_accounting.get_config",
        return_value=_fake_config(),
    )
    telemetry_accounting.increment_feature("cookie_count", by=2)
    telemetry_accounting.increment_feature("shared_state_count")

    ctx = TelemetryContext()
    features = telemetry_accounting._collect_features_used(ctx, [])
    assert features["cookie_count"] == 2
    assert features["shared_state_count"] == 1


def test_collect_features_used_context_overrides_persistent(mocker: MockerFixture):
    """Context-side counters beat the persistent baseline for the same key."""
    mocker.patch(
        "reflex.utils.telemetry_accounting.get_config",
        return_value=_fake_config(),
    )
    telemetry_accounting._recorded_features["upload_count"] = 1
    ctx = TelemetryContext()
    with ctx:
        telemetry_accounting.increment_feature("upload_count", by=4)

    features = telemetry_accounting._collect_features_used(ctx, [])
    assert features["upload_count"] == 4


def test_collect_features_used_records_state_manager_mode(mocker: MockerFixture):
    """The configured state-manager mode lights up exactly one boolean key."""
    mocker.patch(
        "reflex.utils.telemetry_accounting.get_config",
        return_value=_fake_config(state_manager_mode=SimpleNamespace(value="redis")),
    )
    ctx = TelemetryContext()
    features = telemetry_accounting._collect_features_used(ctx, [])
    assert features["state_manager_redis"] == 1
    assert features["state_manager_disk"] == 0
    assert features["state_manager_memory"] == 0


def test_collect_features_used_records_cors_customized(mocker: MockerFixture):
    """A non-default ``cors_allowed_origins`` sets the cors counter to 1."""
    mocker.patch(
        "reflex.utils.telemetry_accounting.get_config",
        return_value=_fake_config(cors_allowed_origins=("https://example.com",)),
    )
    ctx = TelemetryContext()
    features = telemetry_accounting._collect_features_used(ctx, [])
    assert features["cors_customized"] == 1


def test_collect_features_used_default_cors_stays_zero(mocker: MockerFixture):
    """Default ``("*",)`` origins read as not customized."""
    mocker.patch(
        "reflex.utils.telemetry_accounting.get_config",
        return_value=_fake_config(),
    )
    ctx = TelemetryContext()
    features = telemetry_accounting._collect_features_used(ctx, [])
    assert features["cors_customized"] == 0


def test_collect_features_used_counts_background_handlers(mocker: MockerFixture):
    """The state walk counts ``@rx.event(background=True)`` handlers."""
    mocker.patch(
        "reflex.utils.telemetry_accounting.get_config",
        return_value=_fake_config(),
    )

    class _BgState(BaseState):
        @rx.event(background=True)
        async def slow(self):
            """Background handler used to assert detection."""

        @rx.event
        def fast(self):
            """Foreground handler that must not be miscounted."""

    ctx = TelemetryContext()
    features = telemetry_accounting._collect_features_used(ctx, [_BgState])
    assert features["background_event_handlers_count"] == 1


def test_storage_classes_increment_their_counters():
    """Constructing ``Cookie`` / ``LocalStorage`` / ``SessionStorage`` increments."""
    Cookie()
    Cookie()
    LocalStorage()
    SessionStorage()
    assert telemetry_accounting._recorded_features["cookie_count"] == 2
    assert telemetry_accounting._recorded_features["local_storage_count"] == 1
    assert telemetry_accounting._recorded_features["session_storage_count"] == 1


def test_shared_state_subclass_increments_counter():
    """Subclassing ``rx.SharedState`` bumps the shared-state counter."""
    before = telemetry_accounting._recorded_features.get("shared_state_count", 0)

    class _SharedA(rx.SharedState):
        x: int = 0

    class _SharedB(rx.SharedState):
        y: int = 0

    after = telemetry_accounting._recorded_features["shared_state_count"]
    assert after - before == 2
