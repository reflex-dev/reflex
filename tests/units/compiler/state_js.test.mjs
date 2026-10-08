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
  transport = "websocket",
  importFails = false,
} = {}) {
  const sockets = [];
  const microtasks = [];
  const timers = new Map();
  const firstHydrates = [];
  const updates = [];
  const window = new EventTarget();
  window.location = new URL("http://localhost:3000/page?query=value");
  const storage = new Map(storedToken ? [["token", storedToken]] : []);
  window.sessionStorage = {
    getItem: (key) => storage.get(key),
    setItem: (key, value) => storage.set(key, value),
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

  /** A transport double shared by the plain WebSocket and socket.io clients. */
  function fakeSocket(kind, opts) {
    const handlers = new Map();
    const socket = {
      kind,
      connected: false,
      opens: 0,
      namespaceConnects: 0,
      disconnects: 0,
      offs: 0,
      io: { opts, encoder: {}, decoder: {} },
      open() {
        this.opens++;
      },
      on(name, handler) {
        handlers.set(name, handler);
      },
      off() {
        this.offs++;
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
  // Called with `new`: a constructor returning an object yields that object.
  function ReflexWebSocket(url, opts) {
    return fakeSocket("websocket", opts);
  }
  const io = (url, opts) => fakeSocket("socketio", opts);
  const imports = {
    "socket.io-client": { default: io },
    "$/utils/helpers/websocket": {
      ReflexWebSocket,
      disableChannels() {},
      getChannel() {},
      parseJsonLenient() {},
      undefinedToNull() {},
    },
    mergician: { mergician() {} },
    "$/env.json": {
      default: { EVENT: "ws://localhost:8000/_event", TRANSPORT: transport },
    },
    "$/reflex.json": { default: { version: "test" } },
    "universal-cookie": { default: class {} },
    react: { useCallback() {}, useEffect() {}, useRef() {}, useState() {} },
    "react-router": {
      useLocation() {},
      useNavigate() {},
      useSearchParams() {},
      useParams() {},
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
  const link = (name) => {
    assert.ok(imports[name], `unexpected import: ${name}`);
    return new vm.SyntheticModule(
      Object.keys(imports[name]),
      function () {
        for (const [key, value] of Object.entries(imports[name]))
          this.setExport(key, value);
      },
      { context },
    );
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
    // The socket.io client is imported on demand.
    async importModuleDynamically(name) {
      if (importFails) {
        // A chunk missing after a redeploy; browsers cache the failure.
        throw new TypeError("Failed to fetch dynamically imported module");
      }
      const imported = link(name);
      await imported.link(() => {});
      await imported.evaluate();
      return imported;
    },
  });
  await module.link(link);
  await module.evaluate();
  const socket = { current: null };
  let connectErrors = [];
  return {
    connectErrors: () => connectErrors,
    sockets,
    timers,
    firstHydrates,
    window,
    socket,
    updates,
    dispose,
    flush: () => microtasks.splice(0).forEach((fn) => fn()),
    connect: (transports = ["websocket"]) =>
      module.namespace.connect(
        socket,
        { child: (delta) => updates.push(delta.count) },
        transports,
        (update) => {
          connectErrors =
            typeof update === "function" ? update(connectErrors) : update;
        },
        {},
        () => {},
        { current: {} },
      ),
  };
}

test("warm the transport without opening a session, then reuse it with every handler attached", async () => {
  const app = await setup();
  app.flush();
  assert.equal(app.sockets.length, 1);
  assert.equal(app.sockets[0].kind, "websocket");
  assert.equal(app.sockets[0].opens, 1);
  assert.equal(app.sockets[0].namespaceConnects, 0);
  assert.deepEqual(app.firstHydrates, []);
  await app.connect();
  assert.equal(app.sockets.length, 1);
  assert.equal(app.socket.current.namespaceConnects, 1);
  assert.deepEqual(app.updates, [7]);
  assert.deepEqual(app.firstHydrates, [true]);
  assert.equal(app.timers.size, 0);
  assert.equal(app.window.sessionStorage.getItem("token"), "assigned-token");
  assert.equal(app.socket.current.auth.event.router_data.pathname, "/page");
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

for (const transport of ["websocket", "socketio"]) {
  test(`reconnect over ${transport} uses the assigned token and requests a full hydrate`, async () => {
    const app = await setup({ transport });
    app.flush();
    await app.connect([transport]);
    app.socket.current.connected = false;
    app.socket.current.reconnect();
    assert.equal(app.sockets.length, 1);
    assert.equal(app.socket.current.io.opts.query.token, "assigned-token");
    assert.deepEqual(app.firstHydrates, [true, false]);
    assert.equal(app.socket.current.auth.event.name, "root.hydrate_and_load");
    assert.equal(app.socket.current.namespaceConnects, 2);
  });
}

for (const reason of ["timeout", "pagehide", "hot reload"]) {
  test(`discard an unclaimed warm transport on ${reason}`, async () => {
    const app = await setup();
    app.flush();
    const warm = app.sockets[0];
    if (reason === "timeout") [...app.timers.keys()][0]();
    if (reason === "pagehide") app.window.dispatchEvent(new Event("pagehide"));
    if (reason === "hot reload") app.dispose();
    assert.equal(warm.disconnects, 1);
    // The transport's offline listener goes with it.
    assert.equal(warm.offs, 1);
    assert.equal(app.timers.size, 0);
    await app.connect();
    assert.equal(app.sockets.length, 2);
    assert.equal(app.socket.current.namespaceConnects, 1);
  });
}

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
  // Reported, not rejected: the unhandled rejection handler adds an event,
  // which reconnects, which would fail again without end.
  await app.connect();
  assert.equal(app.sockets.length, 0);
  assert.match(String(app.connectErrors()[0]), /storage blocked/);
  // A later attempt is not locked out by the failed one.
  app.window.sessionStorage.getItem = () => "original-token";
  await app.connect();
  assert.equal(app.sockets.length, 1);
});

test("a socket.io client that fails to load is a connection error", async () => {
  const app = await setup({ transport: "socketio", importFails: true });
  await app.connect(["socketio"]);
  assert.equal(app.socket.current, null);
  assert.equal(app.connectErrors().length, 1);
  assert.match(String(app.connectErrors()[0]), /dynamically imported module/);
});

for (const [transport, engineTransport] of [
  ["socketio", "websocket"],
  ["polling", "polling"],
]) {
  test(`a caller selecting ${transport} gets a socket.io session carrying the boot event`, async () => {
    const app = await setup();
    app.flush();
    await app.connect([transport]);
    assert.equal(app.sockets[0].disconnects, 1);
    assert.equal(app.socket.current.kind, "socketio");
    assert.equal(app.socket.current.io.opts.autoConnect, false);
    assert.deepEqual(
      [...app.socket.current.io.opts.transports],
      [engineTransport],
    );
    assert.equal(app.socket.current.namespaceConnects, 1);
    assert.deepEqual(app.firstHydrates, [true]);
    assert.equal(app.socket.current.auth.event.router_data.pathname, "/page");
  });
}

for (const config of [
  { browser: false },
  { stateful: false },
  { disabled: true },
  { hidden: true },
  // The socket.io client is only loaded on connect.
  { transport: "socketio" },
]) {
  test(`skip speculative connections for ${JSON.stringify(config)}`, async () => {
    const app = await setup(config);
    app.flush();
    assert.equal(app.sockets.length, 0);
    assert.equal(app.timers.size, 0);
  });
}
