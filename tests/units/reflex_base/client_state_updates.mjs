import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import { createQueueRuntime } from "./client_event_queue_runtime.mjs";

const source = fs.readFileSync(process.argv[2], "utf8");

/** Connect the real event handler to an isolated socket and browser storage. */
async function createConnection(t, dispatch = {}) {
  t.mock.method(console, "error", () => {});
  t.mock.method(console, "warn", () => {});
  const handlers = new Map();
  const sent = [];
  const saved = new Map();
  const sessionStorage = {
    getItem: () => "test-token",
    setItem: (key, value) => saved.set(key, value),
  };
  const socket = {
    connected: true,
    io: { encoder: {}, decoder: {} },
    on: (name, handler) => handlers.set(name, handler),
    emit: (name, value) => sent.push({ name, value }),
    connect: () => handlers.get("connect")(),
  };
  const app = {
    initialEvents: () => [{ name: "test.hydrate", payload: {} }],
    state_name: "known.first",
  };
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
  const params = { current: {} };
  await runtime.connect(
    { current: null },
    dispatch,
    ["websocket"],
    () => {},
    {
      local_storage: {
        "known.first.value": {},
        "unknown.first.value": {},
      },
      session_storage: { "known.second.value": {} },
    },
    () => {},
    params,
  );
  return {
    sent,
    saved,
    dispatch,
    reports: () => sent.filter((event) => event.name === "client_error"),
    receive: (update) => handlers.get("event")(update),
    enqueue: (events) =>
      runtime.queueEvents(events, socket, false, () => {}, params),
  };
}

for (const unknownFirst of [true, false]) {
  test(`mixed delta applies known state, unknown first=${unknownFirst}`, async (t) => {
    const applied = [];
    const c = await createConnection(t, {
      "known.first": (value) => applied.push(value),
      "known.second": (value) => applied.push(value),
    });
    const entries = [
      ["known.first", { value: "one", is_hydrated_rx_state_: true }],
      ["known.second", { value: "two" }],
    ];
    const unknown = ["unknown.first", { value: "ignored" }];
    unknownFirst ? entries.unshift(unknown) : entries.push(unknown);
    const delta = Object.freeze(Object.fromEntries(entries));
    const callback = { name: "test.callback", payload: {} };
    c.receive({ delta, events: [callback] });
    assert.deepEqual(applied, [
      { value: "one", is_hydrated_rx_state_: true },
      { value: "two" },
    ]);
    assert.deepEqual(
      [...c.saved],
      [
        ["known.first.value", "one"],
        ["known.second.value", "two"],
      ],
    );
    assert.equal(delta["unknown.first"].value, "ignored");
    assert.equal(c.reports().length, 1);
    assert.equal(c.reports()[0].value.substate, "unknown.first");
    assert.equal(c.reports()[0].value.error_type, "dispatch_function_missing");
    assert.match(c.reports()[0].value.message, /rebuild/);
    assert.ok(c.sent.some((event) => event.value === callback));

    // A later valid update and a new outbound event still work.
    c.receive({ delta: { "known.first": { value: "three" } } });
    await c.enqueue([{ name: "test.bump", payload: {} }]);
    assert.deepEqual(applied.at(-1), { value: "three" });
    assert.equal(c.saved.get("known.first.value"), "three");
    assert.equal(c.sent.at(-1).value.name, "test.bump");
    assert.equal(c.reports().length, 1);
  });
}

test("unknown-only updates report each missing name once and allow events", async (t) => {
  const c = await createConnection(t);
  for (let i = 0; i < 3; i++) {
    c.receive({ delta: { "unknown.first": { value: i } } });
  }
  assert.equal(c.reports().length, 1);
  assert.equal(c.saved.size, 0);
  c.receive({
    delta: { "unknown.first": {}, "unknown.second": {}, "unknown.third": {} },
  });
  assert.equal(c.reports().length, 2);
  assert.equal(c.reports()[1].value.substate, "unknown.second, unknown.third");
  const callback = { name: "test.callback", payload: {} };
  c.receive({ events: [callback] });
  await c.enqueue([{ name: "test.bump", payload: {} }]);
  assert.ok(c.sent.some((event) => event.value === callback));
  assert.equal(c.sent.at(-1).value.name, "test.bump");

  // Diagnostics must not prevent a subsequently registered state from updating.
  const applied = [];
  c.dispatch["unknown.first"] = (value) => applied.push(value);
  c.receive({ delta: { "unknown.first": { value: "registered" } } });
  assert.deepEqual(applied, [{ value: "registered" }]);
  assert.equal(c.saved.get("unknown.first.value"), "registered");
  assert.equal(c.reports().length, 2);
});

test("reducer failures still reach the backend error handler", async (t) => {
  const c = await createConnection(t, {
    "known.first": () => {
      throw new Error("failed reducer");
    },
  });
  c.receive({ delta: { "known.first": {} } });
  assert.deepEqual(c.reports()[0].value, {
    message: "failed reducer",
    error_type: "state_update_processing_error",
  });
});
