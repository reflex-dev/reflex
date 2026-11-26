/**
 * `reflex` is the API scripts reach Reflex through. These pin each member and
 * that it reads the runtime at call time.
 */
import { expect, test, vi } from "vitest";

import { eventLoop } from "$/utils/context-registry";
import { reflex } from "$/utils/reflex";
import { refs } from "$/utils/state";

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
  // A script gets the name from Python, here as
  // f"{SearchState.get_full_name()}.save" builds it for a state in __main__.
  const save = "reflex___state____state.__main______search_state.save";
  expect(reflex.event(save, { value: 3 })).toEqual({
    name: save,
    payload: { value: 3 },
  });
  expect(reflex.event(save)).toEqual({ name: save });
});

test("is frozen, so a script cannot replace a member for everyone", () => {
  expect(Object.isFrozen(reflex)).toBe(true);
  expect(Object.keys(reflex)).toEqual(["ref", "addEvents", "event"]);
});

test("loads first, before utils/state, despite the import cycle", async () => {
  vi.resetModules();
  const { reflex: fresh } = await import("$/utils/reflex");
  const state = await import("$/utils/state");
  state.refs.ref_first = { current: 1 };
  expect(fresh.ref("first")).toBe(state.refs.ref_first);
});
