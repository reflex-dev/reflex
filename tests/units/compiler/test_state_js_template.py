"""Regression tests for the state.js frontend template."""

import shutil
import subprocess
from pathlib import Path

import pytest

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


@pytest.mark.skipif(shutil.which("node") is None, reason="node missing")
def test_merge_slot_props_handles_conditional_event_handlers() -> None:
    """Falsy handlers, direct object merges and DOM-ref routing behave per contract."""
    content = STATE_JS_TEMPLATE.read_text()
    helpers = content[
        content.index("export const mergeRefs =") : content.index(
            "export const getRefValue ="
        )
    ]
    subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            helpers
            + """
import assert from 'node:assert/strict';
for (const absent of [null, undefined, false, 0, '']) {
  let calls = 0;
  const handler = () => calls++;
  for (const [own, injected] of [[absent, handler], [handler, absent]]) {
    const merged = mergeSlotProps({onClick: injected}, {onClick: own});
    assert.equal(merged.onClick, handler);
    merged.onClick();
  }
  assert.equal(calls, 2);
}
const calls = [];
const own = {onClick: () => calls.push('own')};
const injected = {onClick: () => calls.push('injected')};
const first = mergeSlotProps(injected, own);
assert.equal(first.onClick, mergeSlotProps(injected, own).onClick);
first.onClick();
assert.deepEqual(calls, ['own', 'injected']);
// Object props merge directly through mergician — the own side is a fresh
// literal every render, so there is no identity to cache under, and neither
// input object may be mutated by the merge.
const mergician = (injected, own) => ({...injected, ...own});
const injectedStyle = {color: 'red', margin: 4};
const ownStyle = {color: 'blue'};
const mergedStyle = mergeSlotProps({style: injectedStyle}, {style: ownStyle}).style;
assert.deepEqual(mergedStyle, {color: 'blue', margin: 4});
assert.notEqual(mergedStyle, ownStyle);
assert.notEqual(mergedStyle, injectedStyle);
assert.deepEqual(ownStyle, {color: 'blue'});
assert.deepEqual(injectedStyle, {color: 'red', margin: 4});
// A root whose DOM ref rides a dedicated prop (DebounceInput's inputRef)
// never receives `ref`; the injected ref is routed and composed there.
const ownRef = {current: null};
const seen = [];
const routed = mergeSlotProps(
  {ref: (n) => seen.push(n), name: 'n'},
  {inputRef: ownRef, id: 'x'},
  'inputRef',
);
assert.ok(!('ref' in routed));
assert.equal(routed.name, 'n');
assert.equal(routed.id, 'x');
const cleanup = routed.inputRef({tag: 'input'});
assert.equal(ownRef.current.tag, 'input');
assert.equal(seen[0].tag, 'input');
cleanup();
assert.equal(ownRef.current, null);
assert.equal(seen[1], null);
assert.equal(
  mergeSlotProps({id: 's'}, {inputRef: ownRef}, 'inputRef').inputRef, ownRef);
assert.ok(!('ref' in mergeSlotProps({ref: null}, {inputRef: ownRef}, 'inputRef')));
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
