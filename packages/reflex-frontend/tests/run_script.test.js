/**
 * Server-provided JavaScript (`_call_script`, `_call_function` and their
 * callbacks) runs through a Function-constructor helper, not a direct eval, so
 * the minifier may mangle this module. These pin what the generated strings
 * can see and what the script returns.
 */
import { encodePayload } from "engine.io-parser";
import { Encoder } from "socket.io-parser";
import { describe, expect, test, vi } from "vitest";

import { getClientState } from "$/utils/client_state";
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

  test("a script dispatches events through the late-bound addEvents", async () => {
    eventLoop.addEvents = vi.fn();
    await callScript('addEvents([ReflexEvent("state.go", {n: 1})], [2], {})');
    expect(eventLoop.addEvents.mock.calls).toEqual([
      [[{ name: "state.go", payload: { n: 1 } }], [2], {}],
    ]);
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

describe("awaited script results", () => {
  // A connected socket whose server limits a frame to maxPayload, with the
  // namespace and packet encoder of the app's.
  const connectedSocket = (
    maxPayload = 1_000_000,
    transport = "websocket",
  ) => ({
    emit: vi.fn(),
    connected: true,
    nsp: "/_event",
    io: {
      encoder: new Encoder(),
      engine: { _maxPayload: maxPayload, transport: { name: transport } },
    },
  });
  const awaited = (event, socket = connectedSocket()) => ({
    socket,
    applied: applyEvent(
      { ...event, payload: { ...event.payload, rid: "r1" } },
      socket,
      null,
      null,
    ),
    // The outcome the backend receives, once the script has settled, with
    // its JSON bytes as text.
    outcome: async () => {
      await vi.waitFor(() => expect(socket.emit).toHaveBeenCalledTimes(1));
      const [name, outcome] = socket.emit.mock.calls[0];
      expect(name).toBe("result");
      return ArrayBuffer.isView(outcome.json)
        ? { ...outcome, json: new TextDecoder().decode(outcome.json) }
        : outcome;
    },
  });
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

  test("sends the JSON as UTF-8 bytes, so its quotes are not escaped again", async () => {
    const { socket, outcome } = awaited(script('["ab", "\\u00e9"]'));
    await outcome();
    const [, sent] = socket.emit.mock.calls[0];
    // TextEncoder's Uint8Array comes from another realm than the test's.
    expect(Object.prototype.toString.call(sent.json)).toBe(
      "[object Uint8Array]",
    );
    expect([...sent.json]).toEqual([
      ...new TextEncoder().encode('["ab","\u00e9"]'),
    ]);
  });

  test.each([
    // A websocket carries the bytes in one binary frame.
    ["websocket", 12, '"1234567890"', null],
    ["websocket", 11, '"1234567890"', 11],
    // Polling carries them base64-encoded behind a one-character marker, in
    // a request body it may share with the message that refers to them.
    ["polling", 90, '"1234567890"', null],
    ["polling", 89, '"1234567890"', 9],
  ])("over %s with a %d frame limit, rejects a result larger than a message can carry", async (transport, maxPayload, json, maxBytes) => {
    const { outcome } = awaited(
      script(json),
      connectedSocket(maxPayload, transport),
    );
    const expected =
      maxBytes === null
        ? { rid: "r1", json }
        : {
            rid: "r1",
            error: {
              name: "RangeError",
              message: `The script returned 12 bytes of JSON, more than the ${maxBytes} a message to the backend can carry; return less data, or raise REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE on the backend.`,
              stack: "<stack>",
              kind: "serialization",
            },
          };
    const sent = await outcome();
    expect(maxBytes === null ? sent : withoutStack(sent)).toEqual(expected);
  });

  test("over polling, a result at the limit fills the request body it shares with its message", async () => {
    const socket = connectedSocket(90, "polling");
    const { outcome } = awaited(script('"1234567890"'), socket);
    await outcome();
    const [name, sent] = socket.emit.mock.calls[0];
    // The body engine.io-client posts when the message and its attachment
    // queue together, as they do while an earlier request is in flight.
    const packets = socket.io.encoder
      .encode({ type: 2, nsp: socket.nsp, data: [name, sent] })
      .map((data) => ({ type: "message", data }));
    const body = await new Promise((resolve) =>
      encodePayload(packets, resolve),
    );
    expect(body).toBe(
      '451-/_event,["result",{"rid":"r1","json":{"_placeholder":true,"num":0}}]\x1ebIjEyMzQ1Njc4OTAi',
    );
    expect(body.length).toBe(90);
  });

  test("measures a result settled while disconnected against the limit of the next connection", async () => {
    const socket = connectedSocket(-1);
    socket.connected = false;
    const handlers = {};
    socket.once = vi.fn((name, handler) => {
      handlers[name] = handler;
    });
    const { outcome } = awaited(script('"1234567890"'), socket);
    await vi.waitFor(() => expect(handlers.connect).toBeDefined());
    expect(socket.emit).not.toHaveBeenCalled();
    socket.io.engine._maxPayload = 11;
    socket.connected = true;
    handlers.connect();
    expect(withoutStack(await outcome()).error.name).toBe("RangeError");
  });

  test("sends data shaped like a DOM node as JSON", async () => {
    const { outcome } = awaited(
      script('({nodeType: 1, nodeName: "DIV", window: {}})'),
    );
    expect(await outcome()).toEqual({
      rid: "r1",
      json: '{"nodeType":1,"nodeName":"DIV","window":{}}',
    });
  });

  test("reads the getters of a result only to serialize it", async () => {
    globalThis.reads = [];
    try {
      const { outcome } = awaited(
        script(
          '({get nodeType() { reads.push("nodeType"); return 1; }, get window() { reads.push("window"); return 2; }})',
        ),
      );
      expect(await outcome()).toEqual({
        rid: "r1",
        json: '{"nodeType":1,"window":2}',
      });
      expect(globalThis.reads).toEqual(["nodeType", "window"]);
    } finally {
      delete globalThis.reads;
    }
  });

  test("runs no Symbol.toStringTag of a result", async () => {
    const { outcome } = awaited(
      script(
        "({count: 0, get [Symbol.toStringTag]() { this.count++; throw new Error('tag read'); }})",
      ),
    );
    expect(await outcome()).toEqual({ rid: "r1", json: '{"count":0}' });
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

  test.each([
    ["a value whose name getter throws", "({ get name() { throw 1; } })"],
    [
      "a revoked Proxy",
      "(() => { const p = Proxy.revocable({}, {}); p.revoke(); return p.proxy; })()",
    ],
    [
      "an Error whose message getter throws",
      "Object.defineProperty(new Error(), 'message', { get() { throw 1; } })",
    ],
    ["an object String() rejects", "Object.create(null)"],
  ])("still answers the backend when it throws %s", async (_what, thrown) => {
    // Reading the thrown value throws; the backend must still get an error
    // rather than wait for its timeout.
    const { outcome } = awaited(script(`Promise.reject(${thrown})`));
    expect(await outcome()).toEqual({
      rid: "r1",
      error: {
        name: "Error",
        message:
          "The script threw a value whose name, message or stack cannot be read.",
        stack: "",
      },
    });
  });

  test.each([
    [
      "a DOM node inside a value",
      "({el: document.body})",
      "The script returned a DOM node or window, which JSON cannot carry; return the data you need from it instead.",
    ],
    [
      "the window",
      "window",
      "The script returned a DOM node or window, which JSON cannot carry; return the data you need from it instead.",
    ],
    // An iframe's nodes and window come from another realm, so they are not
    // instances of this window's Node.
    [
      "a DOM node of an iframe",
      `(() => {
        const frame = document.body.appendChild(document.createElement("iframe"));
        const value = {el: frame.contentDocument.body};
        frame.remove();
        return value;
      })()`,
      "The script returned a DOM node or window, which JSON cannot carry; return the data you need from it instead.",
    ],
    [
      "the window of an iframe",
      `(() => {
        const frame = document.body.appendChild(document.createElement("iframe"));
        // Removed once the result is sent, so the frame is on the page then.
        setTimeout(() => frame.remove());
        return [frame.contentWindow];
      })()`,
      "The script returned a DOM node or window, which JSON cannot carry; return the data you need from it instead.",
    ],
    [
      "a function",
      "() => 1",
      "The script returned a function, which JSON cannot carry; return plain data (objects, arrays, strings, numbers, booleans or null) instead.",
    ],
    ["a BigInt", "1n", "Do not know how to serialize a BigInt"],
  ])("rejects %s as a serialization error", async (_what, code, message) => {
    const { outcome } = awaited(script(code));
    expect(withoutStack(await outcome())).toEqual({
      rid: "r1",
      error: {
        name: "TypeError",
        message,
        stack: "<stack>",
        kind: "serialization",
      },
    });
  });

  test("a script without a request id still reports errors to window.onerror", async () => {
    const onerror = vi.fn();
    window.onerror = onerror;
    const socket = { emit: vi.fn() };
    await applyEvent(script("throw new Error('boom')"), socket, null, null);
    expect(onerror.mock.calls).toEqual([
      ["boom", null, null, null, new Error("boom")],
    ]);
    expect(socket.emit).not.toHaveBeenCalled();
  });
});
