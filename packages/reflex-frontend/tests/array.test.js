/**
 * Unit tests for `utils/helpers/array.js`.
 *
 * `compareArrays` backs the ordering operators of list Vars, so the
 * assertions state what Python returns for the same lists. NaN stands for
 * a pair Python cannot order, so every ordering operator gives false.
 */
import { describe, expect, test } from "vitest";

import compareArrays from "$/utils/helpers/array";
import compareDatetime from "$/utils/helpers/datetime";

describe("compareArrays", () => {
  test.each([
    [[10, 20], [5, 6], 1],
    [[2], [10], -1],
    [[1, 9], [1, 10], -1],
    [[1, 10, 0], [1, 9, 0], 1],
    [[1, 2], [1, 2], 0],
    [[1, 2], [1, 2, 3], -1],
    [[1, 2, 3], [1, 2], 1],
    [[], [], 0],
    [[], [1], -1],
    [["a", "c"], ["a", "b"], 1],
    [[1, "a"], [1, "b"], -1],
    [[[1, 2], [3]], [[1, 2], [2]], 1],
    [[[1, 2]], [[1, 2]], 0],
    [[[1]], [[1, 2]], -1],
    [[true], [false], 1],
    [[true], [1], 0],
    [[true], [2], -1],
    [[false], [1], -1],
    [[0.5], [true], -1],
  ])("compareArrays(%j, %j) is %d", (lhs, rhs, expected) => {
    expect(compareArrays(lhs, rhs)).toBe(expected);
  });

  test.each([
    [
      [1, "a"],
      [1, 2],
    ],
    [[null], [1]],
    [
      [[1], 2],
      [[1], [2]],
    ],
    [[NaN], [1]],
    [
      [1, NaN],
      [1, 2],
    ],
    [null, [1]],
    [[1], undefined],
    [null, null],
  ])("compareArrays(%j, %j) cannot be ordered", (lhs, rhs) => {
    expect(compareArrays(lhs, rhs)).toBeNaN();
  });

  test("a NaN item equals NaN, like Python's identity check on list items", () => {
    // Python compares list items with `x is y or x == y`, so the same NaN
    // object (math.nan, or one list compared with itself) counts as equal.
    expect(compareArrays([NaN], [NaN])).toBe(0);
    expect(compareArrays([NaN, 1], [NaN, 2])).toBe(-1);
    expect(compareArrays([[NaN]], [[NaN], 1])).toBe(-1);
    expect(compareArrays([{ a: NaN }, 1], [{ a: NaN }, 2])).toBe(-1);
    expect(compareArrays([0], [-0])).toBe(0);
  });

  test("strings order by code point, not UTF-16 code unit", () => {
    // U+1F600 is a surrogate pair starting 0xD83D, below U+FF5E in UTF-16.
    expect(compareArrays(["\u{1F600}"], ["～"])).toBe(1);
    expect(compareArrays(["～"], ["\u{1F600}"])).toBe(-1);
    expect(compareArrays(["a\u{1F600}"], ["a\u{1F601}"])).toBe(-1);
    expect(compareArrays(["ab"], ["abc"])).toBe(-1);
  });

  test("equal dicts compare equal, unequal dicts cannot be ordered", () => {
    expect(compareArrays([{ a: 1 }], [{ a: 1 }])).toBe(0);
    expect(compareArrays([{ a: 1, b: 2 }], [{ b: 2, a: 1 }])).toBe(0);
    expect(compareArrays([{ a: 1 }, 1], [{ a: 1 }, 2])).toBe(-1);
    expect(compareArrays([{ a: true }], [{ a: 1 }])).toBe(0);
    expect(compareArrays([{ a: [1, { b: 2 }] }], [{ a: [1, { b: 2 }] }])).toBe(
      0,
    );
    expect(compareArrays([{ a: 1 }], [{ a: 2 }])).toBeNaN();
    expect(compareArrays([{ a: 1 }], [{ b: 1 }])).toBeNaN();
    expect(compareArrays([{ a: 1 }], [{ a: 1, b: 2 }])).toBeNaN();
  });

  test("an item comparator orders serialized dates by their value", () => {
    // As strings the UTC offset is ignored; compareDatetime orders instants.
    expect(
      compareArrays(
        ["2024-01-01 00:00:00+01:00"],
        ["2024-01-01 00:00:00+00:00"],
        compareDatetime,
      ),
    ).toBe(-1);
    expect(
      compareArrays(
        [["2024-01-02"]],
        [["2024-01-01"], ["2024-01-03"]],
        compareDatetime,
      ),
    ).toBe(1);
    expect(
      compareArrays(["2024-01-01"], ["2024-01-01 00:00:00"], compareDatetime),
    ).toBeNaN();
  });
});
