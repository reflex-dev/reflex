import { describe, expect, test, vi } from "vitest";

import compareDatetime from "@reflex-dev/reflex-base/helpers/datetime";
import debounce from "@reflex-dev/reflex-base/helpers/debounce";
import throttle from "@reflex-dev/reflex-base/helpers/throttle";

describe("compareDatetime helper", () => {
  test("orders serialized python datetimes without local-tz drift", () => {
    expect(compareDatetime("2020-01-02", "2020-01-03")).toBe(-1);
    expect(compareDatetime("2020-01-02 10:00:00", "2020-01-02 09:00:00")).toBe(1);
    expect(
      compareDatetime("2020-01-02 10:00:00+02:00", "2020-01-02 08:00:00Z"),
    ).toBe(0);
  });

  test("mismatched kinds and unparsable values are incomparable", () => {
    expect(compareDatetime("2020-01-02", "2020-01-02 00:00:00")).toBeNaN();
    expect(compareDatetime("garbage", "2020-01-02")).toBeNaN();
    expect(compareDatetime(null, null)).toBe(0);
  });
});

describe("debounce helper", () => {
  test("collapses rapid calls keyed by name", () => {
    vi.useFakeTimers();
    const spy = vi.fn();
    debounce("key", spy, 50);
    debounce("key", spy, 50);
    vi.advanceTimersByTime(60);
    expect(spy).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});

describe("throttle helper", () => {
  test("allows one call per window per key", () => {
    vi.useFakeTimers();
    expect(throttle("tkey", 100)).toBe(true);
    expect(throttle("tkey", 100)).toBe(false);
    vi.advanceTimersByTime(120);
    expect(throttle("tkey", 100)).toBe(true);
    vi.useRealTimers();
  });
});
