/**
 * Server-provided JavaScript (`_call_script`, `_call_function` and their
 * callbacks) runs through a Function-constructor helper, not a direct eval, so
 * the minifier may mangle this module. These pin what the generated strings
 * can see and what the script returns.
 */
import { describe, expect, test, vi } from "vitest";

import { eventLoop } from "$/utils/context-registry";
import { applyEvent, getToken } from "$/utils/state";

const callScript = (code, callback, socket = null) =>
  applyEvent(
    { name: "_call_script", payload: { javascript_code: code, callback } },
    socket,
    null,
    null,
  );

describe("_call_script", () => {
  test("returns the completion value of a statement list to the callback", async () => {
    const seen = [];
    await callScript("var x = 20; x + 1", (result) => seen.push(result));
    expect(seen).toEqual([21]);
  });

  test("callback strings dispatch through the late-bound addEvents", async () => {
    eventLoop.addEvents = vi.fn();
    await callScript(
      "42",
      '((_result) => addEvents([ReflexEvent("state.set", {v: _result})], [_result], {}))',
    );
    expect(eventLoop.addEvents).toHaveBeenCalledTimes(1);
    const [events, args] = eventLoop.addEvents.mock.calls[0];
    expect(events[0].name).toBe("state.set");
    expect(events[0].payload).toEqual({ v: 42 });
    expect(args).toEqual([42]);
  });

  test("runs strict and sees no other module-local names", async () => {
    const onerror = vi.fn();
    window.onerror = onerror;
    await callScript("undeclared = 1");
    await callScript("eventLoop");
    expect(onerror).toHaveBeenCalledTimes(2);
    expect(onerror.mock.calls[0][4]).toBeInstanceOf(ReferenceError);
    expect(onerror.mock.calls[1][4]).toBeInstanceOf(ReferenceError);
  });

  test("scripts keep the socket, navigate, params and token names", async () => {
    // Apps written against direct eval call socket.disconnect() and read the
    // session token from a script.
    const socket = { disconnect: vi.fn() };
    const token = getToken();
    expect(typeof token).toBe("string");
    const seen = [];
    await callScript(
      "socket.disconnect(); [typeof navigate, typeof params, token]",
      (result) => seen.push(result),
      socket,
    );
    expect(socket.disconnect).toHaveBeenCalledTimes(1);
    expect(seen).toEqual([["object", "object", token]]);
  });

  test("callback strings can use every helper this module exports", async () => {
    // Var operations inside a callback compile to helpers such as pyMod,
    // isTrue or pyStrLength, which compiled pages import but a string cannot.
    eventLoop.addEvents = vi.fn();
    await callScript(
      "7",
      '((_result) => addEvents([ReflexEvent("s.set", {x: pyMod(_result, 2), y: isTrue(_result), z: pyStrLength("ab")})]))',
    );
    expect(eventLoop.addEvents).toHaveBeenCalledTimes(1);
    expect(eventLoop.addEvents.mock.calls[0][0][0].payload).toEqual({
      x: 1,
      y: true,
      z: 2,
    });
  });

  test("callbacks dispatch through the event loop mounted at call time", async () => {
    const first = vi.fn();
    const second = vi.fn();
    const event = { payload: { callback: "(value) => addEvents([value])" } };
    eventLoop.addEvents = first;
    await callScript("1", event.payload.callback);
    eventLoop.addEvents = second;
    await callScript("2", event.payload.callback);
    expect(first).toHaveBeenCalledWith([1]);
    expect(second).toHaveBeenCalledWith([2]);
  });

  test("the evaluator is compiled on first use, not on import", async () => {
    // A Content Security Policy without unsafe-eval rejects the Function
    // constructor; apps that never send scripts must still load.
    vi.resetModules();
    const RealFunction = globalThis.Function;
    globalThis.Function = function () {
      throw new EvalError("blocked by CSP");
    };
    try {
      await expect(import("$/utils/state")).resolves.toBeTruthy();
    } finally {
      globalThis.Function = RealFunction;
    }
  });

  test("_call_function evaluates a string and calls it", async () => {
    const seen = [];
    await applyEvent(
      {
        name: "_call_function",
        payload: { function: "() => 7", callback: (r) => seen.push(r) },
      },
      null,
      null,
      null,
    );
    expect(seen).toEqual([7]);
  });
});

describe("awaited script results", () => {
  const awaited = (event) => {
    const socket = { emit: vi.fn() };
    return {
      socket,
      applied: applyEvent({ ...event, rid: "r1" }, socket, null, null),
      // The outcome the backend receives, once the script has settled.
      outcome: async () => {
        await vi.waitFor(() => expect(socket.emit).toHaveBeenCalledTimes(1));
        const [name, outcome] = socket.emit.mock.calls[0];
        expect(name).toBe("result");
        return outcome;
      },
    };
  };
  const script = (code) => ({
    name: "_call_script",
    payload: { javascript_code: code, callback: null },
  });
  // The stack trace depends on the run, so it is compared as a placeholder.
  const withoutStack = (outcome) => {
    expect(typeof outcome.error.stack).toBe("string");
    return { ...outcome, error: { ...outcome.error, stack: "<stack>" } };
  };

  test("sends the script's value back as JSON", async () => {
    const { outcome } = awaited(script('({a: [1, 2], b: "x", c: null})'));
    expect(await outcome()).toEqual({
      rid: "r1",
      json: '{"a":[1,2],"b":"x","c":null}',
    });
  });

  test("sends undefined as null", async () => {
    const { outcome } = awaited(script("undefined"));
    expect(await outcome()).toEqual({ rid: "r1", json: "null" });
  });

  test("awaits a promise without holding up the event queue", async () => {
    let resolve;
    globalThis.pendingResult = new Promise((r) => {
      resolve = r;
    });
    try {
      const { socket, applied, outcome } = awaited(
        script("globalThis.pendingResult"),
      );
      // applyEvent returns while the promise is pending, so the queue moves on.
      await applied;
      expect(socket.emit).not.toHaveBeenCalled();
      resolve(5);
      expect(await outcome()).toEqual({ rid: "r1", json: "5" });
    } finally {
      delete globalThis.pendingResult;
    }
  });

  test("calls a _call_function function and sends its value", async () => {
    const { outcome } = awaited({
      name: "_call_function",
      payload: { function: () => [true], callback: null },
    });
    expect(await outcome()).toEqual({ rid: "r1", json: "[true]" });
  });

  test("sends an error the script throws to the backend, not window.onerror", async () => {
    const onerror = vi.fn();
    window.onerror = onerror;
    const { outcome } = awaited(script('throw new RangeError("too far")'));
    expect(withoutStack(await outcome())).toEqual({
      rid: "r1",
      error: { name: "RangeError", message: "too far", stack: "<stack>" },
    });
    expect(onerror).not.toHaveBeenCalled();
  });

  test("sends a rejected promise as an error", async () => {
    const { outcome } = awaited(
      script('Promise.reject(new TypeError("refused"))'),
    );
    expect(withoutStack(await outcome())).toEqual({
      rid: "r1",
      error: { name: "TypeError", message: "refused", stack: "<stack>" },
    });
  });

  test("describes a thrown value that is not an Error", async () => {
    const { outcome } = awaited(script('Promise.reject("nope")'));
    expect(await outcome()).toEqual({
      rid: "r1",
      error: { name: "Error", message: "nope", stack: "" },
    });
  });

  test("describes a thrown value that cannot become a string", async () => {
    // String() throws on an object without a prototype; the backend must
    // still receive an error rather than wait for its timeout.
    const { outcome } = awaited(script("Promise.reject(Object.create(null))"));
    expect(await outcome()).toEqual({
      rid: "r1",
      error: { name: "Error", message: "[object Object]", stack: "" },
    });
  });

  test.each([
    [
      "a DOM node",
      "document.body",
      "TypeError",
      "The script returned a DOM node or window, which JSON cannot carry; return the data you need from it instead.",
    ],
    [
      "a DOM node inside a value",
      "({el: document.body})",
      "TypeError",
      "The script returned a DOM node or window, which JSON cannot carry; return the data you need from it instead.",
    ],
    [
      "the window",
      "window",
      "TypeError",
      "The script returned a DOM node or window, which JSON cannot carry; return the data you need from it instead.",
    ],
    [
      "a function",
      "() => 1",
      "TypeError",
      "The script returned a function, which JSON cannot carry.",
    ],
    ["a BigInt", "1n", "TypeError", "Do not know how to serialize a BigInt"],
  ])("rejects %s as a serialization error", async (_what, code, name, message) => {
    const { outcome } = awaited(script(code));
    expect(withoutStack(await outcome())).toEqual({
      rid: "r1",
      error: { name, message, stack: "<stack>", kind: "serialization" },
    });
  });

  test("a script without a request id still reports errors to window.onerror", async () => {
    const onerror = vi.fn();
    window.onerror = onerror;
    const socket = { emit: vi.fn() };
    await applyEvent(script("throw new Error('boom')"), socket, null, null);
    expect(onerror).toHaveBeenCalledTimes(1);
    expect(socket.emit).not.toHaveBeenCalled();
  });
});
