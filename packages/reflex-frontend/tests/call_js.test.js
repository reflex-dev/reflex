/**
 * `_call_js` calls an exported function of a JavaScript module an app imports
 * from Python. utils/scripts.js maps each module's Python name to a function
 * that loads it, so the event carries only names and JSON arguments, and
 * nothing is evaluated.
 */
import { afterEach, beforeAll, expect, test, vi } from "vitest";

import { applyEvent, eventActionKey, queueEvents } from "$/utils/state";

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
  let answer = () => {};
  const answered = new Promise((resolve) => {
    answer = resolve;
  });
  let releaseAsking = () => {};
  const askingLoaded = new Promise((resolve) => {
    releaseAsking = resolve;
  });
  let answerLate = () => {};
  const answeredLate = new Promise((resolve) => {
    answerLate = resolve;
  });
  let releaseHanging = () => {};
  const hangingLoaded = new Promise((resolve) => {
    releaseHanging = resolve;
  });
  let releaseDirect = () => {};
  const directLoaded = new Promise((resolve) => {
    releaseDirect = resolve;
  });
  return {
    releaseDirect,
    directLoaded,
    seen: [],
    answer,
    answered,
    releaseAsking,
    askingLoaded,
    answerLate,
    answeredLate,
    releaseHanging,
    hangingLoaded,
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
      write: (value) => {
        globalThis.partyValue = value;
      },
      ask: () =>
        modules.answered.then((answer) =>
          modules.seen.push(["answered", answer]),
        ),
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
    "app.scripts.asking": () =>
      modules.askingLoaded.then(() => ({
        ask: () => {
          modules.seen.push(["asked"]);
          return modules.answeredLate.then((answer) =>
            modules.seen.push(["answered", answer]),
          );
        },
      })),
    "app.scripts.hanging": () =>
      modules.hangingLoaded.then(() => ({
        wait: () => {
          modules.seen.push(["waiting"]);
          return new Promise(() => {});
        },
      })),
    "app.scripts.direct": () =>
      modules.directLoaded.then(() => ({
        ping: (value) => modules.seen.push(["direct", value]),
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

test("a function's promise does not hold back the events after it", async () => {
  // As a script's does not: it can wait on the user, as for the answer to a
  // dialog, and the app keeps handling events meanwhile, even those queued
  // with the call.
  globalThis.reads = [];
  const socket = { connected: true, emit: vi.fn() };
  await queueEvents(
    [
      callJsEvent("app.scripts.party", "ask", []),
      {
        name: "_call_script",
        payload: { javascript_code: "reads.push('next')" },
      },
    ],
    socket,
    false,
    null,
    null,
  );
  expect(globalThis.reads).toEqual(["next"]);
  expect(modules.seen).toEqual([]);
  modules.answer("yes");
  await vi.waitFor(() => expect(modules.seen).toEqual([["answered", "yes"]]));
});

test("a promise that never settles does not hold back the events after it, though its module was loading", async () => {
  globalThis.reads = [];
  const socket = { connected: true, emit: vi.fn() };
  const queued = queueEvents(
    [
      callJsEvent("app.scripts.hanging", "wait", []),
      {
        name: "_call_script",
        payload: { javascript_code: "reads.push('next')" },
      },
    ],
    socket,
    false,
    null,
    null,
  );
  modules.releaseHanging();
  await queued;
  expect(globalThis.reads).toEqual(["next"]);
  expect(modules.seen).toEqual([["waiting"]]);
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

test("a function of a module that was loading holds back later events only until it runs", async () => {
  // The events after it wait for the function to run, as they would had the
  // module loaded, but not for the promise it returns.
  globalThis.reads = [];
  const socket = { connected: true, emit: vi.fn() };
  const asking = queueEvents(
    [callJsEvent("app.scripts.asking", "ask", [])],
    socket,
    false,
    null,
    null,
  );
  const next = queueEvents(
    [
      {
        name: "_call_script",
        payload: { javascript_code: "reads.push('next')" },
      },
    ],
    socket,
    false,
    null,
    null,
  );
  modules.releaseAsking();
  await next;
  expect(globalThis.reads).toEqual(["next"]);
  expect(modules.seen).toEqual([["asked"]]);
  modules.answerLate("yes");
  await asking;
  expect(modules.seen).toEqual([["asked"], ["answered", "yes"]]);
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
  const socket = { connected: true, emit: vi.fn() };
  const call = queueEvents(
    [callJsEvent("app.scripts.slow", "ping", ["late"])],
    socket,
    false,
    null,
    null,
  );
  await Promise.resolve();
  expect(modules.seen).toEqual([]);
  modules.releaseSlow();
  await call;
  expect(modules.seen).toEqual([["ping", "late"]]);
});

test("applyEvent called directly waits for a module still loading", async () => {
  // processEvent waits for the load itself; applyEvent is exported, and a
  // caller that does not wait must not get an error for the unloaded module.
  const onerror = vi.fn();
  window.onerror = onerror;
  const call = callJs("app.scripts.direct", "ping", ["direct"]);
  await Promise.resolve();
  expect(modules.seen).toEqual([]);
  modules.releaseDirect();
  await call;
  expect(modules.seen).toEqual([["direct", "direct"]]);
  expect(onerror.mock.calls).toEqual([]);
});

test("reports a missing module, function or non-function export", async () => {
  const onerror = vi.fn();
  window.onerror = onerror;
  await callJs("app.scripts.party", "missing", []);
  await callJs("app.scripts.party", "notAFunction", []);
  await callJs("app.other", "celebrate", []);
  const reported = (message) => [
    message,
    null,
    null,
    null,
    new TypeError(message),
  ];
  const notExported = (name) =>
    reported(
      `Cannot call app.scripts.party.${name}: the JavaScript module app.scripts.party exports no function named ${name}. Export a function named ${name} from it, or correct the name in Python.`,
    );
  expect(onerror.mock.calls).toEqual([
    notExported("missing"),
    notExported("notAFunction"),
    reported(
      "Cannot call app.other.celebrate: the frontend does not include the JavaScript module app.other, as when Python first imports it inside an event handler, after the app compiled. Import it at the top of a Python module that the app imports when it loads.",
    ),
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

test("each module function keeps its own debounce and throttle key", () => {
  const call = (module, fn) => ({
    name: "_call_js",
    payload: { module, function: fn, args: [] },
  });
  expect(
    [
      [call("app.scripts.party", "celebrate")],
      [call("app.scripts.party", "flash")],
      [call("app.scripts.page", "celebrate")],
      [call("app.scripts.party", "celebrate"), { name: "state.handler" }],
    ].map(eventActionKey),
  ).toEqual([
    "_call_js:app.scripts.party:celebrate",
    "_call_js:app.scripts.party:flash",
    "_call_js:app.scripts.page:celebrate",
    "_call_js:app.scripts.party:celebrate+++state.handler",
  ]);
});
