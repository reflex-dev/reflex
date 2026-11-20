/**
 * `_call_js` calls an exported function of a JavaScript module an app imports
 * from Python. The modules are bundled and re-exported by utils/scripts.js, so
 * the event carries only names and JSON arguments, and nothing is evaluated.
 */
import { afterEach, expect, test, vi } from "vitest";

import { applyEvent } from "$/utils/state";

const seen = [];

vi.mock("$/utils/scripts", () => ({
  app$scripts$party: {
    celebrate: (count, id) => seen.push(["celebrate", count, id]),
    later: async (value) => {
      await Promise.resolve();
      seen.push(["later", value]);
    },
    notAFunction: 3,
  },
}));

afterEach(() => {
  seen.length = 0;
  window.onerror = null;
});

const callJs = (module, fn, args) =>
  applyEvent(
    { name: "_call_js", payload: { module, function: fn, args } },
    null,
    null,
    null,
  );

test("calls the named function with the arguments", async () => {
  await callJs("app$scripts$party", "celebrate", [200, "results"]);
  expect(seen).toEqual([["celebrate", 200, "results"]]);
});

test("waits for an async function before the next event", async () => {
  await callJs("app$scripts$party", "later", ["done"]);
  expect(seen).toEqual([["later", "done"]]);
});

test("reports a missing module, function or non-function export", async () => {
  const onerror = vi.fn();
  window.onerror = onerror;
  await callJs("app$scripts$party", "missing", []);
  await callJs("app$scripts$party", "notAFunction", []);
  await callJs("app$other", "celebrate", []);
  expect(onerror.mock.calls.map((call) => [call[0], call[4].name])).toEqual([
    [
      "app.scripts.party.missing is not a function exported by a JavaScript module this app imports.",
      "TypeError",
    ],
    [
      "app.scripts.party.notAFunction is not a function exported by a JavaScript module this app imports.",
      "TypeError",
    ],
    [
      "app.other.celebrate is not a function exported by a JavaScript module this app imports.",
      "TypeError",
    ],
  ]);
  expect(seen).toEqual([]);
});

test("a function that throws is reported, not raised", async () => {
  const onerror = vi.fn();
  window.onerror = onerror;
  await callJs("app$scripts$party", "celebrate", null);
  expect(onerror).toHaveBeenCalledTimes(1);
  expect(onerror.mock.calls[0][4]).toBeInstanceOf(TypeError);
});
