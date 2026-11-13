/**
 * Server-provided JavaScript (`_call_script`, `_call_function` and their
 * callbacks) runs through a Function-constructor helper, not a direct eval, so
 * the minifier may mangle this module. These pin what the generated strings
 * can see and what the script returns.
 */
import { describe, expect, test, vi } from "vitest";

import { eventLoop } from "$/utils/context-registry";
import { applyEvent } from "$/utils/state";

const callScript = (code, callback) =>
  applyEvent(
    { name: "_call_script", payload: { javascript_code: code, callback } },
    null,
    null,
    null,
  );

describe("_call_script", () => {
  test("returns the completion value of a statement list to the callback", async () => {
    const seen = [];
    await callScript("var x = 20; x + 1", (result) => seen.push(result));
    expect(seen).toEqual([21]);
  });

  test("callback strings dispatch through the late-bound addEvents", async () => {
    eventLoop.addEvents = vi.fn();
    await callScript(
      "42",
      '((_result) => addEvents([ReflexEvent("state.set", {v: _result})], [_result], {}))',
    );
    expect(eventLoop.addEvents).toHaveBeenCalledTimes(1);
    const [events, args] = eventLoop.addEvents.mock.calls[0];
    expect(events[0].name).toBe("state.set");
    expect(events[0].payload).toEqual({ v: 42 });
    expect(args).toEqual([42]);
  });

  test("runs strict and sees no module-local names", async () => {
    const onerror = vi.fn();
    window.onerror = onerror;
    await callScript("undeclared = 1");
    await callScript("socket");
    expect(onerror).toHaveBeenCalledTimes(2);
    expect(onerror.mock.calls[0][4]).toBeInstanceOf(ReferenceError);
    expect(onerror.mock.calls[1][4]).toBeInstanceOf(ReferenceError);
  });

  test("_call_function evaluates a string and calls it", async () => {
    const seen = [];
    await applyEvent(
      {
        name: "_call_function",
        payload: { function: "() => 7", callback: (r) => seen.push(r) },
      },
      null,
      null,
      null,
    );
    expect(seen).toEqual([7]);
  });
});
