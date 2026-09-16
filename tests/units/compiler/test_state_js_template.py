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


@pytest.mark.skipif(shutil.which("node") is None, reason="node missing")
def test_merge_slot_props_handles_conditional_event_handlers() -> None:
    """Falsy conditional handlers preserve the callable handler on either side."""
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
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
