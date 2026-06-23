"""Tests for ``reflex.utils.telemetry_accounting``."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from reflex_base.config import Config
from reflex_base.plugins.sitemap import SitemapPlugin
from reflex_base.telemetry_context import TelemetryContext

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


def _fake_config(**overrides) -> Config:
    """Build a stand-in config pre-populated with defaults the collector reads.

    Args:
        **overrides: Config attribute overrides.

    Returns:
        A ``SimpleNamespace`` standing in for the resolved Reflex config,
        cast to ``Config`` so callers stay in the typed lane.
    """
    defaults = {
        "plugins": [],
        "disable_plugins": [],
        "state_manager_mode": SimpleNamespace(value="memory"),
        "cors_allowed_origins": ("*",),
    }
    defaults.update(overrides)
    return cast(Config, SimpleNamespace(**defaults))


def _fake_app(**overrides):
    """Build a SimpleNamespace app with the attributes the collector touches.

    Args:
        **overrides: App attribute overrides. ``_lifespan_tasks`` is surfaced
            through a ``get_lifespan_tasks()`` method to match the real API.

    Returns:
        A ``SimpleNamespace`` standing in for a compiled ``App``.
    """
    defaults = {
        "_state": None,
        "_pages": {},
        "_unevaluated_pages": {},
    }
    lifespan_tasks = overrides.pop("_lifespan_tasks", {})
    defaults.update(overrides)
    return SimpleNamespace(
        get_lifespan_tasks=lambda: tuple(lifespan_tasks),
        **defaults,
    )


class TelAcctRoot(BaseState):
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


class TelAcctChild(TelAcctRoot):
    """Child state for accounting tests."""

    c: int = 0


class TelAcctGrandchild(TelAcctChild):
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
    stats = telemetry_accounting._collect_state_stats(TelAcctRoot)
    assert stats == {
        "event_handlers_count": len(TelAcctRoot.event_handlers),
        "vars_count": len(TelAcctRoot.vars),
        "backend_vars_count": len(TelAcctRoot.backend_vars),
        "computed_vars_count": len(TelAcctRoot.computed_vars),
        "depth_from_root": 0,
    }


def test_collect_state_stats_depth_hierarchy():
    """Depth increases with each parent-to-child step."""
    assert (
        telemetry_accounting._collect_state_stats(TelAcctChild)["depth_from_root"] == 1
    )
    assert (
        telemetry_accounting._collect_state_stats(TelAcctGrandchild)["depth_from_root"]
        == 2
    )


def test_walk_states_yields_root_and_descendants():
    """The walker reaches every descendant transitively."""
    walked = set(telemetry_accounting._walk_states(TelAcctRoot))
    assert {TelAcctRoot, TelAcctChild, TelAcctGrandchild} <= walked


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
        _state=TelAcctRoot,
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

    class UserWalkState(rx.State):
        x: int = 0

    walked = list(telemetry_accounting._walk_states(State))
    walked_names = {cls.__name__ for cls in walked}

    assert UpdateVarsInternalState not in walked
    assert OnLoadInternalState not in walked
    assert FrontendEventExceptionState not in walked
    assert "SharedStateBaseInternal" not in walked_names
    assert State not in walked
    assert UserWalkState in walked


def test_memo_wrapper_class_records_wrapped_component_type():
    """The dynamic memo subclass exposes the user-authored component class."""
    from reflex_base.components.memo import _get_memo_component_class
    from reflex_components_radix.themes.components.button import Button

    wrapper_cls = _get_memo_component_class(
        "Button_button_deadbeefcafebabe",
        Button,
    )
    assert wrapper_cls._wrapped_component_type is Button


def test_count_components_buckets_memo_wrapper_by_wrapped_type():
    """Memo wrappers count under their wrapped component class name."""
    from reflex_components_radix.themes.components.button import Button

    class StubMemoWrapper:
        _wrapped_component_type = Button
        children = ()

    counts = telemetry_accounting._count_components(
        [StubMemoWrapper()],  # pyright: ignore[reportArgumentType]
    )

    assert counts == {"Button": 1}


def test_collect_features_used_emits_every_known_key():
    """All names in ``_KNOWN_FEATURES`` ship in the snapshot, defaulted to 0."""
    features = telemetry_accounting._collect_features_used(
        _fake_app(),  # pyright: ignore[reportArgumentType]
        _fake_config(),
        [],
    )
    for name in telemetry_accounting._KNOWN_FEATURES:
        assert name in features, name


def test_collect_features_used_walks_state_fields_for_storage():
    """Storage counts come from a walk over user state fields."""

    class StorageState(BaseState):
        c1: str = Cookie()
        c2: str = Cookie()
        ls: str = LocalStorage()
        ss: str = SessionStorage()
        plain: int = 0

    features = telemetry_accounting._collect_features_used(
        _fake_app(),  # pyright: ignore[reportArgumentType]
        _fake_config(),
        [StorageState],
    )
    assert features["cookie_count"] == 2
    assert features["local_storage_count"] == 1
    assert features["session_storage_count"] == 1
    assert "plain" not in features


def test_collect_features_used_storage_not_double_counted_through_inheritance():
    """Inherited storage fields are not re-counted on each descendant."""

    class StorageParent(BaseState):
        c: str = Cookie()
        ls: str = LocalStorage()
        ss: str = SessionStorage()

    class StorageChild(StorageParent):
        pass

    class StorageGrandchild(StorageChild):
        extra: str = Cookie()

    features = telemetry_accounting._collect_features_used(
        _fake_app(),  # pyright: ignore[reportArgumentType]
        _fake_config(),
        [StorageParent, StorageChild, StorageGrandchild],
    )
    assert features["cookie_count"] == 2
    assert features["local_storage_count"] == 1
    assert features["session_storage_count"] == 1


def test_collect_features_used_upload_reads_class_flag(mocker: MockerFixture):
    """``upload_count`` mirrors ``Upload.is_used`` (no per-node tree walk)."""
    from reflex_components_core.core.upload import Upload

    mocker.patch.object(Upload, "is_used", True)
    used = telemetry_accounting._collect_features_used(
        _fake_app(),  # pyright: ignore[reportArgumentType]
        _fake_config(),
        [],
    )
    assert used["upload_count"] == 1

    mocker.patch.object(Upload, "is_used", False)
    unused = telemetry_accounting._collect_features_used(
        _fake_app(),  # pyright: ignore[reportArgumentType]
        _fake_config(),
        [],
    )
    assert unused["upload_count"] == 0


def test_collect_features_used_counts_shared_state_subclasses():
    """The walk counts user states that subclass ``rx.SharedState``."""

    class SharedOne(rx.SharedState):
        x: int = 0

    class SharedTwo(rx.SharedState):
        y: int = 0

    features = telemetry_accounting._collect_features_used(
        _fake_app(),  # pyright: ignore[reportArgumentType]
        _fake_config(),
        [SharedOne, SharedTwo],
    )
    assert features["shared_state_count"] == 2


def test_collect_features_used_counts_dynamic_routes():
    """Routes with ``[arg]`` parts count; static routes do not."""
    app = _fake_app(
        _unevaluated_pages={
            "/": object(),
            "/about": object(),
            "/items/[id]": object(),
            "/blog/[[slug]]": object(),
        },
    )
    features = telemetry_accounting._collect_features_used(
        app,  # pyright: ignore[reportArgumentType]
        _fake_config(),
        [],
    )
    assert features["dynamic_routes_count"] == 2


def test_collect_features_used_counts_user_lifespan_tasks():
    """User-module lifespan tasks count; ``reflex.*`` tasks are excluded."""

    def user_task():
        return None

    def reflex_internal_task():
        return None

    reflex_internal_task.__module__ = "reflex.app"

    app = _fake_app(_lifespan_tasks={user_task: None, reflex_internal_task: None})
    features = telemetry_accounting._collect_features_used(
        app,  # pyright: ignore[reportArgumentType]
        _fake_config(),
        [],
    )
    assert features["lifespan_tasks_count"] == 1


def test_collect_features_used_counts_registered_db_models(mocker: MockerFixture):
    """A non-empty ``ModelRegistry`` reads into ``db_model_count``."""
    mocker.patch.object(telemetry_accounting, "_HAS_SQLALCHEMY", True)
    # Replace ModelRegistry wholesale so the test works whether sqlalchemy is
    # installed (real ModelRegistry) or not (the _ClassThatErrorsOnInit stub).
    fake_registry = SimpleNamespace(get_models=lambda: {object(), object()})
    mocker.patch.object(telemetry_accounting, "ModelRegistry", fake_registry)

    features = telemetry_accounting._collect_features_used(
        _fake_app(),  # pyright: ignore[reportArgumentType]
        _fake_config(),
        [],
    )
    assert features["db_model_count"] == 2


def test_collect_features_used_records_state_manager_mode():
    """The configured state-manager mode lights up exactly one boolean key."""
    features = telemetry_accounting._collect_features_used(
        _fake_app(),  # pyright: ignore[reportArgumentType]
        _fake_config(state_manager_mode=SimpleNamespace(value="redis")),
        [],
    )
    assert features["state_manager_redis"] == 1
    assert features["state_manager_disk"] == 0
    assert features["state_manager_memory"] == 0


def test_collect_features_used_records_cors_customized():
    """A non-default ``cors_allowed_origins`` sets the cors counter to 1."""
    features = telemetry_accounting._collect_features_used(
        _fake_app(),  # pyright: ignore[reportArgumentType]
        _fake_config(cors_allowed_origins=("https://example.com",)),
        [],
    )
    assert features["cors_customized"] == 1


def test_collect_features_used_default_cors_stays_zero():
    """Default ``("*",)`` origins read as not customized."""
    features = telemetry_accounting._collect_features_used(
        _fake_app(),  # pyright: ignore[reportArgumentType]
        _fake_config(),
        [],
    )
    assert features["cors_customized"] == 0


def test_collect_features_used_counts_background_handlers():
    """The state walk counts ``@rx.event(background=True)`` handlers."""

    class BgState(BaseState):
        @rx.event(background=True)
        async def slow(self):
            """Background handler used to assert detection."""

        @rx.event
        def fast(self):
            """Foreground handler that must not be miscounted."""

    features = telemetry_accounting._collect_features_used(
        _fake_app(),  # pyright: ignore[reportArgumentType]
        _fake_config(),
        [BgState],
    )
    assert features["background_event_handlers_count"] == 1
