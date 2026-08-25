// Exercises the applyDelta helper from the frontend templates.
//
// Invoked as `node delta_js_cases.mjs <path to delta.js>` by
// tests/units/compiler/test_delta_js_template.py. The module is loaded from a
// data URL because the template tree has no package.json declaring ESM.
import { readFile } from "node:fs/promises";

const source = await readFile(process.argv[2], "utf8");
const { applyDelta, isEquivalent } = await import(
  "data:text/javascript;charset=utf-8," + encodeURIComponent(source)
);

const results = {};
const check = (name, fn) => {
  results[name] = fn();
};

check("empty_delta_keeps_state", () => {
  const state = { a: 1 };
  return applyDelta(state, {}) === state;
});

check("equal_primitives_keep_state", () => {
  const state = { a: 1, b: "x", c: true, d: null };
  return applyDelta(state, { a: 1, b: "x", c: true, d: null }) === state;
});

check("equal_nested_values_keep_state", () => {
  const state = { rows: [{ id: 1, tags: ["a", "b"] }], meta: { n: 1 } };
  const delta = JSON.parse(JSON.stringify(state));
  return applyDelta(state, delta) === state;
});

check("changed_primitive_applies", () => {
  const state = { a: 1, b: 2 };
  const next = applyDelta(state, { a: 3 });
  return next !== state && next.a === 3 && next.b === 2;
});

check("unchanged_keys_keep_reference", () => {
  const rows = [{ id: 1 }];
  const state = { count: 0, rows };
  const next = applyDelta(state, { count: 1, rows: [{ id: 1 }] });
  return next !== state && next.count === 1 && next.rows === rows;
});

check("changed_nested_value_applies", () => {
  const state = { rows: [{ id: 1 }] };
  const delta = { rows: [{ id: 2 }] };
  const next = applyDelta(state, delta);
  return next.rows === delta.rows;
});

check("missing_key_is_added", () => {
  const state = { a: 1 };
  const next = applyDelta(state, { b: undefined });
  return next !== state && "b" in next && next.b === undefined;
});

check("array_length_difference_applies", () => {
  const state = { rows: [1, 2] };
  return applyDelta(state, { rows: [1, 2, 3] }) !== state;
});

check("array_order_difference_applies", () => {
  const state = { rows: [1, 2] };
  return applyDelta(state, { rows: [2, 1] }) !== state;
});

check("array_vs_object_applies", () => {
  const state = { value: [] };
  return applyDelta(state, { value: {} }) !== state;
});

check("extra_nested_key_applies", () => {
  const state = { meta: { a: 1 } };
  return applyDelta(state, { meta: { a: 1, b: 2 } }) !== state;
});

check("missing_nested_key_applies", () => {
  const state = { meta: { a: 1, b: 2 } };
  return applyDelta(state, { meta: { a: 1 } }) !== state;
});

check("renamed_nested_key_applies", () => {
  const state = { meta: { a: 1 } };
  return applyDelta(state, { meta: { b: 1 } }) !== state;
});

check("null_vs_object_applies", () => {
  const state = { meta: null };
  return applyDelta(state, { meta: {} }) !== state;
});

check("object_vs_null_applies", () => {
  const state = { meta: {} };
  return applyDelta(state, { meta: null }) !== state;
});

check("type_change_applies", () => {
  const state = { value: 1 };
  return applyDelta(state, { value: "1" }) !== state;
});

check("sparse_array_holes_compare_equal", () => {
  return isEquivalent([1, , 3], [1, undefined, 3]);
});

check("non_plain_objects_are_not_equivalent", () => {
  const date = new Date(0);
  return !isEquivalent(date, new Date(0)) && isEquivalent(date, date);
});

check("deeply_equal_nested_arrays", () => {
  const state = { grid: [[1, [2, { a: [3] }]]] };
  return (
    applyDelta(state, JSON.parse(JSON.stringify(state))) === state &&
    applyDelta(state, { grid: [[1, [2, { a: [4] }]]] }) !== state
  );
});

process.stdout.write(JSON.stringify(results));
