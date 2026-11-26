/**
 * Server-provided JavaScript (`_call_script`, `_call_function` and their
 * callbacks) runs through a Function-constructor helper, not a direct eval, so
 * the minifier may mangle this module. These pin what the generated strings
 * can see and what the script returns.
 */
import { describe, expect, test, vi } from "vitest";

import { getClientState } from "$/utils/client_state";
import { eventLoop, registerApp } from "$/utils/context-registry";
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

  test("scripts read and write named client state", async () => {
    // ClientStateVar.global_value and global_set compile to these calls, and
    // so does a Var pushed from the backend, which arrives as a script.
    const onerror = vi.fn();
    window.onerror = onerror;
    const seen = [];
    await callScript(
      'setClientState("script_count", 1); setClientState("script_count", (v) => v + 1); getClientState("script_count")',
      (result) => seen.push(result),
    );
    expect(onerror).not.toHaveBeenCalled();
    expect(seen).toEqual([2]);
    expect(getClientState("script_count")).toBe(2);
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

describe("events the transport applies before the frontend ones", () => {
  test("a download of an uploaded file resolves the backend upload URL", async () => {
    const hrefs = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      function () {
        hrefs.push([this.href, this.download]);
      },
    );
    await applyEvent(
      {
        name: "_download",
        payload: {
          url: 'getBackendURL(env.UPLOAD) + "/a.png"',
          filename: "a.png",
        },
      },
      null,
      null,
      null,
    );
    expect(hrefs).toEqual([["http://localhost:8000/_upload/a.png", "a.png"]]);
  });

  test("clearing local storage hydrates again when connected", async () => {
    localStorage.setItem("kept", "1");
    const socket = { connected: true, emit: vi.fn() };
    registerApp({
      initialEvents: () => [{ name: "state.hydrate_and_load" }],
      clientStorage: {},
      state_name: "state",
    });
    await applyEvent({ name: "_clear_local_storage" }, socket, null, {
      current: {},
    });
    expect(localStorage.getItem("kept")).toBeNull();
    await vi.waitFor(() =>
      expect(socket.emit).toHaveBeenCalledWith(
        "event",
        expect.objectContaining({ name: "state.hydrate_and_load" }),
      ),
    );
  });
});
