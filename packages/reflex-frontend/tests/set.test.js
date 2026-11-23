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
  pySetKey,
  pySetMatch,
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

test("structured elements compare their elements as Python does", () => {
  expect(pySetHas([[true]], [1])).toBe(true);
  expect(pySetHas([{ value: [false] }], { value: [0] })).toBe(true);
  expect(pySetUnion([[true]], [[1]])).toEqual([[true]]);
  expect(pySetIntersection([[true]], [[1]])).toEqual([[true]]);
  expect(pySetHas([["1"]], [1])).toBe(false);
  expect(pySetHas([[NaN]], [null])).toBe(false);
  expect(pySetHas([[Infinity]], [null])).toBe(false);
  expect(pySetHas([["o"]], {})).toBe(false);
});

test("a structured key grows with the element, not with its depth", () => {
  let nested = "leaf";
  for (let i = 0; i < 40; i++) nested = [nested];
  expect(pySetKey(nested).length).toBeLessThan(200);
  expect(pySetHas([nested], nested)).toBe(true);
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

test("a set matches the set case it equals, whatever its order", () => {
  // The switch that rx.match compiles to for a set case.
  const match = (tags) => {
    switch (
      JSON.stringify(
        pySetMatch(tags, [
          ["c", "d"],
          [[1, 2], "a"],
        ]),
      )
    ) {
      case JSON.stringify(["c", "d"]):
        return "cd";
      case JSON.stringify([[1, 2], "a"]):
        return "pair";
      default:
        return "other";
    }
  };
  expect(match(["c", "d"])).toBe("cd");
  expect(match(["d", "c"])).toBe("cd");
  expect(match(["d", "c", "d"])).toBe("other");
  expect(match(["a", [1, 2]])).toBe("pair");
  expect(match(["c"])).toBe("other");
  expect(match(["c", "d", "e"])).toBe("other");
  expect(match("cd")).toBe("other");
  expect(match(null)).toBe("other");
});

test("a set case matches by Python equality", () => {
  expect(pySetMatch([true, 2], [[1, 2]])).toEqual([1, 2]);
  expect(pySetMatch(["1"], [[1]])).toEqual(["1"]);
  expect(pySetMatch([[1, 2]], [["o[1,2]"]])).toEqual([[1, 2]]);
  expect(pySetMatch([NaN], [[null]])).toEqual([NaN]);
  expect(pySetMatch([], [null, []])).toEqual([]);
  const value = { a: 1 };
  expect(pySetMatch(value, [[]])).toBe(value);
});
