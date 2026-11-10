/**
 * The connection lifecycle of `utils/state.js`, with the socket replaced by a
 * fake the test drives: what happens to queued events when the connection
 * drops at an awkward moment, and what a torn-down event loop leaves behind.
 *
 * `state.js` keeps its event queue, token and socket bookkeeping in module
 * scope, so every test loads a fresh copy of the module.
 */
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

const io = vi.hoisted(() => vi.fn());
vi.mock("socket.io-client", () => ({ default: io }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// How often a drain may ask whether the socket is connected before the fake
// declares it stuck. A real drain asks a handful of times.
const SPIN_LIMIT = 2000;

/**
 * Stand in for a socket.io socket.
 *
 * A drain that polls a disconnected socket without yielding never returns to
 * the event loop, so it would hang the test run rather than fail a test. The
 * fake breaks such a loop by reconnecting, and records that it had to.
 */
const fakeSocket = (_url, opts) => {
  const handlers = new Map();
  let connected = false;
  let reads = 0;
  const socket = {
    spun: false,
    get connected() {
      if (++reads > SPIN_LIMIT) {
        socket.spun = true;
        connected = true;
      }
      return connected;
    },
    set connected(value) {
      connected = value;
      reads = 0;
    },
    io: {
      opts,
      encoder: { encode: () => [""] },
      decoder: {},
      open: vi.fn(),
    },
    on: (name, handler) => handlers.set(name, handler),
    off: () => handlers.clear(),
    emit: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    trigger: (name, ...args) => handlers.get(name)(...args),
  };
  return socket;
};

const deferred = () => {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
};

// A frontend event that waits on a promise before the queue moves on, as an
// awaited `rx.call_script` or `rx.call_function` does.
const waiting = (gate) => ({
  name: "_call_function",
  payload: { function: () => gate.promise, callback: () => {} },
});
const stateful = { name: "reflex___state____state.handler" };

const sent = (socket) =>
  socket.emit.mock.calls
    .filter(([name]) => name === "event")
    .map(([, event]) => event.name);

const navigate = () => {};
const params = { current: {} };

let state;
let registry;

beforeEach(async () => {
  vi.resetModules();
  io.mockReset().mockImplementation(fakeSocket);
  sessionStorage.clear();
  state = await import("$/utils/state");
  registry = await import("$/utils/context-registry");
  // Let the import's speculative transport warmup see an app without state,
  // then give it one: an app with a single substate never connects.
  await Promise.resolve();
  registry.registerApp({
    initialState: { reflex___state____state: {}, other: {} },
    initialEvents: () => [],
    onLoadInternalEvent: () => [],
    on_load_internal_event: "on_load_internal",
    state_name: "reflex___state____state",
    exception_state_name: "reflex___state____frontend_event_exception_state",
    stateSchema: "schema",
    clientStorage: {},
  });
});

afterEach(() => {
  document.body.replaceChildren();
});

/** Connect a socket the way the mounted event loop does. */
const connectSocket = async () => {
  const socketRef = { current: null };
  await state.connect(
    socketRef,
    {},
    ["websocket"],
    () => {},
    {},
    navigate,
    params,
  );
  return socketRef;
};

/** Mount a component running the event loop, as the app's root layout does. */
const mountEventLoop = async () => {
  const mounted = {};
  const Probe = () => {
    [mounted.addEvents] = state.useEventLoop({});
    return null;
  };
  const container = document.body.appendChild(document.createElement("div"));
  const root = createRoot(container);
  const render = () =>
    act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(Probe)));
    });
  await render();
  return {
    ...mounted,
    socket: io.mock.results[0].value,
    render,
    unmount: () => act(async () => root.unmount()),
  };
};

test("a connection lost while the connect handler drains leaves the rest queued", async () => {
  const socketRef = await connectSocket();
  const socket = socketRef.current;
  const gate = deferred();
  // Queued offline: a stateful event holds the whole queue until the connect.
  await state.queueEvents(
    [waiting(gate), stateful],
    socketRef,
    false,
    navigate,
    params,
  );

  socket.connected = true;
  const drained = socket.trigger("connect");
  socket.connected = false;
  gate.resolve();
  await drained;

  expect(socket.spun).toBe(false);
  expect(sent(socket)).toEqual([]);
  expect(state.isStateful()).toBe(true);
});

test("the stateful event left queued is sent on the next connect", async () => {
  const socketRef = await connectSocket();
  const socket = socketRef.current;
  const gate = deferred();
  await state.queueEvents(
    [waiting(gate), stateful],
    socketRef,
    false,
    navigate,
    params,
  );
  socket.connected = true;
  const drained = socket.trigger("connect");
  socket.connected = false;
  gate.resolve();
  await drained;

  socket.connected = true;
  await socket.trigger("connect");

  expect(sent(socket)).toEqual([stateful.name]);
  expect(state.isStateful()).toBe(false);
});

test("a connection lost while the mounted loop drains leaves the rest queued", async () => {
  const loop = await mountEventLoop();
  const { socket } = loop;
  socket.connected = true;
  await act(async () => socket.trigger("connect"));

  // The drain addEvents starts waits on the first event. Each render while it
  // waits starts a drain of the loop's own, which takes the next one. There
  // are more waiting events than renders, so the stateful event stays queued.
  const gates = Array.from({ length: 8 }, deferred);
  await act(async () => {
    loop.addEvents([...gates.map(waiting), stateful]);
  });
  await loop.render();
  expect(sent(socket)).toEqual([]);

  socket.connected = false;
  await act(async () => {
    for (const gate of gates) gate.resolve();
  });
  // A macrotask only runs once every drain has let go of the event loop.
  await act(() => new Promise((done) => setTimeout(done, 0)));

  expect(socket.spun).toBe(false);
  expect(sent(socket)).toEqual([]);
  expect(state.isStateful()).toBe(true);
  await loop.unmount();
});

test("an unmounted event loop is not reconnected when the page becomes visible", async () => {
  const loop = await mountEventLoop();
  expect(io).toHaveBeenCalledTimes(1);
  await loop.unmount();

  document.dispatchEvent(new Event("visibilitychange"));
  await Promise.resolve();

  expect(document.visibilityState).toBe("visible");
  expect(io).toHaveBeenCalledTimes(1);
});

test("a mounted event loop reconnects its socket when the page becomes visible", async () => {
  const loop = await mountEventLoop();
  const { socket } = loop;
  socket.connected = true;
  await act(async () => socket.trigger("connect"));
  socket.connect.mockClear();

  socket.connected = false;
  document.dispatchEvent(new Event("visibilitychange"));

  expect(socket.connect).toHaveBeenCalledTimes(1);
  expect(io).toHaveBeenCalledTimes(1);
  await loop.unmount();
});
