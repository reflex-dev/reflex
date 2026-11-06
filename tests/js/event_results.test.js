/**
 * Unit tests for `utils/event_results.js`: the result stream a backend event
 * dispatch returns, and the routing of the backend's result records to it.
 */
import { describe, expect, test, vi } from "vitest";

import {
  ResultStream,
  applyResults,
  debouncedResult,
  failPendingRequests,
  recordThrottled,
  registerRequest,
  throttledResult,
} from "$/utils/event_results";

/** Collect every value a stream yields with `for await`. */
const collect = async (stream) => {
  const values = [];
  for await (const value of stream) {
    values.push(value);
  }
  return values;
};

describe("ResultStream", () => {
  test("iterates values in order and awaits to the last one", async () => {
    const stream = new ResultStream();
    const iterated = collect(stream);
    stream.push(1);
    stream.push({ two: 2 });
    stream.push(3);
    stream.close();
    expect(await iterated).toEqual([1, { two: 2 }, 3]);
    expect(await stream).toBe(3);
    // A late iterator still sees every value.
    expect(await collect(stream)).toEqual([1, { two: 2 }, 3]);
  });

  test("resolves undefined when the handler produced no value", async () => {
    const stream = new ResultStream();
    stream.close();
    expect(await stream).toBeUndefined();
    expect(await collect(stream)).toEqual([]);
  });

  test("delivers the values before the failure, then rejects", async () => {
    const stream = new ResultStream();
    stream.push("partial");
    stream.fail(new Error("ValueError: bad page"));
    await expect(stream).rejects.toThrow("ValueError: bad page");
    const seen = [];
    await expect(async () => {
      for await (const value of stream) {
        seen.push(value);
      }
    }).rejects.toThrow("bad page");
    expect(seen).toEqual(["partial"]);
  });

  test("a failure nobody awaits is not an unhandled rejection", async () => {
    const unhandled = vi.fn();
    process.on("unhandledRejection", unhandled);
    try {
      new ResultStream().fail(new Error("ignored"));
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(unhandled).not.toHaveBeenCalled();
    } finally {
      process.off("unhandledRejection", unhandled);
    }
  });

  test("nothing arrives after it settled", async () => {
    const stream = new ResultStream();
    stream.close(true);
    stream.push(1);
    stream.fail(new Error("late"));
    expect(stream.cancelled).toBe(true);
    expect(await stream).toBeUndefined();
  });

  test("an early break stops the iterator, not the stream", async () => {
    const stream = new ResultStream();
    stream.push(1);
    stream.push(2);
    for await (const value of stream) {
      expect(value).toBe(1);
      break;
    }
    stream.close();
    expect(await stream).toBe(2);
  });

  test("merge interleaves values and completes when every stream has", async () => {
    const a = new ResultStream();
    const b = new ResultStream();
    a.push("a1");
    const merged = ResultStream.merge([a, b]);
    b.push("b1");
    a.push("a2");
    a.close();
    expect(merged.settled).toBe(false);
    b.close();
    expect(await collect(merged)).toEqual(["a1", "b1", "a2"]);
    expect(await merged).toBe("a2");
  });

  test("merge fails with the first stream to fail", async () => {
    const a = new ResultStream();
    const b = new ResultStream();
    const merged = ResultStream.merge([a, b]);
    b.fail(new Error("b broke"));
    a.fail(new Error("a broke"));
    await expect(merged).rejects.toThrow("b broke");
  });

  test("merge of one stream is that stream, of none a completed one", async () => {
    const only = new ResultStream();
    expect(ResultStream.merge([only])).toBe(only);
    const none = ResultStream.merge([]);
    expect(none.settled).toBe(true);
    expect(await none).toBeUndefined();
  });

  test("follow pipes a stream in and completes on anything else", async () => {
    const source = new ResultStream();
    source.push(1);
    const follower = new ResultStream();
    follower.follow(source);
    source.push(2);
    source.close();
    expect(await collect(follower)).toEqual([1, 2]);

    const nothing = new ResultStream();
    nothing.follow(undefined);
    expect(nothing.settled).toBe(true);
  });
});

describe("result routing", () => {
  test("routes values, completion and failure by request id", async () => {
    const ok = new ResultStream();
    const bad = new ResultStream();
    const okId = registerRequest(ok);
    const badId = registerRequest(bad);
    expect(okId).not.toBe(badId);

    applyResults([
      { id: okId, value: 1 },
      { id: badId, value: "x" },
      { id: "stale:0", value: "from before a reload" },
    ]);
    applyResults([
      { id: okId, value: 2, done: true },
      { id: badId, error: "ValueError: bad page" },
    ]);
    expect(await collect(ok)).toEqual([1, 2]);
    await expect(bad).rejects.toThrow("ValueError: bad page");
    expect(bad.values).toEqual(["x"]);

    // Completed requests are forgotten.
    applyResults([{ id: okId, value: 3 }]);
    expect(ok.values).toEqual([1, 2]);
  });

  test("a cancelled request completes with its values", async () => {
    const stream = new ResultStream();
    const id = registerRequest(stream);
    applyResults([
      { id, value: 1 },
      { id, done: true, cancelled: true },
    ]);
    expect(stream.cancelled).toBe(true);
    expect(await stream).toBe(1);
  });

  test("a disconnect fails every pending request", async () => {
    const a = new ResultStream();
    const b = new ResultStream();
    const aId = registerRequest(a);
    registerRequest(b);
    failPendingRequests(new Error("disconnected"));
    await expect(a).rejects.toThrow("disconnected");
    await expect(b).rejects.toThrow("disconnected");
    // A record arriving after the disconnect finds nothing to update.
    applyResults([{ id: aId, done: true }]);
    expect(a.error.message).toBe("disconnected");
  });
});

describe("debounce and throttle", () => {
  test("calls in one debounce window share the stream of the dispatch that fires", async () => {
    let fire;
    const schedule = (run) => {
      fire = run;
    };
    const dispatched = new ResultStream();
    const dispatch = vi.fn(() => dispatched);

    const first = debouncedResult("search__300", schedule, dispatch);
    const second = debouncedResult("search__300", schedule, dispatch);
    expect(second).toBe(first);
    expect(dispatch).not.toHaveBeenCalled();

    fire();
    expect(dispatch).toHaveBeenCalledTimes(1);
    dispatched.push("hits");
    dispatched.close();
    expect(await first).toBe("hits");

    // The next window gets a new stream.
    const third = debouncedResult("search__300", schedule, dispatch);
    expect(third).not.toBe(first);
  });

  test("a dropped throttled call shares the open dispatch, or gets a completed stream", async () => {
    const open = new ResultStream();
    expect(recordThrottled("save__500", open)).toBe(open);
    expect(throttledResult("save__500")).toBe(open);
    open.push("saved");
    open.close();
    const late = throttledResult("save__500");
    expect(late).not.toBe(open);
    expect(late.settled).toBe(true);
    expect(await late).toBeUndefined();
    expect(throttledResult("other__500").settled).toBe(true);
  });
});
