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
def test_apply_delta_shares_unchanged_values() -> None:
    """Deltas keep the identity of unchanged plain objects and arrays."""
    content = STATE_JS_TEMPLATE.read_text()
    helpers = content[
        content.index("const isPlainObject =") : content.index(
            "export const evalReactComponent ="
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
const parse = (v) => JSON.parse(JSON.stringify(v));
const rows = [{id: 1, tags: ['a']}, {id: 2, tags: ['b']}, {id: 3, tags: []}];
const state = {rows, kpi: {a: 1, b: {c: 2}}, n: 1, s: 'x', none: null};

// A delta equal to the current state returns the same state object.
assert.equal(applyDelta(state, parse(state)), state);
assert.equal(applyDelta(state, {}), state);

// One changed row: siblings keep their identity, the changed row does not.
const delta = parse({rows, kpi: state.kpi});
delta.rows[1].tags = ['c'];
const next = applyDelta(state, delta);
assert.notEqual(next, state);
assert.equal(next.kpi, state.kpi);
assert.notEqual(next.rows, rows);
assert.equal(next.rows[0], rows[0]);
assert.equal(next.rows[2], rows[2]);
assert.notEqual(next.rows[1], rows[1]);
assert.deepEqual(next.rows[1], {id: 2, tags: ['c']});
assert.deepEqual(rows[1], {id: 2, tags: ['b']});
assert.equal(next.n, 1);

// Length changes share the common prefix without mutating the old array.
const grown = applyDelta(state, {rows: parse([...rows, {id: 4, tags: []}])}).rows;
assert.equal(grown.length, 4);
assert.equal(grown[2], rows[2]);
const shrunk = applyDelta(state, {rows: parse(rows.slice(0, 2))}).rows;
assert.deepEqual(shrunk, rows.slice(0, 2));
assert.equal(shrunk[1], rows[1]);
assert.equal(rows.length, 3);

// Added, removed and renamed keys produce a new object with shared values.
const added = applyDelta(state, {kpi: parse({...state.kpi, d: 3})}).kpi;
assert.deepEqual(added, {a: 1, b: {c: 2}, d: 3});
assert.equal(added.b, state.kpi.b);
const removed = applyDelta(state, {kpi: parse({b: state.kpi.b})}).kpi;
assert.deepEqual(removed, {b: {c: 2}});
assert.equal(removed.b, state.kpi.b);
const undef = {kpi: {a: undefined}};
assert.deepEqual(applyDelta(undef, {kpi: {b: undefined}}).kpi, {b: undefined});

// Type changes and non-plain values are replaced as before.
assert.deepEqual(applyDelta(state, {kpi: [1]}).kpi, [1]);
assert.equal(applyDelta(state, {none: {}}).none.constructor, Object);
const date = new Date(0);
const withDate = {d: new Date(0)};
assert.equal(applyDelta(withDate, {d: date}).d, date);

// A "__proto__" key from JSON stays an own data property.
const proto = applyDelta({o: {}}, {o: JSON.parse('{"__proto__": {"x": 1}}')}).o;
assert.equal(Object.getPrototypeOf(proto), Object.prototype);
assert.deepEqual(Object.getOwnPropertyDescriptor(proto, '__proto__').value, {x: 1});
const protoState = {o: JSON.parse('{"__proto__": {"x": 1}, "y": [1]}')};
const protoNext = applyDelta(protoState, {o: JSON.parse('{"__proto__": {"x": 1}, "y": [2]}')}).o;
assert.equal(Object.getPrototypeOf(protoNext), Object.prototype);
assert.equal(Object.getOwnPropertyDescriptor(protoNext, '__proto__').value,
  Object.getOwnPropertyDescriptor(protoState.o, '__proto__').value);
assert.deepEqual(protoNext.y, [2]);
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
