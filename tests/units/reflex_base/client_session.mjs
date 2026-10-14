import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import { createQueueRuntime } from "./client_event_queue_runtime.mjs";

const source = fs.readFileSync(process.argv[2], "utf8");
const tick = () => new Promise((resolve) => setImmediate(resolve));

/** Create browser storage with Web Storage's missing-value behavior. */
function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
    clear: () => values.clear(),
    values,
  };
}

/** Serialize callbacks as the browser's exclusive Web Locks do. */
function locks() {
  let tail = Promise.resolve();
  return {
    request: (_name, callback) => {
      const request = tail.then(callback);
      tail = request.catch(() => {});
      return request;
    },
  };
}

/** Evaluate the frontend with a browser and manually driven Socket.IO peer. */
async function browserSession({
  fetch,
  localStorage = storage(),
  sessionStorage = storage(),
  webLocks,
  warm = false,
  eventURL = "ws://localhost:8000/prefix/_event",
} = {}) {
  const callbacks = new Map();
  const timeouts = new Map();
  const delays = new Map();
  const errors = [];
  const connections = [];
  const warmups = [];
  const requests = [];
  const emitted = [];
  const uploads = [];
  const socket = { current: null };
  const window = {
    location: { hostname: "localhost", protocol: "http:" },
    navigator: { locks: webLocks },
    localStorage,
    sessionStorage,
    addEventListener() {},
    removeEventListener() {},
    setTimeout(callback, delay) {
      const id = Symbol();
      timeouts.set(id, callback);
      delays.set(id, delay);
      return id;
    },
    clearTimeout: (id) => timeouts.delete(id),
    async fetch(url, options) {
      requests.push([String(url), options]);
      return fetch
        ? await fetch(url, options)
        : {
            ok: true,
            json: async () => ({
              client_token: options.headers["Reflex-Client-Token"],
              expires_in: 3600,
            }),
          };
    },
  };
  const runtime = await createQueueRuntime(source, {
    uploadFiles: async (...args) => {
      try {
        await args[10]?.();
        uploads.push(args);
      } catch {}
    },
    browser: {
      window,
      document: {
        cookie: "",
        visibilityState: "visible",
        addEventListener() {},
        removeEventListener() {},
      },
      localStorage,
      sessionStorage,
    },
    env: { EVENT: eventURL, TRANSPORT: "websocket" },
    initialState: warm
      ? { test_state: {}, test_exception_state: {} }
      : undefined,
    io: (_url, options) => {
      const current = {
        connected: false,
        io: {
          opts: options,
          encoder: {},
          decoder: {},
          open(callback) {
            warmups.push(options.query.token);
            callback();
          },
        },
        on: (event, callback) => callbacks.set(event, callback),
        emit: (event, payload) => emitted.push([event, payload]),
        connect() {
          connections.push(this.io.opts.query.token);
          return this;
        },
        disconnect() {
          this.connected = false;
          callbacks.get("disconnect")?.("io client disconnect");
          return this;
        },
      };
      if (options.autoConnect !== false) current.connect();
      return current;
    },
  });
  return {
    runtime,
    socket,
    callbacks,
    timeouts,
    delays,
    connections,
    warmups,
    requests,
    emitted,
    uploads,
    errors,
    localStorage,
    sessionStorage,
    connect: async () => {
      await runtime.connect(
        socket,
        {},
        ["websocket"],
        (update) => {
          errors.splice(
            0,
            errors.length,
            ...(typeof update === "function" ? update(errors) : update),
          );
        },
        {},
        () => {},
        { current: {} },
      );
      await tick();
    },
    async accept(token = "bound-tab", credential) {
      await callbacks.get("new_token")(token);
      const exchange = credential
        ? callbacks.get("session_token")(credential)
        : undefined;
      socket.current.connected = true;
      await callbacks.get("connect")();
      return { exchange };
    },
  };
}

test("cold websocket hydrates before cookie exchange completes", async () => {
  let finish;
  const tab = await browserSession({
    fetch: () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  });
  assert.equal(tab.runtime.getToken(), "");
  await tab.connect();
  assert.deepEqual(tab.connections, [""]);
  assert.equal(
    tab.socket.current.auth.event.name,
    "reflex___state.test.hydrate_and_load",
  );
  assert.deepEqual(tab.socket.current.auth.event.payload.hashes, {
    test_state: "compiled-defaults",
  });
  assert.equal(tab.requests.length, 0);
  const { exchange } = await tab.accept("bound-tab", "signed-credential");
  assert.equal(tab.runtime.event_queue.length, 0);
  tab.runtime.event_queue.push({ name: "reflex___state.test.after_hydrate" });
  await tab.runtime.processEvent(tab.socket.current, () => {}, { current: {} });
  assert.equal(tab.emitted.length, 1);
  const [url, options] = tab.requests[0];
  assert.equal(url, "http://localhost:8000/prefix/_reflex/session");
  assert.equal(options.credentials, "include");
  assert.equal(options.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(options.body), {
    session_token: "signed-credential",
  });
  assert.equal(tab.socket.current.io.opts.withCredentials, true);
  finish({
    ok: true,
    json: async () => ({ client_token: "bound-tab", expires_in: 3600 }),
  });
  await exchange;
  assert.equal(tab.runtime.getToken(), "bound-tab");
  assert.equal(tab.sessionStorage.getItem("token"), null);
  for (const value of [
    ...tab.sessionStorage.values.values(),
    ...tab.localStorage.values.values(),
  ]) {
    assert.notEqual(value, "signed-credential");
  }
});

test("legacy tokens are presented for validation without being adopted", async () => {
  const sessionStorage = storage();
  sessionStorage.setItem("token", "legacy-unbound");
  const tab = await browserSession({ sessionStorage });
  assert.equal(tab.runtime.getToken(), "");
  await tab.connect();
  assert.deepEqual(tab.connections, ["legacy-unbound"]);
  await tab.accept("bound-tab");
  assert.equal(tab.runtime.getToken(), "bound-tab");
  assert.equal(sessionStorage.getItem("token"), "legacy-unbound");
});

test("cold tabs wait for the first cookie while its socket hydrates", async () => {
  const webLocks = locks();
  const localStorage = storage();
  let finish;
  const first = await browserSession({
    webLocks,
    localStorage,
    fetch: () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  });
  const second = await browserSession({ webLocks, localStorage });
  await Promise.all([first.connect(), first.connect(), second.connect()]);
  assert.deepEqual(first.connections, [""]);
  assert.deepEqual(second.connections, []);
  const { exchange } = await first.accept("first-tab", "credential");
  assert.equal(first.socket.current.connected, true);
  assert.deepEqual(second.connections, []);
  finish({
    ok: true,
    json: async () => ({ client_token: "first-tab", expires_in: 3600 }),
  });
  await exchange;
  await tick();
  assert.deepEqual(second.connections, [""]);
  await second.accept("second-tab");
  assert.equal(second.requests.length, 0);
});

test("fresh hint reconnects directly without HTTP or a lock", async () => {
  const first = await browserSession();
  await first.connect();
  await (await first.accept("existing-tab", "credential")).exchange;
  const tab = await browserSession({
    warm: true,
    localStorage: first.localStorage,
    sessionStorage: first.sessionStorage,
    webLocks: {
      request() {
        throw new Error("fresh session must not wait");
      },
    },
  });
  await tick();
  assert.deepEqual(tab.warmups, ["existing-tab"]);
  assert.deepEqual(tab.connections, []);
  await tab.connect();
  assert.deepEqual(tab.connections, ["existing-tab"]);
  assert.equal(tab.requests.length, 0);
  await tab.accept("existing-tab");
  tab.socket.current.disconnect();
  await tab.socket.current.reconnect();
  assert.deepEqual(tab.connections, ["existing-tab", "existing-tab"]);
  assert.equal(tab.socket.current.auth.event.payload.hashes, undefined);
  assert.equal(tab.requests.length, 0);
});

test("cold transport cannot capture cookies before the session lock", async () => {
  const tab = await browserSession({ warm: true, webLocks: locks() });
  await tick();
  assert.deepEqual(tab.warmups, []);
  await tab.connect();
  assert.deepEqual(tab.connections, [""]);
  await (await tab.accept("bound-tab", "credential")).exchange;
});

test("cookie-wins exchange adopts its token and reconnects the provisional socket", async () => {
  const tab = await browserSession({
    fetch: async () => ({
      ok: true,
      json: async () => ({ client_token: "cookie-tab", expires_in: 3600 }),
    }),
  });
  await tab.connect();
  await (await tab.accept("provisional-tab", "credential")).exchange;
  assert.deepEqual(tab.connections, ["", "cookie-tab"]);
  assert.equal(tab.runtime.getToken(), "cookie-tab");
});

for (const teardown of [false, true]) {
  test(`cookie-wins readiness waits for reconnect and respects teardown=${teardown}`, async () => {
    let finish;
    const tab = await browserSession({
      fetch: () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    });
    await tab.connect();
    const { exchange } = await tab.accept("provisional-tab", "credential");
    let ready = false;
    const pending = tab.runtime.waitForSession().then(() => {
      ready = true;
    });
    pending.catch(() => {});
    await tab.runtime.applyRestEvent(
      { name: "upload", handler: "uploadFiles", payload: { files: [] } },
      tab.socket.current,
    );
    finish({
      ok: true,
      json: async () => ({ client_token: "cookie-tab", expires_in: 3600 }),
    });
    await exchange;
    await tick();
    assert.equal(tab.socket.current.connected, false);
    assert.equal(ready, false);
    assert.equal(tab.uploads.length, 0);
    if (teardown) {
      tab.socket.current.releaseSessionBootstrap();
      await assert.rejects(pending, /Session connection closed/);
      await tick();
      assert.equal(tab.uploads.length, 0);
    } else {
      await tab.accept("cookie-tab");
      await pending;
      await tick();
      assert.equal(ready, true);
      assert.equal(tab.uploads.length, 1);
      assert.equal(tab.runtime.getToken(), "cookie-tab");
    }
  });
}

test("refresh and duplicate-tab updates preserve a socket with matching identity", async () => {
  const tab = await browserSession();
  await tab.connect();
  await tab.accept("first-tab");
  await tab.callbacks.get("new_token")("duplicated-tab");
  await tab.callbacks.get("session_refresh")();
  assert.equal(tab.emitted.at(-1)[0], "session_refresh");
  await tab.callbacks.get("session_token")("renewed-credential");
  assert.equal(
    tab.requests[0][1].headers["Reflex-Client-Token"],
    "duplicated-tab",
  );
  assert.deepEqual(JSON.parse(tab.requests[0][1].body), {
    session_token: "renewed-credential",
  });
  assert.deepEqual(tab.connections, [""]);
});

test("failed exchange releases the cold-tab lock and surfaces failure", async () => {
  const webLocks = locks();
  const first = await browserSession({
    webLocks,
    fetch: async () => ({ ok: false, status: 403 }),
  });
  const second = await browserSession({ webLocks });
  await first.connect();
  await second.connect();
  await (await first.accept("first-tab", "credential")).exchange;
  await tick();
  assert.deepEqual(second.connections, [""]);
  assert.equal(first.errors.length, 1);
  assert.equal(first.runtime.getToken(), "first-tab");
});

test("stalled exchange times out without holding up hydration", async () => {
  const tab = await browserSession({
    fetch: (_url, { signal }) =>
      new Promise((_resolve, reject) => {
        signal.addEventListener("abort", () => reject(new Error("timed out")));
      }),
  });
  await tab.connect();
  const { exchange } = await tab.accept("first-tab", "credential");
  assert.equal(tab.socket.current.connected, true);
  tab.timeouts.values().next().value();
  await exchange;
  assert.equal(tab.errors[0].message, "timed out");
});

test("disconnecting before acceptance releases the cold-tab lock", async () => {
  const webLocks = locks();
  const first = await browserSession({ webLocks });
  const second = await browserSession({ webLocks });
  await first.connect();
  await second.connect();
  first.socket.current.disconnect();
  await tick();
  assert.deepEqual(second.connections, [""]);
});

test("backend apps have independent token and freshness storage", async () => {
  const first = await browserSession();
  await first.connect();
  await (await first.accept("first-tab", "credential")).exchange;
  const second = await browserSession({
    localStorage: first.localStorage,
    sessionStorage: first.sessionStorage,
    eventURL: "ws://localhost:9000/other/_event",
  });
  assert.equal(second.runtime.getToken(), "");
  await second.connect();
  assert.deepEqual(second.connections, [""]);
});

test("uploads wait for the cookie while following WebSocket events drain", async () => {
  let finish;
  const tab = await browserSession({
    fetch: () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  });
  await tab.connect();
  const { exchange } = await tab.accept("first-tab", "credential");
  await tab.runtime.queueEvents(
    [
      {
        name: "reflex___state.test.upload",
        handler: "uploadFiles",
        payload: { files: [] },
      },
      { name: "reflex___state.test.ordinary" },
    ],
    tab.socket,
    false,
    () => {},
    { current: {} },
  );
  assert.equal(tab.uploads.length, 0);
  assert.equal(tab.emitted.length, 1);
  finish({
    ok: true,
    json: async () => ({ client_token: "first-tab", expires_in: 3600 }),
  });
  await exchange;
  await tick();
  assert.equal(tab.uploads.length, 1);
});

test("failed initial exchange holds HTTP readiness until recovery or disconnect", async () => {
  const tab = await browserSession({
    fetch: async () => ({ ok: false, status: 403 }),
  });
  await tab.connect();
  await (await tab.accept("first-tab", "credential")).exchange;
  let ready = false;
  const pending = tab.runtime.waitForSession().then(() => {
    ready = true;
  });
  pending.catch(() => {});
  await tick();
  assert.equal(ready, false);
  await tab.runtime.applyRestEvent(
    { name: "upload", handler: "uploadFiles", payload: { files: [] } },
    tab.socket.current,
  );
  await tick();
  assert.equal(tab.uploads.length, 0);
  tab.socket.current.disconnect();
  await assert.rejects(pending, /Session connection closed/);
  await tick();
  assert.equal(tab.uploads.length, 0);
});

test("idle sessions schedule renewal without an application event", async () => {
  const tab = await browserSession({
    fetch: async () => ({
      ok: true,
      json: async () => ({
        client_token: "bound-tab",
        expires_in: 100,
        refresh_in: 20,
      }),
    }),
  });
  await tab.connect();
  await (await tab.accept("bound-tab", "credential")).exchange;
  const timer = [...tab.timeouts.keys()].find(
    (id) => tab.delays.get(id) === 20000,
  );
  assert.ok(timer, "renewal uses the server's configured refresh interval");
  tab.timeouts.get(timer)();
  await tick();
  assert.equal(tab.emitted.at(-1)[0], "session_refresh");
  await tab.callbacks.get("session_token")("renewed-credential");
  assert.equal(
    JSON.parse(tab.requests.at(-1)[1].body).session_token,
    "renewed-credential",
  );
  tab.socket.current.disconnect();
  assert.equal(tab.timeouts.size, 0, "disconnect clears renewal timers");
});

test("transient exchange failure retries and recovers HTTP readiness on the live socket", async () => {
  let fail = true;
  const tab = await browserSession({
    fetch: async () =>
      fail
        ? { ok: false, status: 503 }
        : {
            ok: true,
            json: async () => ({ client_token: "bound-tab", expires_in: 100 }),
          },
  });
  await tab.connect();
  await (await tab.accept("bound-tab", "credential")).exchange;
  let ready = false;
  const readiness = tab.runtime.waitForSession().then(() => {
    ready = true;
  });
  // Observe rejection so a failing regression does not leak an unhandled promise.
  readiness.catch(() => {});
  await tick();
  assert.equal(ready, false);
  fail = false;
  for (const callback of [...tab.timeouts.values()]) callback();
  await tick();
  assert.equal(tab.emitted.at(-1)?.[0], "session_refresh");
  await tab.callbacks.get("session_token")("fresh-credential");
  await readiness;
  assert.equal(ready, true);
  await tab.runtime.waitForSession();
  assert.deepEqual(tab.connections, [""]);
});

test("an exchange completing after disconnect cannot replace a newer connection's token", async () => {
  let finish;
  const tab = await browserSession({
    fetch: () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  });
  await tab.connect();
  const { exchange } = await tab.accept("first-tab", "credential");
  const ready = tab.runtime.waitForSession();
  ready.catch(() => {});
  tab.socket.current.disconnect();
  await assert.rejects(ready, /Session connection closed/);
  await tab.callbacks.get("new_token")("next-tab");
  finish({
    ok: true,
    json: async () => ({ client_token: "stale-tab", expires_in: 100 }),
  });
  await exchange;
  assert.equal(tab.runtime.getToken(), "next-tab");
  assert.equal(tab.timeouts.size, 0);
});
