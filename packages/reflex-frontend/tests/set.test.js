/**
 * Unit tests for `utils/helpers/set.js`.
 *
 * The helpers back every SetVar operation, so they run on each render; these
 * pin the Python set semantics they give the serialized array, including an
 * optional set whose value is null (or undefined, through a missing field),
 * which counts as an empty set.
 */
import { describe, expect, test } from "vitest";

import {
  pySetDifference,
  pySetHas,
  pySetIntersection,
  pySetIsDisjoint,
  pySetIsSubset,
  pySetSymmetricDifference,
  pySetUnion,
} from "$/utils/helpers/set";

const sorted = (arr) => [...arr].sort();

test("set operations on present sets", () => {
  const a = ["a", "b"];
  const b = ["b", "c"];
  expect(pySetHas(a, "a")).toBe(true);
  expect(pySetHas(a, "c")).toBe(false);
  expect(sorted(pySetUnion(a, b))).toEqual(["a", "b", "c"]);
  expect(pySetIntersection(a, b)).toEqual(["b"]);
  expect(pySetDifference(a, b)).toEqual(["a"]);
  expect(sorted(pySetSymmetricDifference(a, b))).toEqual(["a", "c"]);
  expect(pySetIsSubset(["b"], a)).toBe(true);
  expect(pySetIsSubset(a, b)).toBe(false);
  expect(pySetIsDisjoint(a, ["z"])).toBe(true);
  expect(pySetIsDisjoint(a, b)).toBe(false);
});

test("set elements compare by value", () => {
  expect(pySetHas([[1, 2]], [1, 2])).toBe(true);
  expect(pySetHas([[1, 2]], "o[1,2]")).toBe(false);
  expect(pySetHas([0, 1], false)).toBe(true);
  expect(pySetHas([NaN], NaN)).toBe(true);
  expect(pySetUnion([0, 1], [true])).toEqual([0, 1]);
  expect(
    pySetSymmetricDifference(
      [[3, 4]],
      [
        [3, 4],
        [5, 6],
        [5, 6],
      ],
    ),
  ).toEqual([[5, 6]]);
});

describe.each([null, undefined])("a %s set is empty", (none) => {
  const x = ["x", "y"];

  test("membership", () => {
    expect(pySetHas(none, "x")).toBe(false);
    expect(pySetHas(none, null)).toBe(false);
  });

  test("combinations", () => {
    expect(pySetUnion(none, x)).toEqual(x);
    expect(pySetUnion(x, none)).toEqual(x);
    expect(pySetUnion(none, none)).toEqual([]);
    expect(pySetIntersection(none, x)).toEqual([]);
    expect(pySetIntersection(x, none)).toEqual([]);
    expect(pySetDifference(none, x)).toEqual([]);
    expect(pySetDifference(x, none)).toEqual(x);
    expect(pySetSymmetricDifference(none, x)).toEqual(x);
    expect(pySetSymmetricDifference(x, none)).toEqual(x);
    expect(pySetSymmetricDifference(none, none)).toEqual([]);
  });

  test("comparisons", () => {
    expect(pySetIsSubset(none, x)).toBe(true);
    expect(pySetIsSubset(x, none)).toBe(false);
    expect(pySetIsSubset([], none)).toBe(true);
    expect(pySetIsSubset(none, none)).toBe(true);
    expect(pySetIsDisjoint(none, x)).toBe(true);
    expect(pySetIsDisjoint(x, none)).toBe(true);
  });

  test("results never alias an operand", () => {
    const union = pySetUnion(x, none);
    expect(union).not.toBe(x);
    expect(pySetDifference(x, none)).not.toBe(x);
  });
});
