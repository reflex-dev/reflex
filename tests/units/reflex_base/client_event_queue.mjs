import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import { createQueueRuntime } from "./client_event_queue_runtime.mjs";

let targetPath = process.argv[2];
if (
  !fs.existsSync(targetPath) &&
  targetPath.includes(".templates/web/utils/state.js")
) {
  targetPath = targetPath.replace(
    "packages/reflex-base/src/reflex_base/.templates/web/utils/state.js",
    "packages/reflex-frontend/src/utils/state.js",
  );
}
const source = fs.readFileSync(targetPath, "utf8");
const stateful = (id) => ({
  name: "reflex___state.test.event",
  payload: { id },
});
const call = (fn, callback) => ({
  name: "_call_function",
  payload: { function: fn, callback },
});
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
};

/** Bind dispatch arguments while keeping the real queue and handlers intact. */
async function createQueue(connected = true) {
  const output = [];
  const runtime = await createQueueRuntime(source, {
    uploadFiles: () => output.push("upload"),
  });
  const socket = {
    connected,
    emit: (_, event) => output.push(event.payload.id),
  };
  const navigate = (path, options) => output.push([path, options]);
  const params = { current: {} };
  return {
    runtime,
    socket,
    output,
    local: (id) => call(() => output.push(id)),
    enqueue: (events, prepend = false, target = socket) =>
      runtime.queueEvents(events, target, prepend, navigate, params),
    drain: () => runtime.processEvent(socket, navigate, params),
  };
}

/** Create the real addEvents callback with lightweight React hook stubs. */
async function createAddEvents() {
  const output = [];
  const actionKeys = [];
  const runtime = await createQueueRuntime(source, {
    throttle: (key) => {
      actionKeys.push(key);
      return true;
    },
  });
  const [addEvents] = runtime.useEventLoop({});
  return {
    actionKeys,
    addEvents,
    output,
    local: (id) => call(() => output.push(id)),
  };
}

for (const ref of [false, true]) {
  test(
    "FIFO filtering with " + (ref ? "reference" : "raw") + " sockets",
    async () => {
      const q = await createQueue();
      await q.enqueue(
        [null, stateful(1), undefined, q.local(2), stateful(3)],
        false,
        ref ? { current: q.socket } : q.socket,
      );
      assert.deepEqual(q.output, [1, 2, 3]);
      assert.equal(q.runtime.event_queue.length, 0);
      assert.equal(q.runtime.isStateful(), false);
    },
  );
}

test("offline stateful events hold the whole queue until reconnect", async () => {
  const q = await createQueue(false);
  await q.enqueue([q.local(1), stateful(2), q.local(3)]);
  assert.deepEqual(q.output, []);
  assert.equal(q.runtime.event_queue.length, 3);
  assert.equal(q.runtime.isStateful(), true);
  q.socket.connected = true;
  await q.drain();
  assert.deepEqual(q.output, [1, 2, 3]);
  assert.equal(q.runtime.event_queue.length, 0);
});

test("empty and local-only queues work with absent or disconnected sockets", async () => {
  for (const socket of [null, { current: null }, { connected: false }]) {
    const q = await createQueue();
    await q.enqueue([], false, socket);
    await q.enqueue([null, undefined], false, socket);
    await q.enqueue([q.local(1), q.local(2)], false, socket);
    assert.deepEqual(q.output, [1, 2]);
    assert.equal(q.runtime.event_queue.length, 0);
  }
});

test("prepend preserves order, queue identity, and input without extra shifts", async (t) => {
  const q = await createQueue(false);
  const pending = q.runtime.event_queue;
  const shift = (pending.shift = t.mock.fn(pending.shift));
  const existing = [stateful(3), q.local(4)];
  await q.enqueue(existing);
  const incoming = Object.freeze([
    Object.freeze([stateful(1), null]),
    Object.freeze([q.local(2), Object.freeze([undefined])]),
  ]);
  await q.enqueue(incoming, true);
  await q.enqueue([[], [null, [undefined]]], true);
  assert.equal(q.runtime.event_queue, pending);
  assert.deepEqual([...pending], [incoming[0][0], incoming[1][0], ...existing]);
  assert.equal(shift.mock.callCount(), 0);
  q.socket.connected = true;
  await q.drain();
  assert.deepEqual(q.output, [1, 2, 3, 4]);
  assert.equal(shift.mock.callCount(), 4);
  assert.equal(pending.length, 0);
});

for (const prepend of [false, true]) {
  test(
    "connected dispatch skips stateful scans, prepend=" + prepend,
    async (t) => {
      const q = await createQueue();
      const pending = q.runtime.event_queue;
      const scan = (pending.some = t.mock.fn(pending.some));
      for (const event of [q.local, stateful]) {
        await q.enqueue([event(1)], prepend);
        await q.drain();
        assert.equal(q.output.pop(), 1);
        assert.equal(q.output.length, 0);
        const ids = Array.from({ length: 32 }, (_, id) => id);
        await q.enqueue(ids.map(event), prepend);
        assert.deepEqual(q.output.splice(0), ids);
      }
      assert.equal(q.runtime.event_queue.length, 0);
      assert.equal(scan.mock.callCount(), 0);
    },
  );
}

test("disconnect during an event pauses remaining stateful events", async () => {
  const q = await createQueue();
  await q.enqueue([
    call(() => {
      q.output.push(1);
      q.socket.connected = false;
    }),
    q.local(2),
    stateful(3),
  ]);
  assert.deepEqual(q.output, [1]);
  assert.equal(q.runtime.event_queue.length, 2);
  q.socket.connected = true;
  await q.drain();
  assert.deepEqual(q.output, [1, 2, 3]);
});

for (const prepend of [false, true]) {
  test("reentrant dispatch preserves order, prepend=" + prepend, async () => {
    const q = await createQueue();
    let nested;
    await q.enqueue([
      call(() => {
        q.output.push(1);
        nested = q.enqueue([q.local(2)], prepend);
      }),
      q.local(3),
    ]);
    await nested;
    assert.deepEqual(q.output, prepend ? [1, 2, 3] : [1, 3, 2]);
    assert.equal(q.runtime.event_queue.length, 0);
  });
}

test("overlapping calls retain async callback and promise settling order", async () => {
  const q = await createQueue();
  const wait = deferred();
  let settled = false;
  const first = q
    .enqueue([
      call(
        () => {
          q.output.push(1);
          return wait.promise;
        },
        () => q.output.push(4),
      ),
      q.local(2),
    ])
    .then(() => {
      settled = true;
    });
  await q.enqueue([q.local(3)]);
  assert.deepEqual(q.output, [1, 2, 3]);
  await new Promise(setImmediate);
  assert.equal(settled, false);
  wait.resolve();
  await first;
  assert.deepEqual(q.output, [1, 2, 3, 4]);
  assert.equal(settled, true);
});

test("redirect and REST events retain ordering", async () => {
  const q = await createQueue();
  await q.enqueue([
    { name: "_redirect", payload: { path: "/next", replace: true } },
    {
      name: "reflex___state.test.upload",
      handler: "uploadFiles",
      payload: { files: [] },
    },
    q.local("last"),
  ]);
  assert.deepEqual(q.output, [["/next", { replace: true }], "upload", "last"]);
  assert.equal(q.runtime.event_queue.length, 0);
});

test("dispatch rejection does not block pending work", async (t) => {
  const q = await createQueue();
  const emit = t.mock.method(q.socket, "emit", () => {
    throw new Error("socket write failed");
  });
  await assert.rejects(
    q.enqueue([stateful(1), q.local(2)]),
    /socket write failed/,
  );
  assert.deepEqual(q.output, [2]);
  assert.equal(q.runtime.event_queue.length, 0);
  emit.mock.restore();
  await q.enqueue([stateful(3)]);
  assert.deepEqual(q.output, [2, 3]);
  assert.equal(q.runtime.event_queue.length, 0);
});

for (const rejection of [0, null]) {
  test(`falsy dispatch rejection ${rejection} is preserved`, async (t) => {
    const q = await createQueue();
    t.mock.method(q.socket, "emit", () => {
      throw rejection;
    });

    await assert.rejects(q.enqueue([stateful(1), q.local(2)]), (error) =>
      Object.is(error, rejection),
    );
    assert.deepEqual(q.output, [2]);
    assert.equal(q.runtime.event_queue.length, 0);
  });
}

test("addEvents flattens nested event lists before applying actions", async () => {
  const q = await createAddEvents();
  const actions = [];
  const browserEvent = {
    preventDefault: () => actions.push("preventDefault"),
    stopPropagation: () => actions.push("stopPropagation"),
  };
  const first = {
    ...q.local(1),
    event_actions: { preventDefault: true },
  };
  const second = {
    ...q.local(2),
    event_actions: { stopPropagation: true, throttle: 1 },
  };

  const generatedHandler = (event) =>
    q.addEvents(
      [[], [first, [null, second, [undefined]]], q.local(3)],
      [event],
      {},
    );
  await generatedHandler(browserEvent);

  assert.deepEqual(actions, ["preventDefault", "stopPropagation"]);
  assert.deepEqual(q.actionKeys, [
    "_call_function+++_call_function+++_call_function",
  ]);
  assert.deepEqual(q.output, [1, 2, 3]);
});

test("a malformed event does not strand later queued events", async () => {
  const q = await createQueue(false);
  q.socket.emit = (_, event) => {
    if (event.payload?.id !== undefined) q.output.push(event.payload.id);
  };

  q.runtime.event_queue.push({ name: 7 }, q.local(1));
  await q.drain();

  assert.deepEqual(q.output, [1]);
  assert.equal(q.runtime.event_queue.length, 0);
});

test("stateful arrival during an offline local await pauses the later drain", async () => {
  const q = await createQueue(false);
  const wait = deferred();
  const first = q.enqueue([
    call(
      () => wait.promise,
      () => q.output.push(1),
    ),
  ]);
  await q.enqueue([q.local(2), stateful(3)]);
  assert.deepEqual(q.output, []);
  wait.resolve();
  await first;
  assert.deepEqual(q.output, [1]);
  assert.equal(q.runtime.event_queue.length, 2);
  q.socket.connected = true;
  await q.drain();
  assert.deepEqual(q.output, [1, 2, 3]);
  assert.equal(q.runtime.event_queue.length, 0);
});

async function createDynamicExecutionRuntime() {
  const calls = [];
  const errors = [];
  const eventLoop = {
    addEvents: (events) => calls.push(events),
  };
  const window = {
    location: { host: "localhost", pathname: "/", search: "", hash: "" },
    onerror: (msg) => errors.push(msg),
  };
  const runtime = await createQueueRuntime(source, {
    dependencies: {
      "test:browser": {
        window,
        document: {},
        localStorage: { clear() {}, removeItem() {} },
        sessionStorage: { clear() {}, removeItem() {} },
      },
      "$/utils/context-registry": {
        app: {
          initialEvents: () => [],
          initialState: {},
          state_name: "test_state",
          exception_state_name: "test_exception_state",
        },
        eventLoop,
      },
      "$/utils/client_state": {
        CLIENT_STATE_REF: "__client_state",
        getClientState: (name) => `stored_${name}`,
        getClientStore: () => ({}),
        setClientState: () => {},
      },
    },
  });
  let disconnects = 0;

  const socket = {
    connected: true,
    emit: () => {},
    disconnect() {
      disconnects++;
      this.connected = false;
    },
  };
  const navigate = () => {};
  const params = {};
  return {
    runtime,
    window,
    calls,
    errors,
    eventLoop,
    socket,
    navigate,
    params,
    disconnects: () => disconnects,
    apply: (event) => runtime.applyEvent(event, socket, navigate, params),
  };
}

test("_call_script preserves script completion for labelled block expression", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "{ value: 42 }",
      callback: "(res) => addEvents([res])",
    },
  });
  assert.deepEqual(env.calls.pop(), [42]);
});

test("_call_script preserves script completion for function declaration returning undefined", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "function f() {}",
      callback: "(res) => addEvents([res === undefined ? 'is_undefined' : res])",
    },
  });
  assert.deepEqual(env.calls.pop(), ["is_undefined"]);
});

test("_call_script preserves script completion for normal expression", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "21 * 2",
      callback: "(res) => addEvents([res])",
    },
  });
  assert.deepEqual(env.calls.pop(), [42]);
});

test("_call_script preserves script completion for multiple statements", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "let a = 10;\nlet b = 2;\na + b;",
      callback: "(res) => addEvents([res])",
    },
  });
  assert.deepEqual(env.calls.pop(), [12]);
});

test("_call_script preserves script completion for statements without completion value", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "console.log('executed');",
      callback: "(res) => addEvents([res === undefined ? 'is_undefined' : res])",
    },
  });
  assert.deepEqual(env.calls.pop(), ["is_undefined"]);
});

test("_call_script with SyntaxError propagates original error and is not executed twice", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "let let = 1;",
    },
  });
  assert.equal(env.errors.length, 1);
  assert.equal(env.errors[0], "Unexpected strict mode reserved word");
});

test("_call_script handles promise results and forwards to callback", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "Promise.resolve(42)",
      callback: "(res) => addEvents([res])",
    },
  });
  assert.deepEqual(env.calls.pop(), [42]);
});

test("callback string can construct and dispatch ReflexEvent", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "'payload_value'",
      callback: "(res) => addEvents([ReflexEvent('my_event', { data: res })])",
    },
  });
  const dispatched = env.calls.pop()[0];
  assert.equal(dispatched.name, "my_event");
  assert.deepEqual(dispatched.payload, { data: "payload_value" });
});

test("_call_function executes string-based function expression and forwards result", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_function",
    payload: {
      function: "() => 123",
      callback: "(res) => addEvents([res])",
    },
  });
  assert.deepEqual(env.calls.pop(), [123]);
});

test("_call_function executes non-string function payload and forwards result", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_function",
    payload: {
      function: () => 456,
      callback: "(res) => addEvents([res])",
    },
  });
  assert.deepEqual(env.calls.pop(), [456]);
});

test("_call_function string can access addEvents and ReflexEvent", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_function",
    payload: {
      function: "() => addEvents([ReflexEvent('fn_dispatched', { ok: true })])",
      callback: null,
    },
  });
  const dispatched = env.calls.pop()[0];
  assert.equal(dispatched.name, "fn_dispatched");
  assert.deepEqual(dispatched.payload, { ok: true });
});

test("_client_state_get retrieves value and forwards to callback", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_client_state_get",
    payload: {
      var_name: "my_key",
      callback: "(res) => addEvents([res])",
    },
  });
  assert.deepEqual(env.calls.pop(), ["stored_my_key"]);
});

test("applyResultCallback awaits Promise-returning callback", async () => {
  const env = await createDynamicExecutionRuntime();
  let finished = false;
  globalThis.__test_finish = () => {
    finished = true;
  };
  try {
    await env.apply({
      name: "_call_script",
      payload: {
        javascript_code: "99",
        callback:
          "async (res) => { await Promise.resolve(); globalThis.__test_finish(); addEvents([res]); }",
      },
    });
    assert.equal(finished, true);
    assert.deepEqual(env.calls.pop(), [99]);
  } finally {
    delete globalThis.__test_finish;
  }
});

test("callbacks use late-bound addEvents after eventLoop remounts", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "1",
      callback: "(res) => addEvents([res])",
    },
  });
  assert.deepEqual(env.calls.pop(), [1]);
  const remountedCalls = [];
  env.eventLoop.addEvents = (events) => remountedCalls.push(events);
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "2",
      callback: "(res) => addEvents([res])",
    },
  });
  assert.deepEqual(remountedCalls.pop(), [2]);
});

test("dynamic execution can access refs and CLIENT_STATE_REF store", async () => {
  const env = await createDynamicExecutionRuntime();

  const clientStateRef = {
    current: { value: "hello_client_state" },
  };
  env.runtime.refs.__client_state = clientStateRef;

  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "refs.__client_state.current.value",
      callback: "(res) => addEvents([res])",
    },
  });

  assert.deepEqual(env.calls.pop(), ["hello_client_state"]);

  env.runtime.refs.custom_ref = {
    current: { value: "hello_ref" },
  };

  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "refs.custom_ref.current.value",
      callback: "(res) => addEvents([res])",
    },
  });
  assert.deepEqual(env.calls.pop(), ["hello_ref"]);
});

test("dynamic execution only has access to explicitly injected dependencies", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "socket.connected",
      callback: "(res) => addEvents([res])",
    },
  });

  assert.deepEqual(env.calls.pop(), [true]);
  assert.deepEqual(env.errors, []);

  await env.apply({
    name: "_call_function",
    payload: {
      function: "() => navigate",
    },
  });

  assert.equal(env.errors.length, 1);
  assert.equal(env.errors[0], "navigate is not defined");

  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "params",
    },
  });

  assert.equal(env.errors.length, 2);
  assert.equal(env.errors[1], "params is not defined");
});

test("strict mode prevents undeclared assignments and top-level this in expressions", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "undeclaredExprVar = 123",
    },
  });
  assert.equal(env.errors.length, 1);
  assert.equal(env.errors[0], "undeclaredExprVar is not defined");
  assert.equal("undeclaredExprVar" in globalThis, false);

  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "this",
      callback: "(res) => addEvents([res === undefined ? 'is_undefined' : res])",
    },
  });
  assert.deepEqual(env.calls.pop(), ["is_undefined"]);
});

test("strict mode prevents undeclared assignments and top-level this in statements", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "let x = 1; undeclaredStmtVar = 456; x;",
    },
  });
  assert.equal(env.errors.length, 1);
  assert.equal(env.errors[0], "undeclaredStmtVar is not defined");
  assert.equal("undeclaredStmtVar" in globalThis, false);

  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "let y = 1; this;",
      callback: "(res) => addEvents([res === undefined ? 'is_undefined' : res])",
    },
  });
  assert.deepEqual(env.calls.pop(), ["is_undefined"]);
});

test("errors in _call_script and _call_function are caught and reported to window.onerror", async () => {
  const env = await createDynamicExecutionRuntime();
  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "throw new Error('script_boom')",
    },
  });
  assert.equal(env.errors.pop(), "script_boom");

  await env.apply({
    name: "_call_function",
    payload: {
      function: "() => { throw new Error('fn_boom'); }",
    },
  });
  assert.equal(env.errors.pop(), "fn_boom");
});

test("evalReactComponent dynamically imports components and executes optional libraries", async () => {
  const env = await createDynamicExecutionRuntime();
  const loadedLibs = [];
  env.window.__reflex = { react: { name: "test_react" } };
  env.window.__reflex_load = async (libs) => {
    loadedLibs.push(...libs);
  };
  const componentSource = `//__reflex_evaluate:["lib1", "lib2"]
export default function DynamicWidget() { return "test_widget"; }
`;
  const component = await env.runtime.evalReactComponent(componentSource);
  assert.deepEqual(loadedLibs, ["lib1", "lib2"]);
  assert.equal(component(), "test_widget");
  assert.equal(env.window.React.name, "test_react");
});

test("_call_script can disconnect the supplied socket", async () => {
  const env = await createDynamicExecutionRuntime();

  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "socket.disconnect()",
    },
  });

  assert.equal(env.socket.connected, false);
  assert.equal(env.disconnects(), 1);
  assert.deepEqual(env.errors, []);
});

test("result callback can access the supplied socket", async () => {
  const env = await createDynamicExecutionRuntime();

  await env.apply({
    name: "_call_script",
    payload: {
      javascript_code: "42",
      callback: "(res) => { socket.disconnect(); addEvents([res]); }",
    },
  });

  assert.equal(env.socket.connected, false);
  assert.deepEqual(env.calls.pop(), [42]);
  assert.deepEqual(env.errors, []);
});
