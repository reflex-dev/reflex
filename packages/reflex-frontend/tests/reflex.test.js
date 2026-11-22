/**
 * `reflex` is the API scripts reach Reflex through. These pin each member and
 * that it reads the runtime at call time.
 */
import { afterEach, expect, test, vi } from "vitest";

import { eventLoop } from "$/utils/context-registry";
import { reflex } from "$/utils/reflex";
import { refs } from "$/utils/state";

afterEach(() => {
  delete window.__reflex;
  delete window.__reflex_load;
});

test("ref finds a component by id, named as format_ref names it", () => {
  const cases = {
    search: "ref_search",
    "my-input": "ref_my_input",
    "a b..c": "ref_a_b_c",
    "naïve-x": "ref_naïve_x",
  };
  for (const [id, key] of Object.entries(cases)) {
    const ref = { current: id };
    refs[key] = ref;
    expect(reflex.ref(id)).toBe(ref);
    delete refs[key];
  }
  expect(reflex.ref("never-mounted")).toBe(undefined);
});

test("addEvents dispatches through the event loop mounted at call time", () => {
  const first = vi.fn();
  const second = vi.fn();
  eventLoop.addEvents = first;
  expect(reflex.addEvents(["a"])).toBe(undefined);
  eventLoop.addEvents = second;
  reflex.addEvents(["b"]);
  expect(first.mock.calls).toEqual([[["a"]]]);
  expect(second.mock.calls).toEqual([[["b"]]]);
});

test("event builds the event addEvents takes", () => {
  expect(reflex.event("state.my_state.save", { value: 3 })).toEqual({
    name: "state.my_state.save",
    payload: { value: 3 },
  });
  expect(reflex.event("state.my_state.reset")).toEqual({
    name: "state.my_state.reset",
  });
});

test("library loads a lazy library first and returns its module", async () => {
  const confetti = { default: () => "boom" };
  window.__reflex = { react: { version: "19" } };
  window.__reflex_load = vi.fn(async (names) => {
    for (const name of names) {
      window.__reflex[name] ??= confetti;
    }
  });
  await expect(reflex.library("canvas-confetti")).resolves.toBe(confetti);
  expect(window.__reflex_load.mock.calls).toEqual([[["canvas-confetti"]]]);
  await expect(reflex.library("react")).resolves.toEqual({ version: "19" });
});

test("library rejects a module of the app's frontend", async () => {
  window.__reflex = { "$/utils/state": {} };
  window.__reflex_load = vi.fn();
  await expect(reflex.library("$/utils/state")).rejects.toThrow(
    new Error(
      'reflex.library("$/utils/state") cannot load "$/utils/state": a name starting with "$/" is a module of the app\'s frontend, not a bundled npm library. Use reflex.ref, reflex.addEvents and reflex.event instead of Reflex internals, and import your own modules from a JavaScript module.',
    ),
  );
  expect(window.__reflex_load.mock.calls).toEqual([]);
});

test("library called before the app registers its libraries says so", async () => {
  await expect(reflex.library("react")).rejects.toThrow(
    new Error(
      'reflex.library("react") cannot load "react" yet: the app registers its bundled libraries when it first mounts, and it has not mounted. Call reflex.library from an event, such as on_mount or on_click, rather than while a module loads.',
    ),
  );
});

test("library rejects a library the app does not bundle", async () => {
  window.__reflex = {};
  await expect(reflex.library("left-pad")).rejects.toThrow(
    new Error(
      'reflex.library("left-pad") cannot load "left-pad": the app does not bundle it for dynamic components. Bundle it by calling bundle_library("left-pad") from reflex.components.dynamic in your app\'s Python code.',
    ),
  );
});

test("library rejects a name the registry only inherits", async () => {
  window.__reflex = {};
  await expect(reflex.library("constructor")).rejects.toThrow(
    new Error(
      'reflex.library("constructor") cannot load "constructor": the app does not bundle it for dynamic components. Bundle it by calling bundle_library("constructor") from reflex.components.dynamic in your app\'s Python code.',
    ),
  );
});

test("is frozen, so a script cannot replace a member for everyone", () => {
  expect(Object.isFrozen(reflex)).toBe(true);
  expect(Object.keys(reflex)).toEqual(["ref", "addEvents", "event", "library"]);
});

test("loads first, before utils/state, despite the import cycle", async () => {
  vi.resetModules();
  const { reflex: fresh } = await import("$/utils/reflex");
  const state = await import("$/utils/state");
  state.refs.ref_first = { current: 1 };
  expect(fresh.ref("first")).toBe(state.refs.ref_first);
});
