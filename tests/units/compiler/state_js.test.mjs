import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(
  new URL(
    "../../../packages/reflex-base/src/reflex_base/.templates/web/utils/state.js",
    import.meta.url,
  ),
  "utf8",
);
const tokenKey = "reflex:ws://localhost:8000/_event:token";

/** Evaluate the actual frontend module with controlled transport and browser APIs. */
async function setup({
  browser = true,
  stateful = true,
  disabled = false,
  hidden = false,
  storedToken = "original-token",
  react = { useCallback() {}, useEffect() {}, useRef() {}, useState() {} },
} = {}) {
  const sockets = [];
  const microtasks = [];
  const timers = new Map();
  const firstHydrates = [];
  const updates = [];
  const window = new EventTarget();
  window.location = new URL("http://localhost:3000/page?query=value");
  const storage = new Map(storedToken ? [[tokenKey, storedToken]] : []);
  window.sessionStorage = {
    getItem: (key) => storage.get(key),
    setItem: (key, value) => storage.set(key, value),
  };
  window.localStorage = {
    getItem: () => (storedToken ? String(Date.now() + 3600000) : undefined),
  };
  const document = new EventTarget();
  document.cookie = disabled ? "backend-enabled=false" : "";
  document.visibilityState = hidden ? "hidden" : "visible";
  let dispose;
  const context = vm.createContext({
    console,
    URL,
    URLSearchParams,
    performance,
    ...(browser ? { window, document } : {}),
    queueMicrotask: (fn) => microtasks.push(fn),
    setTimeout: (fn, ms) => {
      timers.set(fn, ms);
      return fn;
    },
    clearTimeout: (fn) => timers.delete(fn),
  });
  window.setTimeout = context.setTimeout;

  function io(url, opts) {
    const handlers = new Map();
    const socket = {
      connected: false,
      namespaceConnects: 0,
      disconnects: 0,
      io: {
        opts,
        encoder: {},
        decoder: {},
        opens: 0,
        open(callback) {
          this.opens++;
          this.openCallback = callback;
        },
      },
      on(name, handler) {
        handlers.set(name, handler);
      },
      connect() {
        // A ready transport can deliver these synchronously on namespace connect.
        for (const name of [
          "connect",
          "connect_error",
          "event",
          "new_token",
          "disconnect",
        ]) {
          assert.ok(handlers.has(name), `missing handler: ${name}`);
        }
        this.namespaceConnects++;
        this.connected = true;
        handlers.get("connect")();
        handlers.get("new_token")("assigned-token");
        handlers.get("event")({ delta: { child: { count: 7 } } });
      },
      disconnect() {
        this.disconnects++;
        this.connected = false;
      },
    };
    sockets.push(socket);
    return socket;
  }
  const imports = {
    "socket.io-client": { default: io },
    mergician: { mergician() {} },
    "$/env.json": {
      default: { EVENT: "ws://localhost:8000/_event", TRANSPORT: "websocket" },
    },
    "$/reflex.json": { default: { version: "test" } },
    "universal-cookie": { default: class {} },
    react,
    "react-router": {
      useLocation: () => ({ pathname: "/", search: "", hash: "" }),
      useNavigate: () => () => {},
      useSearchParams: () => [new URLSearchParams()],
      useParams: () => ({}),
    },
    "$/utils/context-registry": {
      app: {
        initialEvents(first) {
          firstHydrates.push(first);
          // Like ReflexEvent, a later hydrate without stored values has no payload.
          return [
            first
              ? {
                  name: "root.hydrate_and_load",
                  payload: { hashes: ["defaults"] },
                }
              : { name: "root.hydrate_and_load" },
          ];
        },
        initialState: stateful ? { root: {}, child: {} } : {},
        onLoadInternalEvent() {},
        state_name: "root",
        exception_state_name: "exception",
      },
      eventLoop: { addEvents() {}, connectErrors: [] },
    },
    "$/utils/helpers/json": { parseJson: JSON.parse },
    "$/utils/helpers/debounce": { default() {} },
    "$/utils/helpers/throttle": { default() {} },
    "$/utils/helpers/upload": { uploadFiles() {} },
  };
  const module = new vm.SourceTextModule(source, {
    context,
    initializeImportMeta(meta) {
      meta.hot = {
        dispose(fn) {
          dispose = fn;
        },
      };
    },
  });
  await module.link((name) => {
    assert.ok(imports[name], `unexpected import: ${name}`);
    return new vm.SyntheticModule(
      Object.keys(imports[name]),
      function () {
        for (const [key, value] of Object.entries(imports[name]))
          this.setExport(key, value);
      },
      { context },
    );
  });
  await module.evaluate();
  const socket = { current: null };
  return {
    sockets,
    timers,
    firstHydrates,
    window,
    socket,
    updates,
    module,
    dispose,
    flush: () => microtasks.splice(0).forEach((fn) => fn()),
    connect: (transports = ["websocket"]) =>
      module.namespace.connect(
        socket,
        { child: (delta) => updates.push(delta.count) },
        transports,
        () => {},
        {},
        () => {},
        { current: {} },
      ),
  };
}

test("warm the transport without hydrating, then reuse it with every handler attached", async () => {
  const app = await setup();
  app.flush();
  assert.equal(app.sockets.length, 1);
  assert.equal(app.sockets[0].io.opens, 1);
  assert.equal(app.sockets[0].namespaceConnects, 0);
  assert.equal(app.sockets[0].io.opts.autoConnect, false);
  assert.deepEqual(app.firstHydrates, []);
  await app.connect();
  assert.equal(app.sockets.length, 1);
  assert.equal(app.socket.current.namespaceConnects, 1);
  assert.deepEqual(app.updates, [7]);
  assert.deepEqual(app.firstHydrates, [true]);
  assert.equal(app.timers.size, 0);
  assert.equal(app.window.sessionStorage.getItem(tokenKey), "assigned-token");
  assert.equal(app.socket.current.auth.event.router_data.pathname, "/page");
});

test("a cold session stores only the token assigned by the server", async () => {
  const app = await setup({ storedToken: null });
  app.flush();
  assert.equal(app.sockets.length, 0);
  assert.equal(app.window.sessionStorage.getItem(tokenKey), undefined);
  const saved = [];
  const setItem = app.window.sessionStorage.setItem;
  app.window.sessionStorage.setItem = (key, value) => {
    saved.push(value);
    setItem(key, value);
  };
  await app.connect();
  assert.equal(app.socket.current.io.opts.query.token, "");
  assert.deepEqual(saved, ["assigned-token"]);
});

test("a warm transport carrying another session's token is replaced", async () => {
  const app = await setup();
  app.flush();
  const warm = app.sockets[0];
  app.window.sessionStorage.setItem(tokenKey, "replaced-token");
  await app.connect();
  assert.equal(warm.disconnects, 1);
  assert.equal(app.sockets.length, 2);
  assert.equal(app.socket.current.io.opts.query.token, "replaced-token");
});

test("reconnect uses the assigned token and requests a full hydrate", async () => {
  const app = await setup();
  app.flush();
  await app.connect();
  app.socket.current.connected = false;
  app.socket.current.reconnect();
  assert.equal(app.sockets.length, 1);
  assert.equal(app.socket.current.io.opts.query.token, "assigned-token");
  assert.deepEqual(app.firstHydrates, [true, false]);
  assert.equal(app.socket.current.namespaceConnects, 2);
});

for (const reason of ["error", "timeout", "pagehide", "hot reload"]) {
  test(`discard an unclaimed warm transport on ${reason}`, async () => {
    const app = await setup();
    app.flush();
    const warm = app.sockets[0];
    if (reason === "error") warm.io.openCallback(new Error("offline"));
    if (reason === "timeout") [...app.timers.keys()][0]();
    if (reason === "pagehide") app.window.dispatchEvent(new Event("pagehide"));
    if (reason === "hot reload") app.dispose();
    assert.equal(warm.disconnects, 1);
    assert.equal(app.timers.size, 0);
    await app.connect();
    assert.equal(app.sockets.length, 2);
    assert.equal(app.socket.current.namespaceConnects, 1);
  });
}

test("a late warmup error cannot close the socket after React claims it", async () => {
  const app = await setup();
  app.flush();
  await app.connect();
  app.socket.current.io.openCallback(new Error("late failure"));
  assert.equal(app.socket.current.disconnects, 0);
});

test("a synchronous mount does not leave a second speculative connection", async () => {
  const app = await setup();
  await app.connect();
  app.flush();
  assert.equal(app.sockets.length, 1);
});

test("hot reload before the microtask runs prevents speculative setup", async () => {
  const app = await setup();
  app.dispose();
  app.flush();
  assert.equal(app.sockets.length, 0);
});

test("blocked session storage does not throw from speculative setup", async () => {
  const app = await setup();
  app.window.sessionStorage.getItem = () => {
    throw new Error("storage blocked");
  };
  app.flush();
  assert.equal(app.sockets.length, 0);
  await assert.rejects(app.connect(), /storage blocked/);
});

test("a caller selecting another transport gets its requested configuration", async () => {
  const app = await setup();
  app.flush();
  await app.connect(["polling"]);
  assert.equal(app.sockets[0].disconnects, 1);
  assert.equal(app.socket.current.io.opts.transports[0], "polling");
});

for (const config of [
  { browser: false },
  { stateful: false },
  { disabled: true },
  { hidden: true },
]) {
  test(`skip speculative connections for ${JSON.stringify(config)}`, async () => {
    const app = await setup(config);
    app.flush();
    assert.equal(app.sockets.length, 0);
    assert.equal(app.timers.size, 0);
  });
}

/** Run `useEventLoop` once with minimal hooks, keeping the effects it registers. */
async function mountEventLoop() {
  const effects = [];
  const sent = [];
  const emitted = {
    connected: true,
    emit: (name, payload) => sent.push(payload),
  };
  let refs = 0;
  const harness = await setup({
    react: {
      useCallback: (fn) => fn,
      useEffect: (fn) => effects.push(fn),
      // The first ref is the socket; hand it a connected stand-in.
      useRef: (initial) => ({ current: refs++ === 0 ? emitted : initial }),
      useState: (initial) => [initial, () => {}],
    },
  });
  harness.module.namespace.useEventLoop(
    () => {},
    () => [],
    {},
  );
  return { harness, effects, sent };
}

test("window.onerror reports an error event that carries no Error object", async () => {
  const { harness, effects, sent } = await mountEventLoop();
  // Only the frontend-error effect touches `window.onerror`.
  for (const effect of effects) effect();
  assert.equal(typeof harness.window.onerror, "function");

  // The benign ResizeObserver notification: a message, but `error` is null.
  const message =
    "ResizeObserver loop completed with undelivered notifications.";
  assert.doesNotThrow(() =>
    harness.window.onerror(
      message,
      "http://localhost:3000/app.js",
      12,
      34,
      null,
    ),
  );
  await new Promise((resolve) => setImmediate(resolve));

  const event = sent.find(
    (e) => e.name === "exception.handle_frontend_exception",
  );
  assert.ok(
    event,
    `expected a frontend exception event, got ${JSON.stringify(sent)}`,
  );
  assert.equal(
    event.payload.info,
    message + "\n    at http://localhost:3000/app.js:12:34",
  );
  assert.equal(event.payload.component_stack, "");
});

test("window.onerror preserves the original Error message", async () => {
  const { harness, effects, sent } = await mountEventLoop();
  for (const effect of effects) effect();
  const error = new TypeError("same old message");
  error.stack = "TypeError: same old message\n    at app.js:1:2";
  assert.equal(
    harness.window.onerror("ignored", "ignored.js", 9, 8, error),
    false,
  );
  await new Promise((resolve) => setImmediate(resolve));
  const event = sent.find(
    (e) => e.name === "exception.handle_frontend_exception",
  );
  assert.ok(event);
  assert.equal(
    event.payload.info,
    error.name + ": " + error.message + "\n" + error.stack,
  );
  assert.equal(event.payload.component_stack, "");
});
