/**
 * The script environment is the API scripts reach Reflex through. These pin
 * each member, that it reads the runtime at call time, and that
 * `rx.call_script` code sees it under both of its names.
 */
import { afterEach, describe, expect, test, vi } from "vitest";

import { eventLoop } from "$/utils/context-registry";
import { env } from "$/utils/script_env";
import { applyEvent, refs } from "$/utils/state";

afterEach(() => {
  delete window.__reflex;
  delete window.__reflex_load;
});

describe("env", () => {
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
      expect(env.ref(id)).toBe(ref);
      delete refs[key];
    }
    expect(env.ref("never-mounted")).toBe(undefined);
  });

  test("refs is the registry itself", () => {
    expect(env.refs).toBe(refs);
  });

  test("addEvents dispatches through the event loop mounted at call time", () => {
    const first = vi.fn();
    const second = vi.fn();
    eventLoop.addEvents = first;
    env.addEvents(["a"]);
    eventLoop.addEvents = second;
    env.addEvents(["b"], [1], { preventDefault: true });
    expect(first.mock.calls).toEqual([[["a"], [], {}]]);
    expect(second.mock.calls).toEqual([[["b"], [1], { preventDefault: true }]]);
  });

  test("event builds the event addEvents takes", () => {
    expect(env.event("state.my_state.save", { value: 3 })).toEqual({
      name: "state.my_state.save",
      payload: { value: 3 },
    });
    expect(env.event("state.my_state.reset")).toEqual({
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
    await expect(env.library("canvas-confetti")).resolves.toBe(confetti);
    expect(window.__reflex_load.mock.calls).toEqual([[["canvas-confetti"]]]);
    await expect(env.library("react")).resolves.toEqual({ version: "19" });
  });

  test("library rejects a library the app does not bundle", async () => {
    window.__reflex = {};
    await expect(env.library("left-pad")).rejects.toThrow(
      new Error("left-pad is not a bundled library of this app."),
    );
  });

  test("is frozen, so a script cannot replace a member for everyone", () => {
    expect(() => {
      env.addEvents = () => {};
    }).toThrow(TypeError);
  });
});

test("rx.call_script code sees env as env and as __reflexEnv", async () => {
  const seen = [];
  await applyEvent(
    {
      name: "_call_script",
      payload: {
        javascript_code: "[env === __reflexEnv, env.refs === refs]",
        callback: (result) => seen.push(result),
      },
    },
    null,
    null,
    null,
  );
  expect(seen).toEqual([[true, true]]);
});

test("loads first, before utils/state, despite the import cycle", async () => {
  vi.resetModules();
  const { env: fresh } = await import("$/utils/script_env");
  const state = await import("$/utils/state");
  state.refs.ref_first = { current: 1 };
  expect(fresh.ref("first")).toBe(state.refs.ref_first);
});
