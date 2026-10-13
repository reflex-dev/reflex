import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import { createQueueRuntime } from "./client_event_queue_runtime.mjs";

const source = fs.readFileSync(process.argv[2], "utf8");

/** Connect the real event handler to an isolated socket and browser storage. */
async function createConnection(t, dispatch = {}) {
  t.mock.method(console, "warn", () => {});
  const handlers = new Map();
  const sent = [];
  const saved = new Map();
  const sessionStorage = { getItem: () => "test-token", setItem() {} };
  const socket = {
    connected: true,
    io: { encoder: {}, decoder: {} },
    on: (name, handler) => handlers.set(name, handler),
    emit: (name, value) => sent.push({ name, value }),
    connect: () => handlers.get("connect")(),
  };
  const app = { initialEvents: () => [{ name: "test.hydrate", payload: {} }] };
  const runtime = await createQueueRuntime(source, {
    dependencies: {
      "test:browser": {
        window: {
          location: { pathname: "/", search: "", hash: "" },
          sessionStorage,
          addEventListener() {},
        },
        document: { addEventListener() {} },
        localStorage: { setItem: (key, value) => saved.set(key, value) },
        sessionStorage,
      },
      "socket.io-client": { default: () => socket },
      "$/env.json": { default: { EVENT: "http://backend/_event" } },
      "$/utils/context-registry": { app, eventLoop: {} },
    },
  });
  await runtime.connect(
    { current: null },
    dispatch,
    ["websocket"],
    () => {},
    { local_storage: { "known.value": {}, "unknown.value": {} } },
    () => {},
    { current: {} },
  );
  return {
    sent,
    saved,
    reports: () => sent.filter((event) => event.name === "client_error"),
    receive: (update) => handlers.get("event")(update),
    reconnect: () => handlers.get("connect")(),
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
