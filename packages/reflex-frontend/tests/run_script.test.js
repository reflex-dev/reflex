/**
 * Server-provided JavaScript (`_call_script`, `_call_function` and their
 * callbacks) runs through a Function-constructor helper, not a direct eval, so
 * the minifier may mangle this module. These pin what the generated strings
 * can see and what the script returns.
 */
import { describe, expect, test, vi } from "vitest";

import { eventLoop } from "$/utils/context-registry";
import { applyEvent } from "$/utils/state";

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
    const seen = [];
    await callScript(
      "socket.disconnect(); [typeof navigate, typeof params, typeof token]",
      (result) => seen.push(result),
      socket,
    );
    expect(socket.disconnect).toHaveBeenCalledTimes(1);
    expect(seen).toEqual([["object", "object", "undefined"]]);
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
