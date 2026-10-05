"""Regression tests for the state.js frontend template."""

import shutil
import subprocess
from pathlib import Path

import pytest

STATE_JS_TEMPLATE = (
    Path(__file__).parents[3]
    / "packages/reflex-base/src/reflex_base/.templates/web/utils/state.js"
)


def test_socket_startup_lifecycle() -> None:
    """Execute the frontend startup and reconnect tests against the real template."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the frontend runtime tests")
    result = subprocess.run(
        [
            node,
            "--experimental-vm-modules",
            str(Path(__file__).with_name("state_js.test.mjs")),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


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
def test_get_ref_value_preserves_empty_and_unset_controls() -> None:
    """Form fields retain falsy values and serialize unset refs as null."""
    content = STATE_JS_TEMPLATE.read_text()
    helper = content[
        content.index("export const getRefValue =") : content.index(
            "export const getRefValues ="
        )
    ]
    subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            helper
            + """
import assert from 'node:assert/strict';
for (const value of ['', 0, false, 'filled']) {
  const result = getRefValue({current: {value}});
  assert.equal(result, value);
}
for (const ref of [undefined, {current: null},
                   {current: {querySelector: () => null}}]) {
  assert.equal(JSON.stringify({field: getRefValue(ref)}), '{"field":null}');
}
assert.equal(getRefValue({current: {
  querySelector: () => ({value: 'selected'})
}}), 'selected');
assert.equal(getRefValue({current: {type: 'checkbox', checked: false}}), false);
""",
        ],
        check=True,
        capture_output=True,
        text=True,
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


@pytest.mark.skipif(shutil.which("node") is None, reason="node missing")
def test_form_data_args_are_wrapped_before_emit() -> None:
    """Form data reads as a plain object but is sent as its ordered entries."""
    content = STATE_JS_TEMPLATE.read_text()
    start = content.index("const FORM_DATA_ENTRIES_KEY =")
    end = (
        content.index("\n};\n", content.index("export const encodeFormDataArgs =")) + 4
    )
    subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            """
// The test form stands in for an HTMLFormElement: an array of its entries.
globalThis.FormData = class {
  constructor(form) { this.form = form; }
  entries() { return this.form.values(); }
};
"""
            + content[start:end]
            + """
import assert from 'node:assert/strict';
const file = {name: 'upload.txt'};
const formData = getFormData([['tag', 'a'], ['file', file], ['tag', 'b']]);
assert.deepEqual(Object.keys(formData), ['tag', 'file']);
assert.equal(formData.tag, 'b');
const event = {name: 'state.submit', payload: {form_data: formData, count: 1}};
const sent = encodeFormDataArgs(event);
// The wrapped entries are plain own properties, so they survive Socket.IO
// copying the payload to extract binary attachments.
const copied = JSON.parse(JSON.stringify({...sent.payload}));
assert.deepEqual(copied, {
  form_data: {__reflex_form_data__: [['tag', 'a'], ['file', {name: 'upload.txt'}], ['tag', 'b']]},
  count: 1,
});
assert.equal(sent.payload.form_data.__reflex_form_data__[1][1], file);
// The event itself is left as it was.
assert.equal(event.payload.form_data, formData);
const plain = {name: 'state.other', payload: {count: 1}};
assert.equal(encodeFormDataArgs(plain), plain);
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_state_js_keeps_ref_value_exports_for_older_form_components() -> None:
    """Published reflex-components-core forms import these helpers from state.js."""
    content = STATE_JS_TEMPLATE.read_text()
    assert "export const getRefValue =" in content
    assert "export const getRefValues =" in content
