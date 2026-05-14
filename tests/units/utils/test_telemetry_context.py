"""Tests for ``reflex.utils.telemetry_context``."""

from pytest_mock import MockerFixture

from reflex.utils.telemetry_context import TelemetryContext


def test_get_returns_none_when_no_context_set():
    """``get()`` returns ``None`` instead of raising ``LookupError``."""
    assert TelemetryContext.get() is None


def test_start_returns_none_when_telemetry_disabled(mocker: MockerFixture):
    """``start()`` short-circuits when the config has telemetry disabled."""
    mocker.patch(
        "reflex.utils.telemetry_context.get_config",
        return_value=mocker.Mock(telemetry_enabled=False),
    )
    assert TelemetryContext.start() is None


def test_start_returns_context_when_telemetry_enabled(mocker: MockerFixture):
    """``start()`` returns a fresh context when telemetry is enabled."""
    mocker.patch(
        "reflex.utils.telemetry_context.get_config",
        return_value=mocker.Mock(telemetry_enabled=True),
    )
    assert isinstance(TelemetryContext.start(), TelemetryContext)


def test_start_explicit_telemetry_enabled_overrides_config():
    """An explicit ``telemetry_enabled`` argument bypasses the config lookup."""
    assert TelemetryContext.start(telemetry_enabled=False) is None
    assert isinstance(TelemetryContext.start(telemetry_enabled=True), TelemetryContext)


def test_context_manager_attaches_and_detaches():
    """Entering the context binds it to ``get()``; exiting clears it."""
    ctx = TelemetryContext()
    with ctx:
        assert TelemetryContext.get() is ctx
    assert TelemetryContext.get() is None


def test_elapsed_ms_is_non_negative():
    """``elapsed_ms()`` returns a non-negative integer immediately after creation."""
    ctx = TelemetryContext()
    elapsed = ctx.elapsed_ms()
    assert isinstance(elapsed, int)
    assert elapsed >= 0


def test_set_exception_records_value_on_frozen_dataclass():
    """``set_exception`` mutates the otherwise-frozen ``exception`` field."""
    ctx = TelemetryContext()
    exc = ValueError("boom")
    ctx.set_exception(exc)
    assert ctx.exception is exc


def test_features_used_writable_via_get():
    """Writes through ``get()`` are visible on the original context instance."""
    ctx = TelemetryContext()
    with ctx:
        active = TelemetryContext.get()
        assert active is ctx
        assert active is not None
        active.features_used["foo"] = True
    assert ctx.features_used == {"foo": True}


def test_trigger_stored_on_context():
    """``start(trigger=...)`` round-trips the trigger onto the context."""
    ctx = TelemetryContext.start(telemetry_enabled=True, trigger="backend_startup")
    assert ctx is not None
    assert ctx.trigger == "backend_startup"


def test_distinct_contexts_use_identity_equality():
    """Two ``TelemetryContext`` instances must not compare equal or share a hash.

    ``BaseContext`` uses a class-level dict keyed by ``self`` to track attached
    contexts, so identity-based equality is required for nested use to work.
    """
    a = TelemetryContext()
    b = TelemetryContext()
    assert a != b
    assert hash(a) != hash(b)
    assert a == a


def test_nested_contexts_can_be_entered():
    """Nested ``with`` blocks attach and detach without colliding."""
    outer = TelemetryContext()
    inner = TelemetryContext()
    with outer:
        assert TelemetryContext.get() is outer
        with inner:
            assert TelemetryContext.get() is inner
        assert TelemetryContext.get() is outer
    assert TelemetryContext.get() is None


def test_hot_reload_trigger_accepted():
    """The ``hot_reload`` value is a valid ``CompileTrigger`` and round-trips."""
    ctx = TelemetryContext.start(telemetry_enabled=True, trigger="hot_reload")
    assert ctx is not None
    assert ctx.trigger == "hot_reload"
