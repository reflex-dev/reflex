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
// Values read from id refs replace the form's entries of the same name.
const withRefs = getFormData(
  [['tag', 'a'], ['agree', 'on'], ['tag', 'b']],
  {agree: true, unset: null},
);
assert.deepEqual({...withRefs}, {tag: 'b', agree: true, unset: null});
assert.deepEqual(
  encodeFormDataArgs({name: 'state.submit', payload: {form_data: withRefs}})
    .payload.form_data.__reflex_form_data__,
  [['tag', 'a'], ['agree', true], ['tag', 'b'], ['unset', null]],
);
// A replaced value keeps its place, as when spreading the refs over the form's
// entries.
const ordered = getFormData([['title', 'typed'], ['note', 'n']], {title: 'ref'});
assert.deepEqual(Object.keys(ordered), ['title', 'note']);
assert.deepEqual(
  encodeFormDataArgs({name: 'state.submit', payload: {form_data: ordered}})
    .payload.form_data.__reflex_form_data__,
  [['title', 'ref'], ['note', 'n']],
);
// A name submitted more than once, like a checkbox group with an id, keeps
// its values instead of taking the ref's single value.
const group = getFormData(
  [['colors', 'red'], ['colors', 'blue']],
  {colors: 'red'},
);
assert.deepEqual(
  encodeFormDataArgs({name: 'state.submit', payload: {form_data: group}})
    .payload.form_data.__reflex_form_data__,
  [['colors', 'red'], ['colors', 'blue']],
);
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


def _run_apply_delta_script(script: str) -> None:
    """Run a node script against the delta helpers of state.js.

    The script sees ``applyDelta`` and ``applyDecoded``, which applies a delta
    as the update handler does once a decoder ran.

    Args:
        script: The JavaScript to run after the helpers.
    """
    content = STATE_JS_TEMPLATE.read_text()
    helpers = content[
        content.index("const isPlainObject =") : content.index(
            "export const evalReactComponent ="
        )
    ]
    assert "export const applyDelta" in helpers
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            helpers
            + """
import assert from 'node:assert/strict';
const applyDecoded = (state, delta) => {
  decodedDeltas.add(delta);
  return applyDelta(state, delta);
};
"""
            + script,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node missing")
@pytest.mark.parametrize("apply", ["applyDelta", "applyDecoded"])
def test_apply_delta_shares_unchanged_values(apply: str) -> None:
    """Deltas keep the identity of unchanged plain objects and arrays.

    A decoded delta that is a tree is shared the same way as a plain one.

    Args:
        apply: The function applying the deltas.
    """
    _run_apply_delta_script(
        f"const apply = {apply};"
        + """
const parse = (v) => JSON.parse(JSON.stringify(v));
const rows = [{id: 1, tags: ['a']}, {id: 2, tags: ['b']}, {id: 3, tags: []}];
const state = {rows, kpi: {a: 1, b: {c: 2}}, n: 1, s: 'x', none: null};

// A delta equal to the current state returns the same state object.
assert.equal(apply(state, parse(state)), state);
assert.equal(apply(state, {}), state);

// One changed row: siblings keep their identity, the changed row does not.
const delta = parse({rows, kpi: state.kpi});
delta.rows[1].tags = ['c'];
const next = apply(state, delta);
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
const grown = apply(state, {rows: parse([...rows, {id: 4, tags: []}])}).rows;
assert.equal(grown.length, 4);
assert.equal(grown[2], rows[2]);
const shrunk = apply(state, {rows: parse(rows.slice(0, 2))}).rows;
assert.deepEqual(shrunk, rows.slice(0, 2));
assert.equal(shrunk[1], rows[1]);
assert.equal(rows.length, 3);

// Added, removed and renamed keys produce a new object with shared values.
const added = apply(state, {kpi: parse({...state.kpi, d: 3})}).kpi;
assert.deepEqual(added, {a: 1, b: {c: 2}, d: 3});
assert.equal(added.b, state.kpi.b);
const removed = apply(state, {kpi: parse({b: state.kpi.b})}).kpi;
assert.deepEqual(removed, {b: {c: 2}});
assert.equal(removed.b, state.kpi.b);
const undef = {kpi: {a: undefined}};
assert.deepEqual(apply(undef, {kpi: {b: undefined}}).kpi, {b: undefined});

// Reordering a mapping without changing its values takes the new key order.
const ordered = {d: {a: 1, b: {c: 2}}};
const reordered = apply(ordered, {d: JSON.parse('{"b": {"c": 2}, "a": 1}')}).d;
assert.deepEqual(Object.keys(reordered), ['b', 'a']);
assert.equal(reordered.b, ordered.d.b);

// Values compare with Object.is: python's -0.0 replaces 0, while a repeated
// NaN (revived by parseJson) is unchanged.
const zeros = {z: 0, a: [0], o: {v: 0}};
const negated = apply(zeros, JSON.parse('{"z": -0.0, "a": [-0.0], "o": {"v": -0.0}}'));
assert.deepEqual(negated, {z: -0, a: [-0], o: {v: -0}});
const nans = {x: NaN, a: [NaN], o: {v: NaN}};
assert.equal(apply(nans, {x: NaN, a: [NaN], o: {v: NaN}}), nans);

// Type changes and non-plain values are replaced as before.
assert.deepEqual(apply(state, {kpi: [1]}).kpi, [1]);
assert.equal(apply(state, {none: {}}).none.constructor, Object);
const date = new Date(0);
const withDate = {d: new Date(0)};
assert.equal(apply(withDate, {d: date}).d, date);

// A "__proto__" key from JSON stays an own data property.
const proto = apply({o: {}}, {o: JSON.parse('{"__proto__": {"x": 1}}')}).o;
assert.equal(Object.getPrototypeOf(proto), Object.prototype);
assert.deepEqual(Object.getOwnPropertyDescriptor(proto, '__proto__').value, {x: 1});
const protoState = {o: JSON.parse('{"__proto__": {"x": 1}, "y": [1]}')};
const protoNext = apply(protoState, {o: JSON.parse('{"__proto__": {"x": 1}, "y": [2]}')}).o;
assert.equal(Object.getPrototypeOf(protoNext), Object.prototype);
assert.equal(Object.getOwnPropertyDescriptor(protoNext, '__proto__').value,
  Object.getOwnPropertyDescriptor(protoState.o, '__proto__').value);
assert.deepEqual(protoNext.y, [2]);
"""
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="node missing")
def test_apply_delta_shares_objects_a_decoded_delta_holds_twice() -> None:
    """A delta holding an object twice keeps one result for it."""
    _run_apply_delta_script("""
// Two rows holding one product, as a decoder that dedupes objects returns them.
const decoded = (name) => {
  const product = {name};
  return {rows: [{id: 1, product}, {id: 2, product}]};
};
const first = applyDecoded({rows: []}, decoded('a'));
assert.equal(first.rows[0].product, first.rows[1].product);

// The same values decoded again change nothing.
assert.equal(applyDecoded(first, decoded('a')), first);

// A changed object stays one object.
const changed = applyDecoded(first, decoded('b'));
assert.notEqual(changed.rows[0].product, first.rows[0].product);
assert.equal(changed.rows[0].product, changed.rows[1].product);
assert.deepEqual(changed.rows[1].product, {name: 'b'});

// An unchanged object shares the previous one in a new place as well: beside
// an unchanged row, in a value that was null, and under a new key.
const product = {name: 'a'};
const grown = applyDecoded(first, {rows: [{id: 1, product}, {id: 2, product}, {id: 3, product}]});
assert.equal(grown.rows[0], first.rows[0]);
assert.equal(grown.rows[2].product, first.rows[0].product);
const filled = applyDecoded({a: {id: 1}, b: null}, (() => {
  const shared = {id: 1};
  return {a: shared, b: shared, c: {nested: shared}};
})());
assert.equal(filled.b, filled.a);
assert.equal(filled.c.nested, filled.a);

// A delta no decoder produced is a tree and keeps the plain sharing.
const plain = {a: {id: 1}};
assert.equal(applyDelta(plain, {a: {id: 1}}), plain);
""")


@pytest.mark.skipif(shutil.which("node") is None, reason="node missing")
def test_apply_delta_keeps_the_cycles_of_a_decoded_delta() -> None:
    """A cycle of a decoded delta leads back to the object the state holds."""
    _run_apply_delta_script("""
// A product whose rows point back at it, with a list beside the cycle.
const cyclic = (name, qty = 1) => {
  const product = {name, tags: ['x']};
  product.rows = [{id: 1, product}, {id: 2, qty, product}];
  return {product};
};
const isCycle = (product) =>
  product.rows.every((row) => row.product === product);

// In place of another value, and in a new place.
const replaced = applyDecoded({product: {name: 'a'}}, cyclic('a'));
assert.ok(isCycle(replaced.product));
const added = applyDecoded({}, cyclic('a'));
assert.ok(isCycle(added.product));

// An unchanged cycle keeps the state, the previous cycle included.
assert.equal(applyDecoded(replaced, cyclic('a')), replaced);
assert.equal(applyDecoded(added, cyclic('a')), added);

// A change anywhere on the cycle gives every object on it a new result that
// leads back to the new product, and keeps what is off the cycle.
for (const changed of [
  applyDecoded(replaced, cyclic('b')),
  applyDecoded(replaced, cyclic('a', 2)),
]) {
  assert.notEqual(changed.product, replaced.product);
  assert.ok(isCycle(changed.product));
  assert.ok(isCycle(replaced.product));
  assert.notEqual(changed.product.rows[0], replaced.product.rows[0]);
  assert.equal(changed.product.tags, replaced.product.tags);
}
assert.equal(applyDecoded(replaced, cyclic('b')).product.name, 'b');
assert.equal(applyDecoded(replaced, cyclic('a', 2)).product.rows[1].qty, 2);

// A cycle entered from below, and a var holding an object of the cycle too.
const entered = applyDecoded({row: {id: 0}, product: null}, (() => {
  const {product} = cyclic('a');
  return {row: product.rows[0], product};
})());
assert.equal(entered.row, entered.product.rows[0]);
assert.ok(isCycle(entered.product));
assert.equal(entered.row.product, entered.product);
""")
