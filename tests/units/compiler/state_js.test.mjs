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
} = {}) {
  const sockets = [];
  const microtasks = [];
  const timers = new Map();
  const firstHydrates = [];
  const updates = [];
  const window = new EventTarget();
  window.location = new URL("http://localhost:3000/page?query=value");
  const storage = new Map([["token", "original-token"]]);
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
    "$/env.json": {
      default: { EVENT: "ws://localhost:8000/_event", TRANSPORT: "websocket" },
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
    "$/utils/context": {
      initialEvents(first) {
        firstHydrates.push(first);
        return [
          {
            name: "root.hydrate_and_load",
            payload: first ? { hashes: ["defaults"] } : {},
          },
        ];
      },
      initialState: stateful ? { root: {}, child: {} } : {},
      onLoadInternalEvent() {},
      state_name: "root",
      exception_state_name: "exception",
    },
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
  assert.equal(app.window.sessionStorage.getItem("token"), "assigned-token");
  assert.equal(app.socket.current.auth.event.router_data.pathname, "/page");
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
