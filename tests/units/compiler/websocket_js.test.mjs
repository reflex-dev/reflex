import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(
  new URL(
    "../../../packages/reflex-base/src/reflex_base/.templates/web/utils/helpers/websocket.js",
    import.meta.url,
  ),
  "utf8",
);

/** Evaluate the actual transport module against a scripted browser WebSocket. */
async function setup({ throwOnConstruct = false, closeLater = false } = {}) {
  const sockets = [];
  const timers = new Map();
  const reported = [];

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
  });
  const module = new vm.SourceTextModule(source, { context });
  await module.link(
    () =>
      new vm.SyntheticModule(
        ["parseJson"],
        function () {
          this.setExport("parseJson", JSON.parse);
        },
        { context },
      ),
  );
  await module.evaluate();
  const transport = new module.namespace.ReflexWebSocket(
    "http://localhost:8000/_event",
    { query: { token: "tok" }, protocols: ["version"] },
  );
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
  connectTransport(app);
  const channel = app.getChannel("strict");
  for (const name of [undefined, 42, "", "_open", "_custom", "connect"]) {
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
