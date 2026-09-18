"""Regression tests for the state.js frontend template."""

from pathlib import Path

STATE_JS_TEMPLATE = (
    Path(__file__).parents[3]
    / "packages/reflex-base/src/reflex_base/.templates/web/utils/state.js"
)


def test_state_js_does_not_register_deprecated_unload_listener() -> None:
    """The template must not register the deprecated `unload` event listener.

    Regression for https://github.com/reflex-dev/reflex/issues/6195: Chrome
    emits a deprecation warning when pages register `unload` handlers. The
    `pagehide` listener already covers the cases `unload` was being used for
    (tab close, navigation, bfcache), so the deprecated listener must not be
    re-introduced.
    """
    content = STATE_JS_TEMPLATE.read_text()

    assert 'addEventListener("unload"' not in content, (
        "state.js registers a deprecated `unload` listener; use `pagehide` instead."
    )
    assert 'removeEventListener("unload"' not in content, (
        "state.js still removes a `unload` listener that should no longer be registered."
    )


def test_state_js_still_handles_page_lifecycle_disconnect() -> None:
    """The template must still disconnect on page lifecycle events.

    Replacing the deprecated `unload` listener with `pagehide` is the
    recommended Web Page Lifecycle pattern; verify the replacement listeners
    remain wired so the socket is closed when the user navigates away.
    """
    content = STATE_JS_TEMPLATE.read_text()

    assert 'addEventListener("pagehide"' in content, (
        "state.js should register a `pagehide` listener to disconnect the socket."
    )
    assert 'addEventListener("beforeunload"' in content, (
        "state.js should keep its `beforeunload` listener as a disconnect fallback."
    )


def test_state_js_avoids_unpolyfilled_runtime_apis() -> None:
    """The template must not call `Array.prototype.at`.

    `Array.prototype.at` is ES2022 and, being a runtime method rather than
    syntax, is not downlevelled by the bundler's build target, so it breaks
    older browsers outright. Use length-guarded indexed access instead.
    """
    content = STATE_JS_TEMPLATE.read_text()

    assert ".at(" not in content, (
        "state.js calls Array.prototype.at; use `arr[arr.length - 1]` instead."
    )


def test_state_js_disconnects_on_fatal_mismatch() -> None:
    """A fatal frontend/backend mismatch must close the socket.

    No event can be exchanged after a mismatch, so a socket left open only
    pins a server connection to a dead tab.
    """
    content = STATE_JS_TEMPLATE.read_text()

    fatal_mismatch = content.split("const fatalMismatch = ", 1)[-1].split("\n  };", 1)[
        0
    ]
    assert "socket.current?.disconnect();" in fatal_mismatch, (
        "fatalMismatch should disconnect the socket after surfacing the error."
    )


def test_state_js_reconnect_helper_respects_fatal_mismatch() -> None:
    """Every reconnect path must funnel through the mismatch-aware helper.

    `socket.current.reconnect()` short-circuits on `backend_state_mismatch`, so
    disconnecting on a fatal mismatch cannot start a reconnect loop.
    """
    content = STATE_JS_TEMPLATE.read_text()

    reconnect_helper = content.split("socket.current.reconnect = () => {", 1)[-1].split(
        "\n  };", 1
    )[0]
    assert "if (backend_state_mismatch)" in reconnect_helper, (
        "the reconnect helper must not reconnect after a fatal mismatch."
    )
    # Counting every spelling, `socket.current?.connect()` included, so a
    # direct call cannot slip past the guard by writing itself differently.
    assert reconnect_helper.count(".connect(") == content.count(".connect(") == 1, (
        "socket reconnection should only happen inside the reconnect helper."
    )
