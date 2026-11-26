/**
 * The event loop of an app compiled without state (`useLocalEventLoop` in
 * `utils/state.js`): the browser applies frontend events itself, an event for
 * the backend is reported instead of sent, and nothing connects.
 */
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

const io = vi.hoisted(() => vi.fn());
vi.mock("socket.io-client", () => ({ default: io }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let state;
let registry;
let unmount;

beforeEach(async () => {
  vi.resetModules();
  io.mockReset();
  state = await import("$/utils/state");
  registry = await import("$/utils/context-registry");
  // What the context module of an app without state registers.
  registry.registerApp({
    initialState: {},
    clientStorage: {},
    state_name: undefined,
    onLoadInternalEvent: () => [],
    initialEvents: () => [],
  });
});

afterEach(async () => {
  await unmount?.();
  unmount = undefined;
  vi.restoreAllMocks();
  document.body.replaceChildren();
});

/**
 * Mount the local event loop, as the context module's EventLoopProvider does.
 * @param path The route pattern the probe renders under.
 * @param url The URL to start at.
 */
const mountLocalLoop = async (path = "*", url = "/") => {
  const mounted = { renders: [] };
  const Probe = () => {
    const [addEvents, connectErrors] = state.useLocalEventLoop();
    registry.eventLoop.addEvents = addEvents;
    mounted.addEvents = addEvents;
    mounted.renders.push(connectErrors);
    mounted.location = useLocation();
    return null;
  };
  const container = document.body.appendChild(document.createElement("div"));
  const root = createRoot(container);
  await act(async () => {
    root.render(
      createElement(
        MemoryRouter,
        { initialEntries: [url] },
        createElement(
          Routes,
          null,
          createElement(Route, { path, element: createElement(Probe) }),
        ),
      ),
    );
  });
  unmount = () => act(async () => root.unmount());
  return {
    mounted,
    dispatch: (events, args, actions) =>
      act(async () => {
        await mounted.addEvents(events, args, actions);
      }),
  };
};

const call = (fn, callback) => ({
  name: "_call_function",
  payload: { function: fn, callback },
});
const script = (javascript_code, callback) => ({
  name: "_call_script",
  payload: { javascript_code, callback },
});

test("frontend events apply in order and nothing connects", async () => {
  const { mounted, dispatch } = await mountLocalLoop();
  const seen = [];
  await dispatch([
    call(() => seen.push(1)),
    [call(() => seen.push(2)), null],
    call(() => seen.push(3)),
  ]);
  expect(seen).toEqual([1, 2, 3]);
  expect(io).not.toHaveBeenCalled();
  expect(mounted.renders.every((errors) => errors.length === 0)).toBe(true);
  // One array for the life of the loop, so the provider's memo holds.
  expect(new Set(mounted.renders).size).toBe(1);
});

test("a redirect navigates within the app", async () => {
  const { mounted, dispatch } = await mountLocalLoop();
  await dispatch([{ name: "_redirect", payload: { path: "/next?q=1#top" } }]);
  expect(mounted.location.pathname).toBe("/next");
  expect(mounted.location.search).toBe("?q=1");
  expect(mounted.location.hash).toBe("#top");
});

test("a function's result reaches its callback", async () => {
  const { dispatch } = await mountLocalLoop();
  const seen = [];
  await dispatch([
    call(
      async () => 41 + 1,
      (result) => seen.push(result),
    ),
  ]);
  expect(seen).toEqual([42]);
});

test("client state set and read through events", async () => {
  const { dispatch } = await mountLocalLoop();
  const seen = [];
  await dispatch([
    { name: "_client_state_set", payload: { var_name: "count", value: 3 } },
    {
      name: "_client_state_get",
      payload: { var_name: "count", callback: (value) => seen.push(value) },
    },
  ]);
  expect(seen).toEqual([3]);
});

test("scripts see the runtime's exports, addEvents, navigate and params", async () => {
  const { mounted, dispatch } = await mountLocalLoop("/items/:id", "/items/7");
  const seen = [];
  await dispatch([
    script(
      "[typeof addEvents, typeof navigate, params.current.id, typeof ReflexEvent, typeof isTrue]",
      (result) => seen.push(result),
    ),
  ]);
  expect(seen).toEqual([["function", "function", "7", "function", "function"]]);

  await dispatch([script('navigate("/items/8")')]);
  expect(mounted.location.pathname).toBe("/items/8");
});

test("scripts see nothing of the transport", async () => {
  const { dispatch } = await mountLocalLoop();
  const seen = [];
  await dispatch([
    script(
      "[typeof socket, typeof token, typeof connect, typeof getToken, typeof queueEvents]",
      (result) => seen.push(result),
    ),
  ]);
  expect(seen).toEqual([
    ["undefined", "undefined", "undefined", "undefined", "undefined"],
  ]);
});

test("a compiled callback string dispatches through the mounted loop", async () => {
  const { mounted, dispatch } = await mountLocalLoop("/items/:id", "/items/7");
  // What format_queue_events builds for `callback=rx.redirect(...)`.
  await dispatch([
    script(
      "9",
      '(_result) => {addEvents([ReflexEvent("_redirect", {path:"/items/" + _result})])}',
    ),
  ]);
  await act(() => new Promise((done) => setTimeout(done, 0)));
  expect(mounted.location.pathname).toBe("/items/9");
});

test("a splat route's params reach scripts as a list", async () => {
  const { dispatch } = await mountLocalLoop("/files/*", "/files/a/b");
  const seen = [];
  await dispatch([
    script("params.current.splat", (result) => seen.push(result)),
  ]);
  expect(seen).toEqual([["a", "b"]]);
});

test("an event for the backend is reported, and the next event still applies", async () => {
  const error = vi.spyOn(console, "error").mockImplementation(() => {});
  const { dispatch } = await mountLocalLoop();
  const seen = [];
  await dispatch([
    { name: "reflex___state____state.handler", payload: {} },
    {
      name: "reflex___state____state.upload",
      payload: { files: [] },
      handler: "uploadFiles",
    },
    call(() => seen.push("after")),
  ]);
  expect(seen).toEqual(["after"]);
  expect(error).toHaveBeenCalledTimes(2);
  expect(error.mock.calls[0][0]).toContain('"reflex___state____state.handler"');
  expect(error.mock.calls[0][0]).toContain("enable_state=False");
  expect(io).not.toHaveBeenCalled();
});

test("storage events need the backend that keeps them in sync with state", async () => {
  const error = vi.spyOn(console, "error").mockImplementation(() => {});
  localStorage.setItem("kept", "1");
  const { dispatch } = await mountLocalLoop();
  await dispatch([{ name: "_clear_local_storage" }]);
  expect(localStorage.getItem("kept")).toBe("1");
  expect(error.mock.calls[0][0]).toContain('"_clear_local_storage"');
  localStorage.clear();
});

test("event actions apply to the dispatching DOM event", async () => {
  const { dispatch } = await mountLocalLoop();
  const domEvent = { preventDefault: vi.fn(), stopPropagation: vi.fn() };
  const seen = [];
  await dispatch([call(() => seen.push(1))], [domEvent], {
    preventDefault: true,
    stopPropagation: true,
  });
  expect(domEvent.preventDefault).toHaveBeenCalledTimes(1);
  expect(domEvent.stopPropagation).toHaveBeenCalledTimes(1);
  expect(seen).toEqual([1]);
});

test("isFrontendEvent accepts the events the browser applies itself", () => {
  for (const name of [
    "_redirect",
    "_download",
    "_set_focus",
    "_blur_focus",
    "_set_value",
    "_client_state_set",
    "_client_state_get",
    "_call_function",
    "_call_script",
  ]) {
    expect(state.isFrontendEvent({ name })).toBe(true);
  }
  for (const name of [
    "reflex___state____state.handler",
    "_remove_cookie",
    "_clear_local_storage",
    "_sync_local_storage",
  ]) {
    expect(state.isFrontendEvent({ name })).toBe(false);
  }
});
