import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(
  new URL(
    "../../../packages/reflex-base/src/reflex_base/.templates/web/utils/helpers/array.js",
    import.meta.url,
  ),
  "utf8",
);

/** Evaluate the actual frontend helper module and return its default export. */
async function loadCompareArrays() {
  const module = new vm.SourceTextModule(source, {
    identifier: "array.js",
    context: vm.createContext({}),
  });
  await module.link(() => {
    throw new Error("array.js must not have imports");
  });
  await module.evaluate();
  return module.namespace.default;
}

const compareArrays = await loadCompareArrays();

test("numeric arrays compare element-wise like Python lists", () => {
  assert.equal(compareArrays([10, 20], [5, 6]), 1);
  assert.equal(compareArrays([2], [10]), -1);
  assert.equal(compareArrays([1, 9], [1, 10]), -1);
  assert.equal(compareArrays([1, 10, 0], [1, 9, 0]), 1);
});

test("equal arrays compare equal and prefix sorts shorter first", () => {
  assert.equal(compareArrays([1, 2], [1, 2]), 0);
  assert.equal(compareArrays([1, 2], [1, 2, 3]), -1);
  assert.equal(compareArrays([1, 2, 3], [1, 2]), 1);
  assert.equal(compareArrays([], []), 0);
  assert.equal(compareArrays([], [1]), -1);
});

test("strings and booleans keep Python ordering", () => {
  assert.equal(compareArrays(["a", "c"], ["a", "b"]), 1);
  assert.equal(compareArrays([true], [false]), 1);
  assert.equal(compareArrays([1, "a"], [1, "b"]), -1);
});

test("nested arrays compare recursively", () => {
  assert.equal(compareArrays([[1, 2], [3]], [[1, 2], [2]]), 1);
  assert.equal(compareArrays([[1, 2]], [[1, 2]]), 0);
  assert.equal(compareArrays([[1]], [[1, 2]]), -1);
});

test("incomparable elements give NaN so ordering is false", () => {
  assert.ok(Number.isNaN(compareArrays([1, "a"], [1, 2])));
  assert.ok(Number.isNaN(compareArrays([null], [1])));
  assert.ok(Number.isNaN(compareArrays([[1], 2], [[1], [2]])));
});

test("NaN elements make every ordering comparison false like Python", () => {
  assert.ok(Number.isNaN(compareArrays([NaN], [1])));
  assert.ok(Number.isNaN(compareArrays([NaN], [NaN])));
  assert.ok(Number.isNaN(compareArrays([1, NaN], [1, 2])));
});

test("booleans compare numerically like Python bool subclassing int", () => {
  assert.equal(compareArrays([true], [1]), 0);
  assert.equal(compareArrays([true], [2]), -1);
  assert.equal(compareArrays([false], [1]), -1);
  assert.equal(compareArrays([0.5], [true]), -1);
  assert.equal(compareArrays([1], [true]), 0);
});
