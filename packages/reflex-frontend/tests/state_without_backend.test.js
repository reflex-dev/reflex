/**
 * `utils/state.js` in an app without state, whose compiled context module
 * never imports `utils/socket.js`: the connection to the backend, socket.io
 * and the cookie library stay out of the bundle, and what the browser can do
 * by itself still works.
 *
 * The backend registry is module state, so every test loads fresh modules.
 */
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

// Each factory runs when its module is first imported, and not before.
const loaded = vi.hoisted(() => []);
vi.mock("socket.io-client", () => {
  loaded.push("socket.io-client");
  return { default: vi.fn() };
});
vi.mock("universal-cookie", () => {
  loaded.push("universal-cookie");
  return { default: class {} };
});

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let state;

beforeEach(async () => {
  vi.resetModules();
  loaded.length = 0;
  state = await import("$/utils/state");
  const registry = await import("$/utils/context-registry");
  // What the context module of an app without state registers.
  registry.registerApp({
    initialState: {},
    clientStorage: {},
    initialEvents: () => [],
    onLoadInternalEvent: () => [],
    isDevMode: false,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  document.body.replaceChildren();
});

/** Mount a component running the event loop, as the app's root layout does. */
const mountEventLoop = async () => {
  const mounted = {};
  const Probe = () => {
    [mounted.addEvents, mounted.connectErrors] = state.useEventLoop({});
    mounted.location = useLocation();
    return null;
  };
  const root = createRoot(
    document.body.appendChild(document.createElement("div")),
  );
  await act(async () => {
    root.render(createElement(MemoryRouter, null, createElement(Probe)));
  });
  return {
    mounted,
    addEvents: (...args) => act(async () => mounted.addEvents(...args)),
    unmount: () => act(async () => root.unmount()),
  };
};

test("loading utils/state.js loads neither socket.io nor the cookie library", async () => {
  const { backend } = await import("$/utils/event_loop");
  expect(loaded).toEqual([]);
  expect(backend).toEqual({});
});

test("loading utils/socket.js registers the connection with utils/state.js", async () => {
  const socket = await import("$/utils/socket");
  const { backend } = await import("$/utils/event_loop");
  expect(loaded.sort()).toEqual(["socket.io-client", "universal-cookie"]);
  expect(Object.keys(backend).sort()).toEqual([
    "connect",
    "getToken",
    "hydrateClientStorage",
    "sendEvent",
    "useEventLoop",
    "waitForSession",
  ]);
  expect(backend.connect).toBe(socket.connect);
  expect(backend.useEventLoop).toBe(socket.useEventLoop);
});

test("the event loop runs browser events without a backend", async () => {
  const loop = await mountEventLoop();
  const called = [];

  await loop.addEvents([
    state.ReflexEvent("_call_function", { function: () => called.push("fn") }),
    state.ReflexEvent("_call_script", {
      javascript_code: "[typeof socket, typeof token, isTrue([])]",
      callback: (result) => called.push(result),
    }),
    state.ReflexEvent("_redirect", { path: "/other?x=1" }),
  ]);

  expect(called).toEqual(["fn", ["object", "undefined", false]]);
  expect(loop.mounted.location.pathname + loop.mounted.location.search).toBe(
    "/other?x=1",
  );
  expect(loop.mounted.connectErrors).toEqual([]);
  expect(state.isStateful()).toBe(false);
  expect(loaded).toEqual([]);
  await loop.unmount();
});

test("the event loop keeps one addEvents and one connectErrors across renders", async () => {
  const loop = await mountEventLoop();
  const { addEvents, connectErrors } = loop.mounted;
  await loop.addEvents([state.ReflexEvent("_redirect", { path: "/again" })]);
  expect(loop.mounted.location.pathname).toBe("/again");
  expect(loop.mounted.addEvents).toBe(addEvents);
  expect(loop.mounted.connectErrors).toBe(connectErrors);
  await loop.unmount();
});

test("event actions apply, and a temporal event is dropped", async () => {
  const loop = await mountEventLoop();
  const called = [];
  const dom_event = { preventDefault: vi.fn(), stopPropagation: vi.fn() };

  await loop.addEvents(
    [
      state.ReflexEvent(
        "_call_function",
        { function: () => called.push("kept") },
        { preventDefault: true },
      ),
    ],
    [dom_event],
    { stopPropagation: true },
  );
  await loop.addEvents(
    [state.ReflexEvent("_call_function", { function: () => called.push(1) })],
    [],
    { temporal: true },
  );

  expect(called).toEqual(["kept"]);
  expect(dom_event.preventDefault).toHaveBeenCalledTimes(1);
  expect(dom_event.stopPropagation).toHaveBeenCalledTimes(1);
  await loop.unmount();
});

test("an event for the backend is dropped rather than sent", async () => {
  const loop = await mountEventLoop();
  const called = [];
  await loop.addEvents([
    state.ReflexEvent("some_state.handler", { value: 1 }),
    state.ReflexEvent("_call_function", {
      function: () => called.push("after"),
    }),
  ]);
  expect(called).toEqual(["after"]);
  await loop.unmount();
});

test("_remove_cookie expires the cookie with the options it was set with", async () => {
  document.cookie = "kept=1; path=/";
  document.cookie = "gone=1; path=/";
  const written = vi.spyOn(document, "cookie", "set");

  await state.applyEvent(
    state.ReflexEvent("_remove_cookie", {
      key: "gone",
      options: { path: "/" },
    }),
    null,
    null,
    null,
  );
  await state.applyEvent(
    state.ReflexEvent("_remove_cookie", {
      key: "scoped",
      options: {
        path: "/app",
        domain: "example.com",
        secure: true,
        partitioned: true,
        sameSite: "none",
      },
    }),
    null,
    null,
    null,
  );

  expect(written.mock.calls).toEqual([
    ["gone=; Max-Age=0; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT"],
    [
      "scoped=; Max-Age=0; Domain=example.com; Path=/app; " +
        "Expires=Thu, 01 Jan 1970 00:00:00 GMT; Secure; Partitioned; SameSite=None",
    ],
  ]);
  written.mockRestore();
  expect(document.cookie).toBe("kept=1");
  expect(loaded).toEqual([]);
});

test("the names that need the backend say so, or answer for an app without one", async () => {
  expect(state.getToken()).toBe("");
  await expect(state.waitForSession()).resolves.toBeUndefined();
  expect(() => state.hydrateClientStorage({})).toThrow(
    new Error(
      "hydrateClientStorage needs the connection to the backend, which an app without state does not load.",
    ),
  );
  expect(() => state.connect({ current: null })).toThrow(
    new Error(
      "connect needs the connection to the backend, which an app without state does not load.",
    ),
  );
});

test("with utils/socket.js loaded, the same names reach the connection", async () => {
  sessionStorage.setItem("token", "stored-token");
  await import("$/utils/socket");
  expect(state.getToken()).toBe("stored-token");
  expect(state.hydrateClientStorage({})).toEqual({});
  sessionStorage.clear();
});
