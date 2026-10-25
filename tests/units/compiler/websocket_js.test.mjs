import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const helpers = new URL(
  "../../../packages/reflex-base/src/reflex_base/.templates/web/utils/helpers/",
  import.meta.url,
);
const source = await readFile(new URL("websocket.js", helpers), "utf8");
const jsonSource = await readFile(new URL("json.js", helpers), "utf8");

/** Evaluate the actual transport module against a scripted browser WebSocket. */
async function setup({
  throwOnConstruct = false,
  closeLater = false,
  url = "http://localhost:8000/_event",
} = {}) {
  const sockets = [];
  const timers = new Map();
  const reported = [];
  const listeners = new Map();

  class WebSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;

    constructor(url, protocols) {
      if (throwOnConstruct) {
        // Mixed content or a CSP violation fails the constructor itself.
        throw new Error("SecurityError: insecure WebSocket from https");
      }
      this.url = String(url);
      this.protocols = protocols;
      this.readyState = WebSocket.CONNECTING;
      this.sent = [];
      sockets.push(this);
    }

    send(frame) {
      assert.equal(this.readyState, WebSocket.OPEN);
      this.sent.push(typeof frame === "string" ? JSON.parse(frame) : frame);
    }

    close() {
      if (closeLater) {
        // A dead link: the browser reports the close only after its closing
        // handshake times out, up to a minute later.
        this.readyState = WebSocket.CLOSING;
        return;
      }
      this.readyState = WebSocket.CLOSED;
      this.onclose?.({ code: 1000, reason: "" });
    }

    // Test controls standing in for the network.
    open() {
      this.readyState = WebSocket.OPEN;
      this.onopen?.();
    }

    receive(frame) {
      this.onmessage({ data: JSON.stringify(frame) });
    }

    serverClose(code, reason = "") {
      this.readyState = WebSocket.CLOSED;
      this.onclose?.({ code, reason });
    }
  }

  const context = vm.createContext({
    console,
    URL,
    URLSearchParams,
    TextEncoder,
    TextDecoder,
    ArrayBuffer,
    DataView,
    Uint8Array,
    WebSocket,
    queueMicrotask,
    SharedArrayBuffer,
    reportError: (error) => reported.push(error),
    setTimeout: (fn, ms) => {
      timers.set(fn, ms);
      return fn;
    },
    clearTimeout: (fn) => timers.delete(fn),
    addEventListener: (name, fn) => listeners.set(name, fn),
    removeEventListener: (name, fn) =>
      listeners.get(name) === fn && listeners.delete(name),
  });
  const module = new vm.SourceTextModule(source, { context });
  await module.link((specifier) => {
    assert.equal(specifier, "$/utils/helpers/json");
    return new vm.SourceTextModule(jsonSource, { context });
  });
  await module.evaluate();
  const transport = new module.namespace.ReflexWebSocket(url, {
    query: { token: "tok" },
    protocols: ["version"],
  });
  const events = [];
  for (const name of ["connect", "connect_error", "disconnect", "event"]) {
    transport.on(name, (...args) => events.push([name, ...args]));
  }
  return {
    transport,
    sockets,
    timers,
    events,
    reported,
    listeners,
    getChannel: module.namespace.getChannel,
    decodeChannelFrame: module.namespace.decodeChannelFrame,
  };
}

/**
 * Connect the transport and complete its handshake.
 * @param app The test setup.
 * @param handshake Overrides for the handshake payload.
 * @returns The connected scripted socket.
 */
function connectTransport(app, handshake = {}) {
  app.transport.connect();
  const socket = app.sockets.at(-1);
  socket.open();
  socket.receive(["_handshake", { ...HANDSHAKE[1], ...handshake }]);
  return socket;
}

const HANDSHAKE = [
  "_handshake",
  { ping_interval: 25, ping_timeout: 120, protocol: 2, max_message_size: 1e6 },
];

test("connect sends the connect frame with auth as soon as the socket opens", async () => {
  const { transport, sockets, events } = await setup();
  assert.equal(sockets.length, 0, "the constructor must not dial");
  transport.auth = { event: { name: "boot" } };
  transport.connect();
  const [socket] = sockets;
  assert.equal(new URL(socket.url).searchParams.get("token"), "tok");
  assert.deepEqual(socket.protocols, ["version"]);
  socket.open();
  // No waiting for the handshake: it acknowledges this frame.
  assert.deepEqual(socket.sent, [["_connect", { event: { name: "boot" } }]]);
  assert.equal(transport.connected, false);
  transport.emit("event", { name: "click" });
  assert.equal(socket.sent.length, 1, "events wait for the acknowledgement");
  socket.receive(HANDSHAKE);
  assert.equal(transport.connected, true);
  assert.deepEqual(socket.sent[1], ["event", { name: "click" }]);
  assert.deepEqual(events, [["connect"]]);
});

test("a socket dialed ahead by open opens its session when connect claims it", async () => {
  const { transport, sockets, timers } = await setup();
  transport.open();
  const [socket] = sockets;
  socket.open();
  assert.deepEqual(socket.sent, []);
  // The session timeout starts with the claim, not the dial.
  assert.equal(timers.size, 0);
  transport.auth = { event: { name: "boot" } };
  transport.connect();
  assert.equal(sockets.length, 1);
  assert.deepEqual(socket.sent, [["_connect", { event: { name: "boot" } }]]);
  assert.equal(timers.size, 1);
});

test("connect does nothing more while the session is opening", async () => {
  const { transport, sockets } = await setup();
  transport.connect();
  transport.connect();
  sockets[0].open();
  transport.connect();
  assert.equal(sockets.length, 1);
  assert.equal(sockets[0].sent.length, 1);
});

test("a closed session is reopened on a new socket with the current auth and token", async () => {
  const { transport, sockets, events } = await setup();
  transport.connect();
  sockets[0].open();
  sockets[0].receive(HANDSHAKE);
  sockets[0].close();
  assert.deepEqual(events.at(-1).slice(0, 2), [
    "disconnect",
    "transport close",
  ]);
  transport.auth = { event: { name: "rehydrate" } };
  transport.io.opts.query = { token: "assigned" };
  transport.connect();
  assert.equal(sockets.length, 2);
  assert.equal(new URL(sockets[1].url).searchParams.get("token"), "assigned");
  sockets[1].open();
  assert.deepEqual(sockets[1].sent, [
    ["_connect", { event: { name: "rehydrate" } }],
  ]);
});

test("a session that is never acknowledged fails as a connect error", async () => {
  const { transport, sockets, timers, events } = await setup();
  transport.connect();
  sockets[0].open();
  const [expire] = timers.keys();
  expire();
  assert.equal(sockets[0].readyState, sockets[0].constructor.CLOSED);
  assert.equal(events.at(-1)[0], "connect_error");
  assert.equal(timers.size, 0);
});

/**
 * The UTF-8 size of the connect frame carrying the transport's auth.
 * @param transport The transport.
 * @returns The size in bytes.
 */
const connectFrameSize = (transport) =>
  new TextEncoder().encode(JSON.stringify(["_connect", transport.auth]))
    .byteLength;

for (const [reason, named] of [
  ["max_message_size=100", " (100 bytes)"],
  // An older backend, or a proxy with its own limit.
  ["", ""],
  ["Message Too Big", ""],
]) {
  test(`a connect frame refused for its size with reason ${JSON.stringify(reason)} reports the hydrate`, async () => {
    const { transport, sockets, events, timers } = await setup();
    transport.auth = {
      event: { name: "boot", payload: { large: "é".repeat(80) } },
    };
    transport.connect();
    sockets[0].open();
    sockets[0].serverClose(1009, reason);
    assert.equal(events.length, 1);
    const [name, error] = events[0];
    assert.equal(name, "connect_error");
    assert.equal(error.code, "hydration_payload_too_large");
    assert.equal(
      error.message,
      `Hydration payload (${connectFrameSize(transport)} bytes) exceeds the ` +
        `server limit${named}. Reduce browser storage data and reload.`,
    );
    assert.equal(timers.size, 0);
  });
}

test("other closes are a generic connect error before the handshake and a disconnect after it", async () => {
  const app = await setup();
  app.transport.connect();
  app.sockets[0].open();
  app.sockets[0].serverClose(1008);
  const [name, error] = app.events.at(-1);
  assert.equal(name, "connect_error");
  assert.equal(error.message, "websocket connection failed");
  assert.equal(error.code, undefined);

  // A session's oversized message is not its hydrate.
  const socket = connectTransport(app);
  socket.serverClose(1009, "max_message_size=100");
  assert.deepEqual(app.events.at(-1).slice(0, 2), [
    "disconnect",
    "transport close",
  ]);
});

test("a reconnect over the limit an earlier handshake announced is refused before sending", async () => {
  const app = await setup();
  const first = connectTransport(app, { max_message_size: 100 });
  first.serverClose(1001);
  app.transport.auth = { event: { name: "rehydrate", large: "x".repeat(200) } };
  app.transport.connect();
  const socket = app.sockets.at(-1);
  socket.open();
  assert.notEqual(socket, first);
  assert.deepEqual(socket.sent, []);
  assert.equal(socket.readyState, socket.constructor.CLOSED);
  assert.equal(app.timers.size, 0);
  assert.equal(app.events.filter(([n]) => n === "connect_error").length, 1);
  const [name, error] = app.events.at(-1);
  assert.equal(name, "connect_error");
  assert.equal(error.code, "hydration_payload_too_large");
  assert.equal(
    error.message,
    `Hydration payload (${connectFrameSize(app.transport)} bytes) exceeds ` +
      "the server limit (100 bytes). Reduce browser storage data and reload.",
  );

  // One that fits is sent.
  app.transport.auth = { event: { name: "rehydrate" } };
  app.transport.connect();
  app.sockets.at(-1).open();
  assert.deepEqual(app.sockets.at(-1).sent, [
    ["_connect", { event: { name: "rehydrate" } }],
  ]);
});

test("the transport dials the event path with a trailing slash", async () => {
  // Proxy rules written for Socket.IO route "/_event/*", which "/_event" misses.
  const { transport, sockets } = await setup();
  transport.connect();
  assert.equal(new URL(sockets[0].url).pathname, "/_event/");
});

test("a handler removing itself does not skip the next one", async () => {
  const { transport } = await setup();
  const calls = [];
  const once = () => {
    calls.push("once");
    transport.off("custom", once);
  };
  transport.on("custom", once);
  transport.on("custom", () => calls.push("next"));
  transport._emitLocal("custom");
  transport._emitLocal("custom");
  assert.deepEqual(calls, ["once", "next", "next"]);
});

test("a throwing channel handler cannot leave the transport half torn down", async () => {
  const app = await setup();
  const socket = connectTransport(app);
  const channel = app.getChannel("throws-on-disconnect");
  socket.receive(["_opened", null, "throws-on-disconnect"]);
  channel.on("disconnect", () => {
    throw new Error("component already unmounted");
  });
  app.transport.disconnect();
  assert.equal(app.transport.connected, false);
  assert.equal(socket.readyState, socket.constructor.CLOSED);
  assert.equal(app.events.at(-1)[0], "disconnect");
  assert.equal(app.reported.length, 1);
  assert.match(app.reported[0].message, /already unmounted/);
});

test("the ping watchdog reports a dead link at once", async () => {
  const app = await setup({ closeLater: true });
  connectTransport(app);
  const channel = app.getChannel("watched");
  app.sockets[0].receive(["_opened", null, "watched"]);
  const watchdog = [...app.timers.keys()].at(-1);
  watchdog();
  // Not when the browser gives up on the closing handshake, a minute later.
  assert.equal(app.transport.connected, false);
  assert.deepEqual(app.events.at(-1).slice(0, 2), [
    "disconnect",
    "ping timeout",
  ]);
  assert.equal(channel.connected, false);
});

test("going offline reports the disconnect at once", async () => {
  // Localhost keeps working offline, so only a remote backend is watched.
  const app = await setup({
    url: "https://example.com/_event",
    closeLater: true,
  });
  connectTransport(app);
  app.listeners.get("offline")();
  assert.equal(app.transport.connected, false);
  const [name, reason, details] = app.events.at(-1);
  assert.deepEqual([name, reason], ["disconnect", "transport close"]);
  assert.equal(details.description, "network connection lost");
  // Disposing of the transport releases the listener.
  app.transport.off();
  assert.equal(app.listeners.size, 0);
});

test("a channel opened twice reports connect once", async () => {
  const app = await setup();
  const socket = connectTransport(app);
  const channel = app.getChannel("twice");
  let connects = 0;
  channel.on("connect", () => connects++);
  socket.receive(["_opened", null, "twice"]);
  socket.receive(["_opened", null, "twice"]);
  assert.equal(connects, 1);
});

test("a socket constructor that throws becomes a connect error", async () => {
  const app = await setup({ throwOnConstruct: true });
  app.transport.connect();
  // Reported on a later tick, like any failed dial, once handlers exist.
  assert.deepEqual(app.events, []);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(app.events.length, 1);
  assert.equal(app.events[0][0], "connect_error");
  assert.match(app.events[0][1].message, /SecurityError/);
  // A later attempt dials again rather than finding the transport stuck.
  app.transport.connect();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(app.events.length, 2);
});

test("a channel refuses names and attachments the backend cannot take", async () => {
  const app = await setup();
  const socket = connectTransport(app);
  const channel = app.getChannel("strict");
  socket.receive(["_opened", null, "strict"]);
  const before = socket.sent.length;
  for (const name of [
    undefined,
    42,
    "",
    "_open",
    "_custom",
    "connect",
    "disconnect",
    "error",
  ]) {
    assert.throws(() => channel.emit(name, null));
  }
  for (const buffers of [
    new ArrayBuffer(8),
    [{ size: 3 }],
    [[1, 2, 3]],
    ["abc"],
  ]) {
    assert.throws(() => channel.emit("push", null, buffers), {
      name: "TypeError",
    });
  }
  for (const name of [undefined, "has space", "x".repeat(65)]) {
    assert.throws(() => app.getChannel(name), { name: "TypeError" });
  }
  // Nothing refused was sent or queued behind the message that is valid.
  channel.emit("push", null);
  assert.deepEqual(socket.sent.slice(before), [["push", null, "strict"]]);
});

test("shared buffers are sent whole", async () => {
  const app = await setup();
  const socket = connectTransport(app);
  const channel = app.getChannel("shared");
  socket.receive(["_opened", null, "shared"]);
  channel.emit("push", null, [new SharedArrayBuffer(8)]);
  const [, , , buffers] = app.decodeChannelFrame(socket.sent.at(-1));
  assert.equal(buffers[0].byteLength, 8);
});

test("an oversized event is dropped instead of costing the socket", async () => {
  const app = await setup();
  const socket = connectTransport(app, { max_message_size: 100 });
  const before = socket.sent.length;
  app.transport.emit("event", { blob: "x".repeat(200) });
  assert.equal(socket.sent.length, before);
  assert.equal(app.reported.length, 1);
  assert.match(app.reported[0].message, /over the 100/);
  app.transport.emit("event", { small: true });
  assert.equal(socket.sent.length, before + 1);
});

test("an event queued before the handshake is checked against the limit it brings", async () => {
  const app = await setup();
  app.transport.connect();
  const socket = app.sockets.at(-1);
  socket.open();
  // Emitted before the backend has said what it accepts.
  app.transport.emit("event", { name: "state.big", blob: "x".repeat(200) });
  app.transport.emit("event", { small: true });
  socket.receive(["_handshake", { ...HANDSHAKE[1], max_message_size: 100 }]);
  assert.deepEqual(socket.sent.slice(1), [["event", { small: true }]]);
  assert.equal(app.reported.length, 1);
  assert.match(
    app.reported[0].message,
    /"state\.big" is \d+ bytes, over the 100/,
  );
});

test("a channel message queued on a closing socket is checked against the next backend's limit", async () => {
  const app = await setup();
  let socket = connectTransport(app);
  const channel = app.getChannel("big");
  const errors = [];
  channel.on("error", (error) => errors.push(error));
  socket.receive(["_opened", null, "big"]);
  // The socket is closing, but the browser has not reported the close yet.
  socket.readyState = 2;
  channel.emit("push", { blob: "x".repeat(200) });
  socket.readyState = 3;
  socket.onclose({ code: 1006, reason: "" });

  // The reconnect lands on a backend that accepts less.
  socket = connectTransport(app, { max_message_size: 100 });
  assert.deepEqual(
    socket.sent.map((frame) => frame[0]),
    ["_connect", "_open"],
  );
  assert.deepEqual(
    errors.map((error) => error.code),
    ["message_too_large"],
  );
});

test("a channel message over the backend's limit is refused, measured in UTF-8 bytes", async () => {
  const app = await setup();
  const socket = connectTransport(app, { max_message_size: 1024 });
  const channel = app.getChannel("sized");
  socket.receive(["_opened", null, "sized"]);
  const before = socket.sent.length;
  assert.throws(
    () => channel.emit("push", { blob: "x".repeat(5000) }),
    /"push" is \d+ bytes, over the 1024 the backend accepts \(REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE\)\.$/,
  );
  // 400 characters, 1200 UTF-8 bytes: only a byte-accurate check catches it.
  assert.throws(
    () => channel.emit("push", "\u20ac".repeat(400)),
    (error) => {
      const bytes = Number(/is (\d+) bytes/.exec(error.message)[1]);
      return bytes > 1024 && bytes < 4 * 400;
    },
  );
  channel.emit("push", { small: true });
  assert.deepEqual(socket.sent.slice(before), [
    ["push", { small: true }, "sized"],
  ]);
});

test("a channel message emitted before any limit was known is checked when the channel opens", async () => {
  const app = await setup();
  const channel = app.getChannel("early");
  const errors = [];
  channel.on("error", (error) => errors.push(error));
  // No transport yet, so no limit to check against.
  channel.emit("push", { blob: "y".repeat(5000) });
  channel.emit("push", { small: true });
  const socket = connectTransport(app, { max_message_size: 1024 });
  socket.receive(["_opened", null, "early"]);
  assert.deepEqual(socket.sent.slice(1), [
    ["_open", null, "early"],
    ["push", { small: true }, "early"],
  ]);
  assert.equal(errors.length, 1);
  assert.equal(errors[0].code, "message_too_large");
  assert.match(
    errors[0].message,
    /^A queued channel message is \d+ bytes, over the 1024 the backend accepts \(REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE\); it was dropped\.$/,
  );
});

test("channel frames still queued are dropped on a backend without channels", async () => {
  const app = await setup();
  let socket = connectTransport(app);
  const channel = app.getChannel("probe");
  const errors = [];
  channel.on("error", (error) => errors.push(error.code));
  socket.receive(["_opened", null, "probe"]);
  // The socket is closing, but the browser has not reported the close yet, so
  // these frames queue on the transport.
  socket.readyState = socket.constructor.CLOSING;
  app.transport.emit("event", { name: "state.event" });
  channel.emit("push", { n: 1 });
  channel.emit("frame", { n: 2 }, [new Uint8Array([1, 2, 3])]);
  socket.readyState = socket.constructor.CLOSED;
  socket.onclose({ code: 1006, reason: "" });

  // The reconnect lands on a backend that closes the socket over either.
  socket = connectTransport(app, { protocol: 1 });
  assert.deepEqual(socket.sent.slice(1), [["event", { name: "state.event" }]]);
  assert.equal(app.transport._sendQueue.length, 0);
  assert.deepEqual(errors, ["channels_unsupported"]);
});

test("an _opened from a transport the channel has left changes nothing", async () => {
  const app = await setup();
  const old = connectTransport(app);
  const channel = app.getChannel("moved");
  let connects = 0;
  channel.on("connect", () => connects++);
  old.close();
  channel.emit("push", { n: 1 });
  // A straggler answering the open the closed socket carried.
  old.receive(["_opened", null, "moved"]);
  assert.equal(channel.connected, false);
  assert.equal(connects, 0);

  // The queued message is owed to the transport the channel attaches to next.
  const socket = connectTransport(app);
  socket.receive(["_opened", null, "moved"]);
  assert.equal(connects, 1);
  assert.deepEqual(socket.sent.slice(1), [
    ["_open", null, "moved"],
    ["push", { n: 1 }, "moved"],
  ]);
});
