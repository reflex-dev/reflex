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
async function setup() {
  const sockets = [];
  const timers = new Map();

  class WebSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;

    constructor(url, protocols) {
      this.url = String(url);
      this.protocols = protocols;
      this.readyState = WebSocket.CONNECTING;
      this.sent = [];
      sockets.push(this);
    }

    send(frame) {
      assert.equal(this.readyState, WebSocket.OPEN);
      this.sent.push(JSON.parse(frame));
    }

    close() {
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
  return { transport, sockets, timers, events };
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
