// Unit tests for the state runtime. These are only possible because the
// module no longer imports per-app generated artifacts: the runtime registry
// below stands in for the generated context module's configure call.
import { beforeEach, describe, expect, test } from "vitest";

import { configureReflexRuntime } from "@reflex-dev/reflex-base/runtime";
import {
  ReflexEvent,
  applyDelta,
  getBackendURL,
  hydrateClientStorage,
  isNotNullOrUndefined,
  isTrue,
  pyAnd,
  pyFlatMap,
  pyLstrip,
  pyOr,
  pyRstrip,
  pyStrip,
  refs,
  spreadArraysOrObjects,
} from "@reflex-dev/reflex-base/state";

configureReflexRuntime({
  env: {
    EVENT: "http://localhost:8000/_event",
    PING: "http://localhost:8000/ping",
    UPLOAD: "http://localhost:8000/_upload",
    TRANSPORT: "websocket",
  },
  reflexEnvironment: { version: "0.0.0" },
  state_name: "reflex___state____state",
  exception_state_name:
    "reflex___state____state.reflex___state____frontend_event_exception_state",
  initialState: { reflex___state____state: {} },
});

describe("getBackendURL", () => {
  test("rewrites same-domain hostnames onto the frontend host", () => {
    // jsdom serves from http://localhost:3000 by default.
    const url = getBackendURL("http://localhost:8000/_event");
    expect(url.hostname).toBe("localhost");
    expect(url.port).toBe("8000");
    expect(url.pathname).toBe("/_event");
  });

  test("leaves external hostnames untouched", () => {
    const url = getBackendURL("https://api.example.com/_event");
    expect(url.hostname).toBe("api.example.com");
  });

  test("falls back to the configured PING endpoint", () => {
    expect(getBackendURL(undefined).pathname).toBe("/ping");
  });
});

describe("state helpers", () => {
  test("applyDelta merges deltas over state", () => {
    expect(applyDelta({ a: 1, b: 1 }, { b: 2, c: 3 })).toEqual({
      a: 1,
      b: 2,
      c: 3,
    });
  });

  test("refs is a shared mutable registry", () => {
    refs["__test"] = { current: 42 };
    expect(refs["__test"].current).toBe(42);
    delete refs["__test"];
  });

  test("ReflexEvent omits empty payloads and actions", () => {
    expect(ReflexEvent("evt")).toEqual({ name: "evt" });
    expect(
      ReflexEvent("evt", { a: 1 }, { debounce: 5 }, "uploadFiles"),
    ).toEqual({
      name: "evt",
      payload: { a: 1 },
      event_actions: { debounce: 5 },
      handler: "uploadFiles",
    });
  });

  test("spreadArraysOrObjects merges like types and rejects mixes", () => {
    expect(spreadArraysOrObjects([1], [2])).toEqual([1, 2]);
    expect(spreadArraysOrObjects({ a: 1 }, { b: 2 })).toEqual({ a: 1, b: 2 });
    expect(() => spreadArraysOrObjects([1], 2)).toThrow();
  });
});

describe("python semantics shims", () => {
  test("isTrue follows python truthiness", () => {
    expect(isTrue([])).toBe(false);
    expect(isTrue([0])).toBe(true);
    expect(isTrue({})).toBe(false);
    expect(isTrue({ a: 1 })).toBe(true);
    expect(isTrue("")).toBe(false);
    expect(isTrue(0)).toBe(false);
    expect(isTrue("x")).toBe(true);
  });

  test("isNotNullOrUndefined", () => {
    expect(isNotNullOrUndefined(null)).toBe(false);
    expect(isNotNullOrUndefined(undefined)).toBe(false);
    expect(isNotNullOrUndefined(0)).toBe(true);
    expect(isNotNullOrUndefined("")).toBe(true);
  });

  test("pyOr and pyAnd short-circuit through thunks", () => {
    expect(pyOr([], () => "fallback")).toBe("fallback");
    expect(pyOr([1], () => "fallback")).toEqual([1]);
    expect(pyAnd([], () => "next")).toEqual([]);
    expect(pyAnd([1], () => "next")).toBe("next");
    let evaluated = false;
    pyOr([1], () => {
      evaluated = true;
    });
    expect(evaluated).toBe(false);
  });

  test("py strip family matches python str.strip semantics", () => {
    expect(pyStrip("  x  ")).toBe("x");
    expect(pyLstrip("xxabcxx", "x")).toBe("abcxx");
    expect(pyRstrip("xxabcxx", "x")).toBe("xxabc");
    expect(pyStrip("xyabcyx", "xy")).toBe("abc");
    // Surrogate pairs are stripped as whole code points.
    expect(pyStrip("\u{1F600}a\u{1F600}", "\u{1F600}")).toBe("a");
  });

  test("pyFlatMap iterates values the way python does", () => {
    expect(pyFlatMap([1, 2], (x) => [x, x])).toEqual([1, 1, 2, 2]);
    expect(pyFlatMap(["ab"], (s) => s)).toEqual(["a", "b"]);
    expect(pyFlatMap([{ a: 1, b: 2 }], (o) => o)).toEqual(["a", "b"]);
    expect(() => pyFlatMap([1], (x) => x)).toThrow(TypeError);
  });
});

describe("hydrateClientStorage", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  test("returns empty when nothing is tracked", () => {
    expect(hydrateClientStorage({})).toEqual({});
  });

  test("collects only browser-populated values", () => {
    localStorage.setItem("my_key", "stored");
    sessionStorage.setItem("state.session_value", "sess");
    const client_storage = {
      local_storage: {
        "state.local_value": { name: "my_key" },
        "state.absent_value": {},
      },
      session_storage: {
        "state.session_value": {},
      },
    };
    expect(hydrateClientStorage(client_storage)).toEqual({
      "state.local_value": "stored",
      "state.session_value": "sess",
    });
  });

  test("reads cookies without parsing", () => {
    document.cookie = "state.cookie_value=chocolate";
    const values = hydrateClientStorage({
      cookies: { "state.cookie_value": {} },
    });
    expect(values["state.cookie_value"]).toBe("chocolate");
  });
});
