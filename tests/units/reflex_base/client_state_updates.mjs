import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import { createQueueRuntime } from "./client_event_queue_runtime.mjs";

const source = fs.readFileSync(process.argv[2], "utf8");

// sessionStorage key shared with the auto reload on frontend errors.
const LAST_RELOADED_KEY = "reflex_last_reloaded_on_error";
const BANNER_ID = "reflex-new-version-banner";
const MISMATCH_EVENT = "reflex:state-mismatch";
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
  { isDevMode = false, lastReload } = {},
) {
  const warn = t.mock.method(console, "warn", () => {});
  const handlers = new Map();
  const sent = [];
  const saved = new Map();
  const reloads = [];
  const session = new Map([["token", "test-token"]]);
  const windowEvents = new EventTarget();
  if (lastReload !== undefined) {
    session.set(LAST_RELOADED_KEY, String(lastReload));
  }
  const sessionStorage = {
    getItem: (key) => session.get(key) ?? null,
    setItem: (key, value) => session.set(key, String(value)),
  };
  const body = element("body");
  let authPayload;
  const socket = {
    connected: true,
    io: {
      opts: {},
      encoder: { encode: (packet) => [JSON.stringify(packet)] },
      decoder: {},
    },
    on: (name, handler) => handlers.set(name, handler),
    emit: (name, value) => sent.push({ name, value }),
    connect: () => {
      if (typeof socket.auth === "function") {
        socket.auth((auth) => {
          authPayload = auth;
        });
      } else {
        authPayload = socket.auth;
      }
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
          clearTimeout,
          location: {
            pathname: "/",
            search: "",
            hash: "",
            reload: () => reloads.push(true),
          },
          sessionStorage,
          addEventListener() {},
          removeEventListener() {},
          dispatchEvent: (event) => windowEvents.dispatchEvent(event),
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
      "socket.io-client": { default: () => socket },
      "$/env.json": { default: { EVENT: "http://backend/_event" } },
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
  return {
    sent,
    saved,
    warn,
    reloads,
    session,
    socket,
    authPayload: () => authPayload,
    readAuth: () => socket.auth((auth) => (authPayload = auth)),
    reports: () => sent.filter((event) => event.name === "client_error"),
    receive: (update) => handlers.get("event")(update),
    reconnect: () => handlers.get("connect")(),
    // The runtime's own reconnect, as the disconnect handler calls it.
    reconnectSocket: () => {
      socket.connected = false;
      socketRef.current.reconnect();
    },
    windowEvents,
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

test("an unknown substate does not block known state or events", async (t) => {
  const applied = [];
  const c = await createConnection(t, {
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
});

test("an unknown substate is reported once per connection", async (t) => {
  const c = await createConnection(t);
  const update = { delta: { unknown: {} } };
  c.receive(update);
  c.receive(update);
  assert.equal(c.reports().length, 1);
  await c.reconnect();
  c.receive(update);
  assert.equal(c.reports().length, 2);
});

test("the state schema rides in the CONNECT auth on connect and reconnect", async (t) => {
  const c = await createConnection(t);
  c.readAuth();
  assert.equal(c.authPayload().state_schema, FRONTEND_SCHEMA);
  assert.equal(c.authPayload().event.name, "test.hydrate");
  assert.deepEqual(c.authPayload().event.payload.hashes, []);

  c.reconnectSocket();
  assert.equal(c.socket.connected, true);
  assert.equal(c.authPayload().state_schema, FRONTEND_SCHEMA);
  assert.equal(c.authPayload().event.payload.hashes, undefined);
});

test("a mismatch in prod reloads once per cooldown, then shows a banner", async (t) => {
  const c = await createConnection(t);
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
  // Every mismatch warns once, the one that reloaded included.
  assert.equal(c.warn.mock.callCount(), 3);
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
});

test("a reload inside the cooldown window is skipped, outside it is taken", async (t) => {
  const recent = await createConnection(
    t,
    {},
    {
      lastReload: Date.now() - 1000,
    },
  );
  recent.mismatch(10000);
  assert.equal(recent.reloads.length, 0);
  assert.ok(recent.banner());

  const stale = await createConnection(
    t,
    {},
    {
      lastReload: Date.now() - 20000,
    },
  );
  stale.mismatch(10000);
  assert.equal(stale.reloads.length, 1);
  assert.equal(stale.banner(), undefined);
});

test("a mismatch in prod dispatches a cancelable window event first", async (t) => {
  const c = await createConnection(t);
  const seen = [];
  c.windowEvents.addEventListener(MISMATCH_EVENT, (event) =>
    seen.push({
      cancelable: event.cancelable,
      detail: event.detail,
      reloads: c.reloads.length,
    }),
  );
  c.mismatch();
  assert.deepEqual(seen, [
    {
      cancelable: true,
      detail: { frontend: FRONTEND_SCHEMA, backend: "backend-schema" },
      reloads: 0,
    },
  ]);
  // A listener that does not cancel it leaves the default action in place.
  assert.equal(c.reloads.length, 1);
});

test("canceling the window event skips the reload and the banner", async (t) => {
  // Without a recent reload the default would reload, with one show the banner.
  for (const lastReload of [undefined, Date.now() - 1000]) {
    const c = await createConnection(t, {}, { lastReload });
    c.windowEvents.addEventListener(MISMATCH_EVENT, (event) =>
      event.preventDefault(),
    );
    c.mismatch();
    c.mismatch();
    assert.equal(c.reloads.length, 0);
    assert.equal(c.banner(), undefined);
    assert.equal(c.session.get(LAST_RELOADED_KEY), lastReload?.toString());
    // The console still names both hashes when the app handles the mismatch.
    assert.equal(c.warn.mock.callCount(), 2);
    assert.match(
      c.warn.mock.calls[0].arguments[0],
      /frontend-schema.*backend-schema/,
    );

    await c.enqueue([{ name: "test.event", payload: { id: 1 } }]);
    assert.deepEqual(c.sent.at(-1).value.payload, { id: 1 });
  }
});

test("a mismatch in dev only warns", async (t) => {
  const c = await createConnection(t, {}, { isDevMode: true });
  const listener = t.mock.fn();
  c.windowEvents.addEventListener(MISMATCH_EVENT, listener);
  c.mismatch();
  c.mismatch();
  assert.equal(c.warn.mock.callCount(), 2);
  assert.match(c.warn.mock.calls[0].arguments[0], /backend-schema/);
  assert.equal(listener.mock.callCount(), 0);
  assert.equal(c.reloads.length, 0);
  assert.equal(c.banner(), undefined);
  assert.equal(c.session.has(LAST_RELOADED_KEY), false);
});
