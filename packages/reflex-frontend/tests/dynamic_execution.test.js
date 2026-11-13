/**
 * Dynamic JavaScript execution via applyEvent and evalReactComponent.
 *
 * Covers _call_script, _call_function, _client_state_get, applyResultCallback,
 * and evalReactComponent — exercising the real state.js implementation under
 * jsdom, the same environment a Reflex app runs in.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const io = vi.hoisted(() =>
  vi.fn(() => ({ io: { opts: {}, open: () => {} } })),
);
vi.mock("socket.io-client", () => ({ default: io }));

const mockEventLoop = vi.hoisted(() => ({
  addEvents: vi.fn(),
  connectErrors: [],
}));
vi.mock("$/utils/context-registry", async (importOriginal) => {
  const original = await importOriginal();
  return { ...original, eventLoop: mockEventLoop };
});

const mockGetClientState = vi.hoisted(() => vi.fn((name) => `stored_${name}`));
vi.mock("$/utils/client_state", async (importOriginal) => {
  const original = await importOriginal();
  return { ...original, getClientState: mockGetClientState };
});

let applyEvent;
let evalReactComponent;
let refs;

beforeEach(async () => {
  vi.resetModules();
  mockEventLoop.addEvents.mockReset();
  mockGetClientState.mockReset().mockImplementation((name) => `stored_${name}`);
  sessionStorage.clear();

  const state = await import("$/utils/state");
  applyEvent = state.applyEvent;
  evalReactComponent = state.evalReactComponent;
  refs = state.refs;
});

afterEach(() => {
  window.onerror = null;
  vi.restoreAllMocks();
});

const makeSocket = () => {
  let _connected = true;
  let _disconnects = 0;
  return {
    get connected() {
      return _connected;
    },
    emit: () => {},
    disconnect() {
      _disconnects++;
      _connected = false;
    },
    get disconnects() {
      return _disconnects;
    },
  };
};

const navigate = () => {};
const params = { current: {} };

/**
 * Install a window.onerror handler and return the collected messages.
 * state.js calls `window.onerror(e.message, ...)` on caught errors.
 */
const captureErrors = () => {
  const errors = [];
  window.onerror = (msg) => errors.push(msg);
  return errors;
};

describe("_call_script completion semantics", () => {
  test("labelled block expression yields the label's value, not an object", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "{ value: 42 }",
          callback: "(res) => addEvents([res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([42]);
  });

  test("function declaration yields undefined completion value", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "function f() {}",
          callback:
            "(res) => addEvents([res === undefined ? 'is_undefined' : res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([
      "is_undefined",
    ]);
  });

  test("normal expression yields its value", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "21 * 2",
          callback: "(res) => addEvents([res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([42]);
  });

  test("multiple statements yield the last expression value", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "let a = 10;\nlet b = 2;\na + b;",
          callback: "(res) => addEvents([res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([12]);
  });

  test("statement without an expression completion yields undefined", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "console.log('executed');",
          callback:
            "(res) => addEvents([res === undefined ? 'is_undefined' : res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([
      "is_undefined",
    ]);
  });

  test("Promise result is awaited before forwarding to callback", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "Promise.resolve(42)",
          callback: "(res) => addEvents([res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([42]);
  });
});

describe("_call_script error handling", () => {
  test("SyntaxError is reported through window.onerror and not executed twice", async () => {
    const errors = captureErrors();
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: { javascript_code: "let let = 1;" },
      },
      socket,
      navigate,
      params,
    );
    expect(errors).toHaveLength(1);
    expect(errors[0]).toBe("Unexpected strict mode reserved word");
  });

  test("runtime errors are caught and reported through window.onerror", async () => {
    const errors = captureErrors();
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: { javascript_code: "throw new Error('script_boom')" },
      },
      socket,
      navigate,
      params,
    );
    expect(errors).toEqual(["script_boom"]);
  });
});

describe("_call_script strict-mode isolation", () => {
  test("assigning to an undeclared variable throws ReferenceError", async () => {
    const errors = captureErrors();
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: { javascript_code: "undeclaredExprVar = 123" },
      },
      socket,
      navigate,
      params,
    );
    expect(errors).toHaveLength(1);
    expect(errors[0]).toBe("undeclaredExprVar is not defined");
    expect("undeclaredExprVar" in globalThis).toBe(false);
  });

  test("undeclared assignment in statement path also throws and does not leak", async () => {
    const errors = captureErrors();
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "let x = 1; undeclaredStmtVar = 456; x;",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(errors).toHaveLength(1);
    expect(errors[0]).toBe("undeclaredStmtVar is not defined");
    expect("undeclaredStmtVar" in globalThis).toBe(false);
  });

  test("top-level this is undefined in expression path", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "this",
          callback:
            "(res) => addEvents([res === undefined ? 'is_undefined' : res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([
      "is_undefined",
    ]);
  });

  test("top-level this is undefined in statement path", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "let y = 1; this;",
          callback:
            "(res) => addEvents([res === undefined ? 'is_undefined' : res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([
      "is_undefined",
    ]);
  });
});

describe("_call_script explicit dependency injection", () => {
  test("callback string can construct and dispatch ReflexEvent", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "'payload_value'",
          callback:
            "(res) => addEvents([ReflexEvent('my_event', { data: res })])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledOnce();
    const dispatched = mockEventLoop.addEvents.mock.calls[0][0][0];
    expect(dispatched.name).toBe("my_event");
    expect(dispatched.payload).toEqual({ data: "payload_value" });
  });

  test("callback strings can use every helper this module exports", async () => {
    // Var operations inside a callback compile to pyMod, isTrue, pyStrLength
    // and other helpers that compiled pages import from state.js.
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "7",
          callback:
            "(res) => addEvents([ReflexEvent('s.set', { x: pyMod(res, 2), y: isTrue(res), z: pyStrLength('ab') })])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledOnce();
    expect(mockEventLoop.addEvents.mock.calls[0][0][0].payload).toEqual({
      x: 1,
      y: true,
      z: 2,
    });
  });

  test("script code can access refs injected into the execution context", async () => {
    refs.__client_state = { current: { value: "hello_client_state" } };
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "refs.__client_state.current.value",
          callback: "(res) => addEvents([res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([
      "hello_client_state",
    ]);

    mockEventLoop.addEvents.mockReset();
    refs.custom_ref = { current: { value: "hello_ref" } };
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "refs.custom_ref.current.value",
          callback: "(res) => addEvents([res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([
      "hello_ref",
    ]);
  });

  test("socket is accessible from script code", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "socket.connected",
          callback: "(res) => addEvents([res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([true]);
  });

  test("script code can call socket.disconnect()", async () => {
    const socket = makeSocket();
    const errors = captureErrors();
    await applyEvent(
      {
        name: "_call_script",
        payload: { javascript_code: "socket.disconnect()" },
      },
      socket,
      navigate,
      params,
    );
    expect(socket.connected).toBe(false);
    expect(socket.disconnects).toBe(1);
    expect(errors).toEqual([]);
  });

  test("callback string can call socket.disconnect()", async () => {
    const socket = makeSocket();
    const errors = captureErrors();
    await applyEvent(
      {
        name: "_call_script",
        payload: {
          javascript_code: "42",
          callback: "(res) => { socket.disconnect(); addEvents([res]); }",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(socket.connected).toBe(false);
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([42]);
    expect(errors).toEqual([]);
  });

  test("navigate and params are not in the execution scope", async () => {
    const errors = captureErrors();
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_function",
        payload: { function: "() => navigate" },
      },
      socket,
      navigate,
      params,
    );
    expect(errors).toHaveLength(1);
    expect(errors[0]).toBe("navigate is not defined");

    await applyEvent(
      {
        name: "_call_script",
        payload: { javascript_code: "params" },
      },
      socket,
      navigate,
      params,
    );
    expect(errors).toHaveLength(2);
    expect(errors[1]).toBe("params is not defined");
  });
});

test("callbacks use late-bound addEvents after eventLoop remounts", async () => {
  const socket = makeSocket();
  await applyEvent(
    {
      name: "_call_script",
      payload: {
        javascript_code: "1",
        callback: "(res) => addEvents([res])",
      },
    },
    socket,
    navigate,
    params,
  );
  expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([1]);

  const remountedCalls = [];
  mockEventLoop.addEvents = vi.fn((events) => remountedCalls.push(events));

  await applyEvent(
    {
      name: "_call_script",
      payload: {
        javascript_code: "2",
        callback: "(res) => addEvents([res])",
      },
    },
    socket,
    navigate,
    params,
  );
  expect(remountedCalls).toEqual([[2]]);
});

test("applyResultCallback awaits a Promise-returning callback", async () => {
  const socket = makeSocket();
  await applyEvent(
    {
      name: "_call_script",
      payload: {
        javascript_code: "99",
        callback:
          "async (res) => { await Promise.resolve(); addEvents([res]); }",
      },
    },
    socket,
    navigate,
    params,
  );
  expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([99]);
});

describe("_call_function", () => {
  test("string function expression is evaluated and its result forwarded", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_function",
        payload: {
          function: "() => 123",
          callback: "(res) => addEvents([res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([123]);
  });

  test("non-string function payload is called directly without eval", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_function",
        payload: {
          function: () => 456,
          callback: "(res) => addEvents([res])",
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([456]);
  });

  test("string function can access addEvents and ReflexEvent", async () => {
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_function",
        payload: {
          function:
            "() => addEvents([ReflexEvent('fn_dispatched', { ok: true })])",
          callback: null,
        },
      },
      socket,
      navigate,
      params,
    );
    expect(mockEventLoop.addEvents).toHaveBeenCalledOnce();
    const dispatched = mockEventLoop.addEvents.mock.calls[0][0][0];
    expect(dispatched.name).toBe("fn_dispatched");
    expect(dispatched.payload).toEqual({ ok: true });
  });

  test("runtime error in string function is caught and reported to window.onerror", async () => {
    const errors = captureErrors();
    const socket = makeSocket();
    await applyEvent(
      {
        name: "_call_function",
        payload: { function: "() => { throw new Error('fn_boom'); }" },
      },
      socket,
      navigate,
      params,
    );
    expect(errors).toEqual(["fn_boom"]);
  });
});

test("_client_state_get retrieves a value and forwards it to the callback", async () => {
  const socket = makeSocket();
  await applyEvent(
    {
      name: "_client_state_get",
      payload: {
        var_name: "my_key",
        callback: "(res) => addEvents([res])",
      },
    },
    socket,
    navigate,
    params,
  );
  expect(mockEventLoop.addEvents).toHaveBeenCalledExactlyOnceWith([
    "stored_my_key",
  ]);
});

test("evalReactComponent imports a component and invokes optional library loading", async () => {
  const loadedLibs = [];
  window.__reflex = { react: { name: "test_react" } };
  window.__reflex_load = async (libs) => {
    loadedLibs.push(...libs);
  };

  const componentSource =
    `//__reflex_evaluate:["lib1", "lib2"]\n` +
    `export default function DynamicWidget() { return "test_widget"; }\n`;

  const component = await evalReactComponent(componentSource);

  expect(loadedLibs).toEqual(["lib1", "lib2"]);
  expect(component()).toBe("test_widget");
  expect(window.React.name).toBe("test_react");

  delete window.__reflex;
  delete window.__reflex_load;
});
