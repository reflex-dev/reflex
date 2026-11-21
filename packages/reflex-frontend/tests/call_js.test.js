/**
 * `_call_js` calls an exported function of a JavaScript module an app imports
 * from Python. utils/scripts.js maps each module's Python name to a function
 * that loads it, so the event carries only names and JSON arguments, and
 * nothing is evaluated.
 */
import { afterEach, beforeAll, expect, test, vi } from "vitest";

import { applyEvent, queueEvents } from "$/utils/state";

const modules = vi.hoisted(() => {
  let releaseSlow = () => {};
  const slowLoaded = new Promise((resolve) => {
    releaseSlow = resolve;
  });
  let releaseGated = () => {};
  const gatedLoaded = new Promise((resolve) => {
    releaseGated = resolve;
  });
  let releaseFirst = () => {};
  const firstLoaded = new Promise((resolve) => {
    releaseFirst = resolve;
  });
  let releaseSecond = () => {};
  const secondLoaded = new Promise((resolve) => {
    releaseSecond = resolve;
  });
  return {
    seen: [],
    releaseSlow,
    slowLoaded,
    releaseGated,
    gatedLoaded,
    releaseFirst,
    firstLoaded,
    releaseSecond,
    secondLoaded,
  };
});

vi.mock("$/utils/scripts", () => ({
  default: {
    "app.scripts.party": async () => ({
      celebrate: (count, id) => modules.seen.push(["celebrate", count, id]),
      later: async (value) => {
        await Promise.resolve();
        modules.seen.push(["later", value]);
      },
      write: (value) => {
        globalThis.partyValue = value;
      },
      fails: () => {
        throw new RangeError("The party is over.");
      },
      notAFunction: 3,
    }),
    "app.scripts.slow": () =>
      modules.slowLoaded.then(() => ({
        ping: (value) => modules.seen.push(["ping", value]),
      })),
    "app.scripts.gated": () =>
      modules.gatedLoaded.then(() => ({
        write: (value) => {
          globalThis.gatedValue = value;
        },
      })),
    "app.scripts.first": () =>
      modules.firstLoaded.then(() => ({
        write: (value) => {
          globalThis.firstValue = value;
        },
      })),
    "app.scripts.second": () =>
      modules.secondLoaded.then(() => ({
        write: (value) => {
          globalThis.secondValue = value;
        },
      })),
    "app.scripts.broken": () =>
      Promise.reject(new Error("Failed to fetch the module.")),
  },
}));

beforeAll(async () => {
  // Let the loads state.js starts on import settle.
  await new Promise((resolve) => setTimeout(resolve));
});

afterEach(() => {
  modules.seen.length = 0;
  window.onerror = null;
});

const callJsEvent = (module, fn, args) => ({
  name: "_call_js",
  payload: { module, function: fn, args },
});

const callJs = (module, fn, args) =>
  applyEvent(callJsEvent(module, fn, args), null, null, null);

test("calls the named function with the arguments", async () => {
  await callJs("app.scripts.party", "celebrate", [200, "results"]);
  expect(modules.seen).toEqual([["celebrate", 200, "results"]]);
});

test("waits for an async function before the next event", async () => {
  await callJs("app.scripts.party", "later", ["done"]);
  expect(modules.seen).toEqual([["later", "done"]]);
});

test("the next event sees what a function did, though events overlap", async () => {
  // processEvent starts an event that arrives while another awaits, so the
  // function must run before _call_js awaits anything.
  globalThis.reads = [];
  const socket = { connected: true, emit: vi.fn() };
  const first = queueEvents(
    [callJsEvent("app.scripts.party", "write", ["new"])],
    socket,
    false,
    null,
    null,
  );
  const second = queueEvents(
    [
      {
        name: "_call_script",
        payload: { javascript_code: "reads.push(partyValue)" },
      },
    ],
    socket,
    false,
    null,
    null,
  );
  await Promise.all([first, second]);
  expect(globalThis.reads).toEqual(["new"]);
});

test("an event queued while the modules load runs after the function before it", async () => {
  // Until the modules the page loads have settled, events wait for them in
  // the order they arrived, so the script still sees what the function did.
  globalThis.reads = [];
  const socket = { connected: true, emit: vi.fn() };
  const first = queueEvents(
    [callJsEvent("app.scripts.gated", "write", ["gated"])],
    socket,
    false,
    null,
    null,
  );
  const second = queueEvents(
    [
      {
        name: "_call_script",
        payload: { javascript_code: "reads.push(globalThis.gatedValue)" },
      },
    ],
    socket,
    false,
    null,
    null,
  );
  modules.releaseGated();
  await Promise.all([first, second]);
  expect(globalThis.reads).toEqual(["gated"]);
});

test("an event waits for each module call before it, not only the first", async () => {
  // The second call starts waiting for its module only once the first has run,
  // and the script queued after both must wait for it too.
  globalThis.reads = [];
  const socket = { connected: true, emit: vi.fn() };
  const queued = [
    [callJsEvent("app.scripts.first", "write", ["first"])],
    [callJsEvent("app.scripts.second", "write", ["second"])],
    [
      {
        name: "_call_script",
        payload: {
          javascript_code:
            "reads.push([globalThis.firstValue, globalThis.secondValue])",
        },
      },
    ],
  ].map((events) => queueEvents(events, socket, false, null, null));
  modules.releaseFirst();
  await new Promise((resolve) => setTimeout(resolve));
  modules.releaseSecond();
  await Promise.all(queued);
  expect(globalThis.reads).toEqual([["first", "second"]]);
});

test("a function of a module still loading runs once it has loaded", async () => {
  const call = callJs("app.scripts.slow", "ping", ["late"]);
  await Promise.resolve();
  expect(modules.seen).toEqual([]);
  modules.releaseSlow();
  await call;
  expect(modules.seen).toEqual([["ping", "late"]]);
});

test("reports a missing module, function or non-function export", async () => {
  const onerror = vi.fn();
  window.onerror = onerror;
  await callJs("app.scripts.party", "missing", []);
  await callJs("app.scripts.party", "notAFunction", []);
  await callJs("app.other", "celebrate", []);
  const reported = (module, name) => {
    const message = `Cannot call ${module}.${name}: the frontend has no function ${name} in the JavaScript module ${module}. Either the module does not export a function of that name, or the frontend was built before the backend imported it. Export a function named ${name} from the module, or restart \`reflex run\` to rebuild the frontend.`;
    return [message, null, null, null, new TypeError(message)];
  };
  expect(onerror.mock.calls).toEqual([
    reported("app.scripts.party", "missing"),
    reported("app.scripts.party", "notAFunction"),
    reported("app.other", "celebrate"),
  ]);
  expect(modules.seen).toEqual([]);
});

test("a function that throws, or a module that fails to load, is reported", async () => {
  const onerror = vi.fn();
  window.onerror = onerror;
  await callJs("app.scripts.party", "fails", []);
  await callJs("app.scripts.broken", "anything", []);
  expect(onerror.mock.calls).toEqual([
    [
      "The party is over.",
      null,
      null,
      null,
      new RangeError("The party is over."),
    ],
    [
      "Failed to fetch the module.",
      null,
      null,
      null,
      new Error("Failed to fetch the module."),
    ],
  ]);
});
