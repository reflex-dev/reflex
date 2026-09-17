"""Integration test for the ``compile`` telemetry event.

Drives a real ``AppHarness`` compile against an app that exercises every
field surfaced in ``features_used``, captures ``telemetry.send`` to a JSONL
file inside the test app, then asserts the emitted counts.

The compile pipeline runs end-to-end here, so a regression in
``record_compile`` (such as the inherited-storage double-count fix) shows
up at the integration boundary rather than only in collector unit tests.
"""

import functools
import json
from collections.abc import Generator
from pathlib import Path

import pytest

from reflex.testing import AppHarness, chdir


def TelemetryCompileApp(events_log_path: str = ""):
    """Reflex app exercising the features collected on the ``compile`` event.

    Includes a parent + child state hierarchy with Cookie / LocalStorage /
    SessionStorage to guard against the inherited-field double-count
    regression, a background event handler, a SharedState user subclass,
    and a dynamic route.

    Args:
        events_log_path: Filesystem path to a JSONL file. Every
            ``telemetry.send`` invocation during compile is appended as
            one JSON object per line so the test can read it back.
    """
    import json
    import os
    from pathlib import Path

    import reflex as rx
    from reflex.istate.storage import Cookie, LocalStorage, SessionStorage
    from reflex.utils import telemetry

    # AppHarness force-disables telemetry. Re-enable it on the live config
    # singleton so the real _compile() path runs record_compile, and
    # redirect telemetry.send to disk so the test can read the payload.
    os.environ["REFLEX_TELEMETRY_ENABLED"] = "true"
    rx.config.get_config().telemetry_enabled = True

    sink = Path(events_log_path)
    sink.parent.mkdir(parents=True, exist_ok=True)

    def _capture(event, properties=None, **_kwargs):
        with sink.open("a") as fh:
            fh.write(
                json.dumps({"event": event, "properties": properties or {}}) + "\n"
            )
        return True

    telemetry.send = _capture

    class StorageRoot(rx.State):
        token: str = Cookie()
        local_pref: str = LocalStorage()

        @rx.event(background=True)
        async def heavy(self):
            """Background handler used to assert detection."""

    class StorageChild(StorageRoot):
        # ``token`` and ``local_pref`` are inherited here and must not be
        # re-counted on the child state.
        session: str = SessionStorage()

    class SharedThing(rx.SharedState):
        value: int = 0

    def index():
        return rx.box(rx.text("home"))

    def item_page():
        return rx.box(rx.text("item"))

    app = rx.App()
    app.add_page(index)
    app.add_page(item_page, route="/items/[id]")


@pytest.fixture
def telemetry_events_log(tmp_path) -> Path:
    """Path to the JSONL telemetry sink the harness app writes into.

    Args:
        tmp_path: pytest tmp_path fixture.

    Returns:
        Path the harness app writes one JSON event per line to.
    """
    return tmp_path / "telemetry_events.jsonl"


@pytest.fixture
def telemetry_compile_harness(
    tmp_path_factory, telemetry_events_log: Path
) -> Generator[AppHarness, None, None]:
    """Run AppHarness for the telemetry-capture app.

    Only ``_initialize_app()`` is invoked — that path imports the app
    module and calls ``App.__call__()`` which triggers ``_compile()``, so
    the captured JSONL contains the compile event by the time the test
    body runs. The dev backend / frontend lifecycle is skipped because
    this test only cares about compile-time telemetry.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture.
        telemetry_events_log: Path the harness app writes events to.

    Yields:
        The configured ``AppHarness`` instance after initialization.
    """
    root = tmp_path_factory.mktemp("telemetry_compile_app")
    with AppHarness.create(
        root=root,
        app_source=functools.partial(
            TelemetryCompileApp,
            events_log_path=str(telemetry_events_log),
        ),
        app_name="telemetry_compile_app",
    ) as harness:
        yield harness


def _read_compile_events(events_log: Path) -> list[dict]:
    """Return every ``compile`` event written to the sink.

    Args:
        events_log: JSONL file the harness app appended to.

    Returns:
        List of ``properties`` dicts for events named ``compile``.
    """
    if not events_log.exists():
        return []
    out: list[dict] = []
    for line in events_log.read_text().splitlines():
        rec = json.loads(line)
        if rec.get("event") == "compile":
            out.append(rec["properties"])
    return out


def test_compile_event_features_used_initial_and_hot_reload(
    telemetry_compile_harness: AppHarness,
    telemetry_events_log: Path,
):
    """Compile event payload is well-formed and stable across hot reload.

    Two assertions in sequence, exercising the live ``_compile()`` path:

    1. The initial compile (driven by AppHarness during fixture setup)
       emits a ``compile`` event with exact ``features_used`` counts.
       Guards the inherited client-storage double-count regression:
       ``token`` and ``local_pref`` live on ``StorageRoot`` and are
       inherited by ``StorageChild`` — each must be counted exactly once.

    2. A second ``_compile`` call under ``trigger="hot_reload"`` re-derives
       the snapshot from scratch and must produce the same counts. A
       regression that cached or accumulated counters across compiles
       shows up here as drift between the two events.
    """
    payloads = _read_compile_events(telemetry_events_log)
    assert payloads, "no compile event was captured by the AppHarness run"
    initial = payloads[-1]
    initial_features = initial["features_used"]
    assert initial_features["cookie_count"] == 1, (
        "inherited cookie field was counted on parent and child"
    )
    assert initial_features["local_storage_count"] == 1, (
        "inherited LocalStorage field was counted on parent and child"
    )
    assert initial_features["session_storage_count"] == 1
    assert initial_features["background_event_handlers_count"] == 1
    assert initial_features["shared_state_count"] == 1
    assert initial_features["dynamic_routes_count"] == 1
    assert initial["trigger"] in {"initial", "backend_startup", None}
    assert initial["exception"] is None

    app = telemetry_compile_harness.app_instance
    assert app is not None, "AppHarness did not populate app_instance"

    # The real reflex CLI invokes hot reloads from inside the app directory.
    # AppHarness chdir's into app_path during _initialize_app() but reverts
    # on exit, so we restore it here to match the live hot-reload environment.
    pre_event_count = len(payloads)
    with chdir(telemetry_compile_harness.app_path):
        app._compile(trigger="hot_reload")

    payloads = _read_compile_events(telemetry_events_log)
    assert len(payloads) == pre_event_count + 1, (
        "hot reload did not emit exactly one additional compile event"
    )
    reload = payloads[-1]
    assert reload["trigger"] == "hot_reload"
    assert reload["exception"] is None
    assert initial_features == reload["features_used"], (
        "features_used drifted between initial compile and hot reload"
    )
    assert initial["component_counts"] == reload["component_counts"]
    assert initial["pages_count"] == reload["pages_count"]
    assert [s["depth_from_root"] for s in initial["states"]] == [
        s["depth_from_root"] for s in reload["states"]
    ]
