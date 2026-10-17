import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import { createQueueRuntime } from "./client_event_queue_runtime.mjs";

const source = fs.readFileSync(process.argv[2], "utf8");

// sessionStorage key shared with the auto reload on frontend errors.
const LAST_RELOADED_KEY = "reflex_last_reloaded_on_error";
const BANNER_ID = "reflex-new-version-banner";
const FRONTEND_SCHEMA = "frontend-schema";

/** A DOM element stub: enough for the banner the runtime builds. */
const element = (tag) => ({
  tag,
  children: [],
  style: {},
  attributes: {},
  append(...nodes) {
    this.children.push(...nodes);
  },
  setAttribute(name, value) {
    this.attributes[name] = value;
  },
});

/** Connect the real event handler to an isolated socket and browser storage. */
async function createConnection(
  t,
  dispatch = {},
  { isDevMode = false, lastReload, socketio = false } = {},
) {
  const warn = t.mock.method(console, "warn", () => {});
  const handlers = new Map();
  const sent = [];
  // The kind of each transport the runtime created.
  const created = [];
  const saved = new Map();
  const reloads = [];
  const session = new Map([["token", "test-token"]]);
  if (lastReload !== undefined) {
    session.set(LAST_RELOADED_KEY, String(lastReload));
  }
  const sessionStorage = {
    getItem: (key) => session.get(key) ?? null,
    setItem: (key, value) => session.set(key, String(value)),
  };
  const body = element("body");
  const socket = {
    connected: true,
    io: { opts: {}, encoder: {}, decoder: {} },
    on: (name, handler) => handlers.set(name, handler),
    emit: (name, value) => sent.push({ name, value }),
    connect: () => {
      socket.connected = true;
      handlers.get("connect")();
    },
  };
  const app = {
    initialEvents: (first) => [
      { name: "test.hydrate", payload: first ? { hashes: [] } : {} },
    ],
    stateSchema: FRONTEND_SCHEMA,
    isDevMode,
  };
  const runtime = await createQueueRuntime(source, {
    dependencies: {
      "test:browser": {
        window: {
          location: {
            pathname: "/",
            search: "",
            hash: "",
            reload: () => reloads.push(true),
          },
          sessionStorage,
          addEventListener() {},
          removeEventListener() {},
        },
        document: {
          body,
          addEventListener() {},
          createElement: element,
          getElementById: (id) =>
            body.children.find((node) => node.id === id) ?? null,
        },
        localStorage: { setItem: (key, value) => saved.set(key, value) },
        sessionStorage,
      },
      "$/utils/helpers/websocket": {
        // Called with `new`: a constructor returning an object yields that object.
        ReflexWebSocket: function () {
          created.push("websocket");
          return socket;
        },
        disableChannels() {},
        getChannel() {},
      },
      "socket.io-client": {
        default: () => {
          created.push("socketio");
          return socket;
        },
      },
      "$/env.json": {
        default: { EVENT: "http://backend/_event", SOCKETIO: socketio },
      },
      "$/utils/context-registry": { app, eventLoop: {} },
    },
  });
  const socketRef = { current: null };
  const navigate = () => {};
  const params = { current: {} };
  await runtime.connect(
    socketRef,
    dispatch,
    ["websocket"],
    () => {},
    { local_storage: { "known.value": {}, "unknown.value": {} } },
    navigate,
    params,
  );
  assert.deepEqual(created, [socketio ? "socketio" : "websocket"]);
  return {
    sent,
    saved,
    warn,
    reloads,
    session,
    socket,
    reports: () => sent.filter((event) => event.name === "client_error"),
    receive: (update) => handlers.get("event")(update),
    reconnect: () => handlers.get("connect")(),
    // The runtime's own reconnect, as the disconnect handler calls it.
    reconnectSocket: () => {
      socket.connected = false;
      socketRef.current.reconnect();
    },
    banner: () => body.children.find((node) => node.id === BANNER_ID),
    mismatch: (cooldown = 10000) =>
      handlers.get("state_mismatch")({
        backend: "backend-schema",
        reload_cooldown_ms: cooldown,
      }),
    enqueue: (events) =>
      runtime.queueEvents(events, socketRef, false, navigate, params),
  };
}

/**
 * Register a test once per transport.
 * @param name The test name.
 * @param fn The test body, given a `connect` that opens a connection over the
 *   transport.
 */
const transportTest = (name, fn) => {
  for (const socketio of [false, true]) {
    test(`${name} (${socketio ? "socket.io" : "websocket"})`, (t) =>
      fn((dispatch, options) =>
        createConnection(t, dispatch, { ...options, socketio }),
      ));
  }
};

transportTest(
  "an unknown substate does not block known state or events",
  async (connect) => {
    const applied = [];
    const c = await connect({
      known: (value) => applied.push(value),
    });
    const callback = { name: "test.callback", payload: {} };
    c.receive({
      delta: Object.freeze({ unknown: { value: "u" }, known: { value: "k" } }),
      events: [callback],
    });
    assert.deepEqual(applied, [{ value: "k" }]);
    assert.deepEqual([...c.saved], [["known.value", "k"]]);
    assert.ok(c.sent.some((event) => event.value === callback));
    assert.deepEqual(
      c.reports().map((event) => event.value.substate),
      ["unknown"],
    );
  },
);

transportTest(
  "an unknown substate is reported once per connection",
  async (connect) => {
    const c = await connect();
    const update = { delta: { unknown: {} } };
    c.receive(update);
    c.receive(update);
    assert.equal(c.reports().length, 1);
    await c.reconnect();
    c.receive(update);
    assert.equal(c.reports().length, 2);
  },
);

transportTest(
  "the state schema rides in the connect auth on connect and reconnect",
  async (connect) => {
    const c = await connect();
    assert.equal(c.socket.auth.state_schema, FRONTEND_SCHEMA);
    assert.equal(c.socket.auth.event.name, "test.hydrate");
    assert.deepEqual(c.socket.auth.event.payload.hashes, []);

    c.reconnectSocket();
    assert.equal(c.socket.connected, true);
    assert.equal(c.socket.auth.state_schema, FRONTEND_SCHEMA);
    assert.equal(c.socket.auth.event.payload.hashes, undefined);
  },
);

transportTest(
  "a mismatch in prod reloads once per cooldown, then shows a banner",
  async (connect) => {
    const c = await connect();
    c.mismatch();
    assert.equal(c.reloads.length, 1);
    assert.ok(Date.now() - Number(c.session.get(LAST_RELOADED_KEY)) < 1000);
    assert.equal(c.banner(), undefined);

    // The reload landed on the same skew (a cached bundle, or several backend
    // versions behind one load balancer): no loop, a banner instead.
    c.mismatch();
    c.mismatch();
    assert.equal(c.reloads.length, 1);
    const banner = c.banner();
    assert.ok(banner);
    assert.equal(banner.attributes.role, "alert");
    assert.match(banner.children[0], /new version/i);
    assert.equal(c.warn.mock.callCount(), 2);
    const button = banner.children.find((node) => node.tag === "button");
    assert.equal(button.textContent, "Reload");

    // The button reloads and restarts the cooldown.
    c.session.set(LAST_RELOADED_KEY, "1");
    button.onclick();
    assert.equal(c.reloads.length, 2);
    assert.ok(Date.now() - Number(c.session.get(LAST_RELOADED_KEY)) < 1000);

    // Detection alone does not stop events: the page keeps working as it can.
    await c.enqueue([{ name: "test.event", payload: { id: 1 } }]);
    assert.deepEqual(c.sent.at(-1).value.payload, { id: 1 });
  },
);

transportTest(
  "a reload inside the cooldown window is skipped, outside it is taken",
  async (connect) => {
    const recent = await connect(
      {},
      {
        lastReload: Date.now() - 1000,
      },
    );
    recent.mismatch(10000);
    assert.equal(recent.reloads.length, 0);
    assert.ok(recent.banner());

    const stale = await connect(
      {},
      {
        lastReload: Date.now() - 20000,
      },
    );
    stale.mismatch(10000);
    assert.equal(stale.reloads.length, 1);
    assert.equal(stale.banner(), undefined);
  },
);

transportTest("a mismatch in dev only warns", async (connect) => {
  const c = await connect({}, { isDevMode: true });
  c.mismatch();
  c.mismatch();
  assert.equal(c.warn.mock.callCount(), 2);
  assert.match(c.warn.mock.calls[0].arguments[0], /backend-schema/);
  assert.equal(c.reloads.length, 0);
  assert.equal(c.banner(), undefined);
  assert.equal(c.session.has(LAST_RELOADED_KEY), false);
});
