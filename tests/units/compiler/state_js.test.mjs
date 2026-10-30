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

/** Evaluate the actual frontend module with controlled transport and browser APIs. */
async function setup({
  browser = true,
  stateful = true,
  disabled = false,
  hidden = false,
  storedToken = "original-token",
  deferNamespaceConnect = false,
  deferConnectAck = false,
  stateName = "root",
  clientStorage = {},
  dropConnects = 0,
  dropReason = "transport close",
  maxPayload = 1_000_000,
  eventUrl = "ws://localhost:8000/_event",
  firstPayload = {},
  reconnectPayload,
  react = { useCallback() {}, useEffect() {}, useRef() {}, useState() {} },
} = {}) {
  const sockets = [];
  const microtasks = [];
  const timers = new Map();
  const firstHydrates = [];
  const onLoadInternalEvent = `${stateName}.test_on_load_internal`;
  const updates = [];
  const consoleErrors = [];
  let connectErrors = [];
  const errorUpdates = [];
  const window = new EventTarget();
  window.location = new URL("http://localhost:3000/page?query=value");
  const storage = new Map(storedToken ? [["token", storedToken]] : []);
  window.sessionStorage = {
    getItem: (key) => storage.get(key),
    setItem: (key, value) => storage.set(key, value),
  };
  const localStorage = {
    items: new Map(),
    getItem(key) {
      return this.items.get(key) ?? null;
    },
  };
  const document = new EventTarget();
  document.cookie = disabled ? "backend-enabled=false" : "";
  document.visibilityState = hidden ? "hidden" : "visible";
  let dispose;
  const context = vm.createContext({
    console: { ...console, error: (...args) => consoleErrors.push(args) },
    URL,
    TextEncoder,
    URLSearchParams,
    performance,
    localStorage,
    ...(browser ? { window, document } : {}),
    queueMicrotask: (fn) => microtasks.push(fn),
    setTimeout: (fn, ms) => {
      timers.set(fn, ms);
      return fn;
    },
    clearTimeout: (fn) => timers.delete(fn),
  });
  window.setTimeout = context.setTimeout;
  window.clearTimeout = context.clearTimeout;

  function io(url, opts) {
    const handlers = new Map();
    const socket = {
      handlers,
      connected: false,
      namespaceConnects: 0,
      disconnects: 0,
      events: [],
      // Like socket.io-client: the URL path names the namespace.
      nsp: new URL(url).pathname,
      // Engine.IO frames of the CONNECT packets sent to the server.
      frames: [],
      io: {
        opts,
        // The handshake announces the server's limit.
        engine: {
          _maxPayload: maxPayload,
          transport: { name: opts.transports[0] },
        },
        // Like socket.io-parser's Encoder.encodeAsString.
        encoder: {
          encodes: 0,
          encode({ type, nsp, data }) {
            this.encodes++;
            const prefix = nsp && nsp !== "/" ? `${nsp},` : "";
            return [`${type}${prefix}${JSON.stringify(data, this.replacer)}`];
          },
        },
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
        this.finishNamespaceConnect = () => {
          if (typeof this.auth === "function") {
            this.auth((auth) => {
              this.auth = auth;
            });
          }
          // Like Manager._packet: encode the auth callback's resolved payload.
          const frames = this.io.encoder.encode({
            type: 0,
            nsp: this.nsp,
            data: this.auth,
          });
          if (frames.length === 0) {
            return;
          }
          this.frames.push(...frames.map((frame) => `4${frame}`));
          this.namespaceConnects++;
          if (this.namespaceConnects <= dropConnects) {
            // The transport closes before the CONNECT is acknowledged. A
            // transport error reports connect_error before the disconnect.
            if (dropReason === "transport error") {
              handlers.get("connect_error")(new Error("xhr post error"));
            }
            handlers.get("disconnect")(dropReason);
            return;
          }
          this.finishConnectAck = () => {
            this.connected = true;
            const connected = handlers.get("connect")();
            handlers.get("new_token")("assigned-token");
            handlers.get("event")({ delta: { child: { count: 7 } } });
            return connected;
          };
          if (!deferConnectAck) this.finishConnectAck();
        };
        if (!deferNamespaceConnect) this.finishNamespaceConnect();
      },
      emit(name, event) {
        this.events.push({ name, event });
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
      default: { EVENT: eventUrl, TRANSPORT: "websocket" },
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
                  payload: { hashes: ["defaults"], ...firstPayload },
                }
              : reconnectPayload
                ? { name: "root.hydrate_and_load", payload: reconnectPayload }
                : { name: "root.hydrate_and_load" },
          ];
        },
        initialState: stateful ? { root: {}, child: {} } : {},
        onLoadInternalEvent() {},
        on_load_internal_event: onLoadInternalEvent,
        state_name: stateName,
        stateSchema: { version: "test" },
        clientStorage,
        exception_state_name: "exception",
      },
      eventLoop: { addEvents() {}, connectErrors: [] },
    },
    "$/utils/client_state": {
      CLIENT_STATE_REF: "__client_state",
      getClientState: () => undefined,
      // Published on `refs` when the module loads, so it has to answer.
      getClientStore: () => ({}),
      setClientState: () => {},
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
    onLoadInternalEvent,
    window,
    localStorage,
    socket,
    updates,
    consoleErrors,
    get connectErrors() {
      // Like React with pending work, apply queued updaters only on render.
      for (const update of errorUpdates.splice(0)) {
        connectErrors =
          typeof update === "function" ? update(connectErrors) : update;
      }
      return connectErrors;
    },
    module,
    dispose,
    flush: () => microtasks.splice(0).forEach((fn) => fn()),
    connect: (transports = ["websocket"]) =>
      module.namespace.connect(
        socket,
        { child: (delta) => updates.push(delta.count) },
        transports,
        (update) => errorUpdates.push(update),
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
  assert.equal(app.window.sessionStorage.getItem("token"), "assigned-token");
  assert.equal(app.socket.current.auth.event.router_data.pathname, "/page");
  assert.deepEqual(app.socket.current.auth.state_schema, { version: "test" });
});

test("connection auth uses the route current when the namespace connects", async () => {
  const app = await setup({ deferNamespaceConnect: true });
  app.flush();
  await app.connect();
  assert.equal(app.socket.current.namespaceConnects, 0);
  app.window.location = new URL("http://localhost:3000/other?query=value");
  app.socket.current.finishNamespaceConnect();
  assert.equal(app.socket.current.namespaceConnects, 1);
  assert.equal(app.socket.current.auth.event.router_data.pathname, "/other");
  assert.equal(
    app.socket.current.auth.event.router_data.asPath,
    "/other?query=value",
  );
});

test("queued on_load is kept when navigation follows auth capture", async () => {
  const stateName = "reflex___state____root";
  const app = await setup({ deferConnectAck: true, stateName });
  app.flush();
  await app.connect();
  const socket = app.socket.current;
  assert.equal(socket.namespaceConnects, 1);
  assert.equal(socket.auth.event.router_data.asPath, "/page?query=value");

  app.window.location = new URL("http://localhost:3000/other?query=value");
  const onLoadEvent = { name: app.onLoadInternalEvent, payload: {} };
  await app.module.namespace.queueEvents(
    [onLoadEvent],
    app.socket,
    false,
    () => {},
    { current: {} },
  );
  assert.equal(app.module.namespace.isStateful(), true);

  await socket.finishConnectAck();

  assert.deepEqual(JSON.parse(JSON.stringify(socket.events)), [
    {
      name: "event",
      event: {
        ...onLoadEvent,
        router_data: {
          pathname: "/other",
          asPath: "/other?query=value",
          query: { query: "value" },
        },
      },
    },
  ]);
});

test("queued on_loads for a newer route are sent once, after the last storage update", async () => {
  const stateName = "reflex___state____root";
  const app = await setup({ deferConnectAck: true, stateName });
  app.flush();
  await app.connect();
  const socket = app.socket.current;

  // Each navigation queues the browser storage it read, then its on_load.
  app.window.location = new URL("http://localhost:3000/other?query=value");
  const onLoadEvent = { name: app.onLoadInternalEvent, payload: {} };
  const storageEvent = (value) => ({
    name: `${stateName}.update_vars_internal_state.update_vars_internal`,
    payload: { vars: { "root.token": value } },
  });
  await app.module.namespace.queueEvents(
    [storageEvent("first"), { ...onLoadEvent }],
    app.socket,
    false,
    () => {},
    { current: {} },
  );
  await app.module.namespace.queueEvents(
    [storageEvent("second"), { ...onLoadEvent }],
    app.socket,
    false,
    () => {},
    { current: {} },
  );
  await socket.finishConnectAck();

  const router_data = {
    pathname: "/other",
    asPath: "/other?query=value",
    query: { query: "value" },
  };
  assert.deepEqual(JSON.parse(JSON.stringify(socket.events)), [
    { name: "event", event: { ...storageEvent("first"), router_data } },
    { name: "event", event: { ...storageEvent("second"), router_data } },
    { name: "event", event: { ...onLoadEvent, router_data } },
  ]);
});

test("queued on_load is discarded when only the hash changes after auth capture", async () => {
  const stateName = "reflex___state____root";
  const app = await setup({ deferConnectAck: true, stateName });
  app.window.location = new URL("http://localhost:3000/other?query=value#top");
  app.flush();
  await app.connect();
  const socket = app.socket.current;

  app.window.location = new URL("http://localhost:3000/other?query=value");
  const onLoadEvent = { name: app.onLoadInternalEvent, payload: {} };
  await app.module.namespace.queueEvents(
    [onLoadEvent],
    app.socket,
    false,
    () => {},
    { current: {} },
  );
  await socket.finishConnectAck();

  assert.deepEqual(JSON.parse(JSON.stringify(socket.events)), []);
});

test("the size check encodes a CONNECT packet once and leaves other packets alone", async () => {
  const app = await connectWith("websocket", {}, 1_000_000);
  const { encoder } = app.socket.current.io;
  assert.equal(app.socket.current.namespaceConnects, 1);
  assert.equal(encoder.encodes, 1);
  assert.match(app.socket.current.frames[0], /"name":"root.hydrate_and_load"/);

  // An event over the limit is not a hydrate; it is encoded as before.
  const event = {
    type: 2,
    nsp: "/_event",
    data: ["event", "x".repeat(1_000_001)],
  };
  assert.equal(encoder.encode(event).length, 1);
  assert.equal(encoder.encodes, 2);
  assert.equal(app.connectErrors.length, 0);
});

/** Measure a frame like the Engine.IO server: code points per websocket text frame, bytes per polling body. */
const frameSize = (frame, transport) =>
  transport === "websocket"
    ? [...frame].length
    : new TextEncoder().encode(frame).byteLength;

/** Connect an app whose first hydrate carries the payload, with the given server limit. */
async function connectWith(transport, firstPayload, maxPayload, options = {}) {
  const app = await setup({ firstPayload, maxPayload, ...options });
  app.flush();
  await app.connect([transport]);
  return app;
}

for (const transport of ["websocket", "polling"]) {
  test(`the ${transport} size check measures the namespaced frame the server receives`, async () => {
    const payload = {
      vars: { large: "é".repeat(400_001), undefinedValue: undefined },
    };
    const options = { eventUrl: "ws://localhost:8000/api/v1/_event" };
    const probe = await connectWith(
      transport,
      payload,
      Number.MAX_SAFE_INTEGER,
      options,
    );
    const frame = probe.socket.current.frames[0];
    assert.match(frame, /^40\/api\/v1\/_event,\{/);
    assert.match(frame, /"undefinedValue":null/);
    const size = frameSize(frame, transport);

    const fits = await connectWith(transport, payload, size, options);
    assert.equal(fits.socket.current.namespaceConnects, 1);
    assert.deepEqual(fits.socket.current.frames, [frame]);
    assert.equal(fits.connectErrors.length, 0);

    const app = await connectWith(transport, payload, size - 1, options);
    const socket = app.socket.current;
    assert.equal(socket.namespaceConnects, 0);
    assert.deepEqual(socket.frames, []);
    assert.equal(socket.disconnects, 1);
    assert.equal(app.timers.size, 0);
    assert.equal(app.connectErrors.length, 1);
    const [error] = app.connectErrors;
    assert.equal(error.code, "hydration_payload_too_large");
    assert.ok(error.message.includes(`(${size} `));
    assert.ok(error.message.includes(`(${size - 1} `));
    assert.match(
      error.message,
      transport === "websocket" ? /characters/ : /bytes/,
    );
    assert.match(error.message, /browser storage/i);
    assert.deepEqual(app.consoleErrors, [[error.message]]);
  });
}

test("the size limit comes from the server handshake, not the frontend build", async () => {
  const payload = { vars: { large: "x".repeat(1_200_000) } };
  const raised = await connectWith("websocket", payload, 2_000_000);
  assert.equal(raised.socket.current.namespaceConnects, 1);
  assert.equal(raised.connectErrors.length, 0);

  const lowered = await connectWith("websocket", payload, 1_000_000);
  assert.equal(lowered.socket.current.namespaceConnects, 0);
  assert.equal(lowered.connectErrors.length, 1);
});

test("websocket limits count code points, polling limits count UTF-8 bytes", async () => {
  // 600,000 code points: 1.2M UTF-16 units and 2.4M UTF-8 bytes.
  const payload = {
    vars: { large: String.fromCodePoint(0x1f600).repeat(600_000) },
  };
  const websocket = await connectWith("websocket", payload, 1_000_000);
  assert.equal(websocket.socket.current.namespaceConnects, 1);
  assert.equal(websocket.connectErrors.length, 0);

  const polling = await connectWith("polling", payload, 1_000_000);
  assert.equal(polling.socket.current.namespaceConnects, 0);
  assert.match(polling.connectErrors[0].message, /bytes/);
});

test("an oversized first hydrate is reported once and not rebuilt per event", async () => {
  const app = await connectWith(
    "websocket",
    { vars: { large: "x".repeat(1_000_001) } },
    1_000_000,
  );
  const socket = app.socket.current;
  // Later events reconnect through connect(), and a visible tab directly.
  await app.connect();
  socket.reconnect();

  assert.deepEqual(app.firstHydrates, [true]);
  assert.equal(socket.namespaceConnects, 0);
  assert.equal(app.timers.size, 0);
  assert.equal(app.connectErrors.length, 1);
  assert.equal(app.consoleErrors.length, 1);
});

test("an oversized full hydrate on reconnect is reported, not retried", async () => {
  const app = await setup({
    reconnectPayload: { vars: { large: "x".repeat(1_000_001) } },
  });
  app.flush();
  await app.connect();
  const socket = app.socket.current;
  socket.connected = false;
  socket.handlers.get("disconnect")("transport close");
  socket.reconnect();

  assert.equal(socket.namespaceConnects, 1);
  assert.deepEqual(app.firstHydrates, [true, false]);
  assert.equal(app.timers.size, 0);
  assert.equal(app.connectErrors.length, 1);
  assert.match(app.connectErrors[0].message, /exceeds/);
});

test("a new session's token is saved only once the mounted app connects", async () => {
  const app = await setup({ storedToken: null });
  app.flush();
  const warm = app.sockets[0];
  const token = warm.io.opts.query.token;
  assert.ok(token);
  // Waiting for the token in session storage must mean the app has mounted.
  assert.equal(app.window.sessionStorage.getItem("token"), undefined);
  const saved = [];
  const setItem = app.window.sessionStorage.setItem;
  app.window.sessionStorage.setItem = (key, value) => {
    saved.push(value);
    setItem(key, value);
  };
  await app.connect();
  assert.equal(app.socket.current, warm);
  assert.deepEqual(saved, [token, "assigned-token"]);
});

test("a warm transport carrying another session's token is replaced", async () => {
  const app = await setup();
  app.flush();
  const warm = app.sockets[0];
  app.window.sessionStorage.setItem("token", "replaced-token");
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

test("a transport closed before the namespace connects backs off with an error", async () => {
  const app = await setup({ dropConnects: Infinity });
  app.flush();
  await app.connect();
  const socket = app.socket.current;
  assert.equal(socket.namespaceConnects, 1);
  assert.equal(app.connectErrors.length, 1);
  assert.deepEqual([...app.timers.values()], [200]);

  const [retry] = app.timers.keys();
  app.timers.clear();
  retry();
  assert.equal(socket.namespaceConnects, 2);
  assert.equal(app.connectErrors.length, 2);
  assert.deepEqual([...app.timers.values()], [400]);
});

test("a transport error before the namespace connects retries once with backoff", async () => {
  const app = await setup({ dropConnects: 2, dropReason: "transport error" });
  app.flush();
  await app.connect();
  const socket = app.socket.current;
  assert.equal(socket.namespaceConnects, 1);
  assert.equal(app.connectErrors.length, 1);
  assert.deepEqual([...app.timers.values()], [200]);

  const [retry] = app.timers.keys();
  app.timers.clear();
  retry();
  assert.equal(socket.namespaceConnects, 2);
  assert.deepEqual([...app.timers.values()], [400]);
});

test("a connect cancels the pending retry", async () => {
  const app = await setup({ dropConnects: 1 });
  app.flush();
  await app.connect();
  const socket = app.socket.current;
  assert.equal(app.timers.size, 1);

  // Another path, such as the page becoming visible, reconnects first.
  socket.reconnect();
  assert.equal(socket.connected, true);
  assert.equal(app.timers.size, 0);

  socket.connected = false;
  socket.handlers.get("disconnect")("io server disconnect");
  assert.equal(socket.namespaceConnects, 2);
  assert.equal(app.timers.size, 0);
});

test("a dropped connection reconnects at once", async () => {
  const app = await setup();
  app.flush();
  await app.connect();
  const socket = app.socket.current;
  socket.connected = false;
  socket.handlers.get("disconnect")("transport close");
  assert.equal(socket.namespaceConnects, 2);
  assert.equal(app.connectErrors.length, 0);
  assert.equal(app.timers.size, 0);
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
async function mountEventLoop(clientStorage = {}) {
  const effects = [];
  const sent = [];
  const emitted = {
    connected: true,
    emit: (name, payload) => sent.push(payload),
  };
  let refs = 0;
  const harness = await setup({
    clientStorage,
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
    clientStorage,
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

test("a storage event syncs every synced var that shares the storage name", async () => {
  const clientStorage = {
    local_storage: {
      first: { name: "shared", sync: true },
      second: { name: "shared", sync: true },
      other: { name: "other", sync: true },
      unsynced: { name: "shared" },
    },
  };
  const { harness, effects, sent } = await mountEventLoop(clientStorage);
  for (const effect of effects) effect();
  harness.localStorage.items.set("shared", "stored");

  const event = new Event("storage");
  event.key = "shared";
  event.storageArea = harness.localStorage;
  harness.window.dispatchEvent(event);
  await new Promise((resolve) => setImmediate(resolve));

  const updates = sent.filter((e) => e.name.endsWith("update_vars_internal"));
  assert.equal(updates.length, 1, JSON.stringify(sent));
  // The vars come from the vm's realm, so compare their serialised form.
  assert.equal(
    JSON.stringify(updates[0].payload.vars),
    JSON.stringify({ first: "stored", second: "stored" }),
  );
});

test("storage names that are Object.prototype properties sync like any other", async () => {
  const clientStorage = {
    local_storage: {
      first: { name: "constructor", sync: true },
      second: { name: "constructor", sync: true },
      third: { name: "__proto__", sync: true },
    },
  };
  const { harness, effects, sent } = await mountEventLoop(clientStorage);
  assert.doesNotThrow(() => {
    for (const effect of effects) effect();
  });
  harness.localStorage.items.set("constructor", "stored");

  for (const key of ["constructor", "toString", "__proto__"]) {
    const event = new Event("storage");
    event.key = key;
    event.storageArea = harness.localStorage;
    harness.window.dispatchEvent(event);
  }
  await new Promise((resolve) => setImmediate(resolve));

  // Only the names a var declared are synced, and a name's vars all are.
  const updates = sent.filter((e) => e.name.endsWith("update_vars_internal"));
  assert.equal(updates.length, 2, JSON.stringify(sent));
  assert.equal(
    JSON.stringify(updates[0].payload.vars),
    JSON.stringify({ first: "stored", second: "stored" }),
  );
  assert.equal(
    JSON.stringify(updates[1].payload.vars),
    JSON.stringify({ third: null }),
  );
});
