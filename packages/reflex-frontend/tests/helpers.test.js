/**
 * The standalone helpers under `utils/helpers`: each mirrors a Python builtin or
 * backs one event action, so the assertions state the Python behavior.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import compareDatetime from "$/utils/helpers/datetime";
import debounce from "$/utils/helpers/debounce";
import range from "$/utils/helpers/range";
import {
  pySetDifference,
  pySetHas,
  pySetIntersection,
  pySetIsDisjoint,
  pySetIsSubset,
  pySetSymmetricDifference,
  pySetUnion,
} from "$/utils/helpers/set";
import throttle from "$/utils/helpers/throttle";

describe("range", () => {
  test.each([
    [[5], [0, 1, 2, 3, 4]],
    [
      [2, 5],
      [2, 3, 4],
    ],
    [
      [0, 10, 3],
      [0, 3, 6, 9],
    ],
    [
      [5, 0, -2],
      [5, 3, 1],
    ],
    [[0], []],
    [[5, 2], []],
    [[0, 5, -1], []],
  ])("range(%j) yields %j", (args, expected) => {
    expect([...range(...args)]).toEqual(expected);
  });

  test("one range can be iterated more than once", () => {
    const numbers = range(3);
    expect([...numbers]).toEqual([0, 1, 2]);
    expect([...numbers]).toEqual([0, 1, 2]);
  });
});

describe("python set operations", () => {
  test("membership compares structured elements by value", () => {
    expect(pySetHas([[1, 2], { a: 1 }], [1, 2])).toBe(true);
    expect(pySetHas([[1, 2]], [2, 1])).toBe(false);
    expect(pySetHas([{ a: 1 }], { a: 1 })).toBe(true);
  });

  test("a string never matches the value it spells", () => {
    expect(pySetHas([1], "1")).toBe(false);
    expect(pySetHas(["[1,2]"], [1, 2])).toBe(false);
    expect(pySetHas(["null"], null)).toBe(false);
  });

  test("booleans equal the numbers they equal in python", () => {
    expect(pySetHas([1], true)).toBe(true);
    expect(pySetHas([0], false)).toBe(true);
    expect(pySetUnion([1, 0], [true, false, 2])).toEqual([1, 0, 2]);
  });

  test("union keeps the order of the first set, then the second", () => {
    expect(pySetUnion(["b", "a"], ["c", "a"])).toEqual(["b", "a", "c"]);
  });

  test("intersection and difference keep the order of the first set", () => {
    expect(pySetIntersection([3, 1, 2], [2, 3])).toEqual([3, 2]);
    expect(pySetDifference([3, 1, 2], [2, 3])).toEqual([1]);
  });

  test("symmetric difference holds each element once", () => {
    expect(pySetSymmetricDifference([1, 2, 3], [3, 4])).toEqual([1, 2, 4]);
    // The compiler puts the set first; the other operand may be a plain array.
    expect(pySetSymmetricDifference([2], [1, 1, 2])).toEqual([1]);
  });

  test("the other operand may be an array holding duplicates", () => {
    expect(pySetUnion([1], [2, 2, 1])).toEqual([1, 2]);
    expect(pySetIntersection([1, 2], [2, 2])).toEqual([2]);
    expect(pySetDifference([1, 2], [2, 2])).toEqual([1]);
  });

  test("subset and disjoint", () => {
    expect(pySetIsSubset([], [1])).toBe(true);
    expect(pySetIsSubset([1, 2], [2, 1, 3])).toBe(true);
    expect(pySetIsSubset([1, 4], [1, 2])).toBe(false);
    expect(pySetIsDisjoint([1, 2], [3])).toBe(true);
    expect(pySetIsDisjoint([1, 2], [2])).toBe(false);
    expect(pySetIsDisjoint([], [])).toBe(true);
  });
});

describe("compareDatetime", () => {
  test.each([
    ["2024-01-01", "2024-01-02", -1],
    ["2024-01-02", "2024-01-01", 1],
    ["2024-01-01", "2024-01-01", 0],
    ["2024-01-01 10:00:00", "2024-01-01T10:00:00", 0],
    ["2024-01-01T10:00:00.000001", "2024-01-01T10:00:00", 1],
    // Microseconds are beyond what a JS Date holds.
    ["2024-01-01T10:00:00.123456", "2024-01-01T10:00:00.123457", -1],
    ["2024-01-01T12:00:00+02:00", "2024-01-01T10:00:00Z", 0],
    ["2024-01-01T10:00:00-05:00", "2024-01-01T10:00:00+00:00", 1],
    // Years below 100 are not shifted into the 1900s.
    ["0001-01-01", "0099-12-31", -1],
  ])("%s against %s is %i", (lhs, rhs, expected) => {
    expect(compareDatetime(lhs, rhs)).toBe(expected);
  });

  test.each([
    // A date, a naive datetime and an aware one do not order in python.
    ["2024-01-01", "2024-01-01T00:00:00"],
    ["2024-01-01T00:00:00", "2024-01-01T00:00:00Z"],
    ["2024-01-01", null],
    ["2024-01-01", "not a date"],
  ])("%s and %s are incomparable", (lhs, rhs) => {
    expect(compareDatetime(lhs, rhs)).toBeNaN();
    expect(compareDatetime(rhs, lhs)).toBeNaN();
  });

  test("two values that are not datetimes compare equal only when identical", () => {
    expect(compareDatetime(null, null)).toBe(0);
    expect(compareDatetime("x", "x")).toBe(0);
    expect(compareDatetime("x", "y")).toBeNaN();
  });
});

describe("timers", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  test("debounce runs only the last call, once the delay passes", () => {
    const calls = [];
    debounce("debounce-last", () => calls.push("first"), 100);
    vi.advanceTimersByTime(99);
    debounce("debounce-last", () => calls.push("second"), 100);
    vi.advanceTimersByTime(99);
    expect(calls).toEqual([]);
    vi.advanceTimersByTime(1);
    expect(calls).toEqual(["second"]);
  });

  test("debounce keeps names apart", () => {
    const calls = [];
    debounce("debounce-a", () => calls.push("a"), 100);
    debounce("debounce-b", () => calls.push("b"), 100);
    vi.advanceTimersByTime(100);
    expect(calls).toEqual(["a", "b"]);
  });

  test("throttle allows one call per window", () => {
    expect(throttle("throttle-window", 100)).toBe(true);
    expect(throttle("throttle-window", 100)).toBe(false);
    vi.advanceTimersByTime(99);
    expect(throttle("throttle-window", 100)).toBe(false);
    vi.advanceTimersByTime(1);
    expect(throttle("throttle-window", 100)).toBe(true);
  });

  test("throttle keeps names apart", () => {
    expect(throttle("throttle-a", 100)).toBe(true);
    expect(throttle("throttle-b", 100)).toBe(true);
  });
});
