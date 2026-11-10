/**
 * `utils/state.js` imported as an app imports it, with its real dependencies.
 *
 * These cover the exports compiled code calls directly: python-semantics
 * operators, prop merging for slotted components, form and ref collection, and
 * the small pieces of the event pipeline that need no socket. The queue and
 * connection lifecycle are covered by the node suites driven from
 * `tests/units`, which predate this package.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  applyDelta,
  applyEventActions,
  encodeFormDataArgs,
  generateUUID,
  getBackendURL,
  getFormData,
  getRefValue,
  getRefValues,
  getToken,
  hydrateClientStorage,
  isBackendDisabled,
  isNotNullOrUndefined,
  isStateful,
  isTrue,
  mergeRefs,
  mergeSlotProps,
  pyAnd,
  pyFlatMap,
  pyLstrip,
  pyOr,
  pyRstrip,
  pyStrAt,
  pyStrChars,
  pyStrip,
  pyStrLength,
  pyStrSlice,
  ReflexEvent,
  spreadArraysOrObjects,
} from "$/utils/state";

const clearCookies = () => {
  for (const cookie of document.cookie.split("; ")) {
    const name = cookie.split("=")[0];
    if (name) {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
    }
  }
};

beforeEach(() => {
  localStorage.clear();
  clearCookies();
});

describe("python truthiness", () => {
  test.each([
    [[], false],
    [[0], true],
    [{}, false],
    [{ a: undefined }, true],
    ["", false],
    ["0", true],
    [0, false],
    [1, true],
    [null, false],
    [undefined, false],
    [false, false],
  ])("isTrue(%j) is %s", (value, expected) => {
    expect(isTrue(value)).toBe(expected);
  });

  test("isNotNullOrUndefined keeps falsy values that are set", () => {
    expect([0, "", false, null, undefined].map(isNotNullOrUndefined)).toEqual([
      true,
      true,
      true,
      false,
      false,
    ]);
  });

  test("pyOr returns the first truthy operand without evaluating the second", () => {
    const rhs = vi.fn(() => "rhs");
    expect(pyOr([1], rhs)).toEqual([1]);
    expect(rhs).not.toHaveBeenCalled();
    expect(pyOr([], rhs)).toBe("rhs");
    expect(pyOr({}, () => 0)).toBe(0);
  });

  test("pyAnd returns the first falsy operand without evaluating the second", () => {
    const rhs = vi.fn(() => "rhs");
    const empty = [];
    expect(pyAnd(empty, rhs)).toBe(empty);
    expect(rhs).not.toHaveBeenCalled();
    expect(pyAnd("lhs", rhs)).toBe("rhs");
  });
});

describe("python string operations", () => {
  test("strip removes whitespace by default", () => {
    expect(pyStrip(" \t a b \n")).toBe("a b");
    expect(pyLstrip("  a  ")).toBe("a  ");
    expect(pyRstrip("  a  ")).toBe("  a");
  });

  test("strip removes any of the given characters, from the ends only", () => {
    expect(pyStrip("abcba", "ab")).toBe("c");
    expect(pyLstrip("xxaxx", "x")).toBe("axx");
    expect(pyRstrip("xxaxx", "x")).toBe("xxa");
    expect(pyStrip("aaa", "a")).toBe("");
    expect(pyStrip("abc", "")).toBe("abc");
  });

  test("strip treats a character outside the BMP as one character", () => {
    expect(pyStrip("😀a😀", "😀")).toBe("a");
    // 😁 shares its high surrogate with 😀, and must not strip half of it.
    expect(pyRstrip("a😀", "😁")).toBe("a😀");
    expect(pyLstrip("😀a", "😁")).toBe("😀a");
  });

  test("length, index and slice count code points", () => {
    expect(pyStrLength("a😀b")).toBe(3);
    expect(pyStrAt("a😀b", 1)).toBe("😀");
    expect(pyStrAt("a😀b", -1)).toBe("b");
    expect(pyStrAt("abc", 5)).toBeUndefined();
    expect(pyStrSlice("a😀bc", 1, 3)).toBe("😀b");
    expect(pyStrSlice("a😀bc", -2)).toBe("bc");
    expect(pyStrSlice("abc", null, 2)).toBe("ab");
    expect(pyStrChars("a😀")).toEqual(["a", "😀"]);
    expect(pyStrChars("")).toEqual([]);
  });

  test("pyFlatMap iterates each result the way python does", () => {
    expect(pyFlatMap([1, 2], (x) => [x, x * 10])).toEqual([1, 10, 2, 20]);
    expect(pyFlatMap(["a😀"], (x) => x)).toEqual(["a", "😀"]);
    expect(pyFlatMap([{ a: 1, b: 2 }], (x) => x)).toEqual(["a", "b"]);
    expect(pyFlatMap([], () => 1)).toEqual([]);
    expect(() => pyFlatMap([1], (x) => x)).toThrow(TypeError);
  });

  test("spreadArraysOrObjects concatenates arrays and merges objects", () => {
    expect(spreadArraysOrObjects([1], [2])).toEqual([1, 2]);
    expect(spreadArraysOrObjects({ a: 1, b: 1 }, { b: 2 })).toEqual({
      a: 1,
      b: 2,
    });
    expect(() => spreadArraysOrObjects(1, 2)).toThrow();
  });
});

describe("mergeRefs", () => {
  test("attaches the node to object and callback refs, and detaches on cleanup", () => {
    const object = { current: null };
    const callback = vi.fn();
    const node = {};
    const cleanup = mergeRefs(object, null, callback)(node);
    expect(object.current).toBe(node);
    expect(callback).toHaveBeenLastCalledWith(node);
    cleanup();
    expect(object.current).toBeNull();
    expect(callback).toHaveBeenLastCalledWith(null);
  });

  test("a callback ref with its own cleanup is not also called with null", () => {
    const ownCleanup = vi.fn();
    const callback = vi.fn(() => ownCleanup);
    mergeRefs(callback)({})();
    expect(ownCleanup).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledTimes(1);
  });
});

describe("mergeSlotProps", () => {
  test("returns the own props untouched when nothing is injected", () => {
    const own = { id: "a" };
    expect(mergeSlotProps({}, own)).toBe(own);
    expect(mergeSlotProps(undefined, own)).toBe(own);
  });

  test("own props win, and injected props fill what the own side lacks", () => {
    expect(
      mergeSlotProps(
        { id: "injected", role: "button", title: "injected" },
        { id: "own", title: undefined },
      ),
    ).toEqual({ id: "own", role: "button", title: "injected" });
  });

  test("event handlers compose, own first", () => {
    const calls = [];
    const merged = mergeSlotProps(
      { onClick: (e) => calls.push(["injected", e]) },
      { onClick: (e) => calls.push(["own", e]) },
    );
    merged.onClick("event");
    expect(calls).toEqual([
      ["own", "event"],
      ["injected", "event"],
    ]);
  });

  test("a composed handler keeps its identity while its inputs keep theirs", () => {
    const injected = { onClick: () => {} };
    const own = { onClick: () => {} };
    const first = mergeSlotProps(injected, own).onClick;
    expect(mergeSlotProps({ ...injected }, { ...own }).onClick).toBe(first);
    expect(mergeSlotProps({ onClick: () => {} }, { ...own }).onClick).not.toBe(
      first,
    );
  });

  test("class names concatenate and style merges deeply, own keys winning", () => {
    const merged = mergeSlotProps(
      { className: "injected", style: { color: "red", margin: 1 } },
      { className: "own", style: { color: "blue" } },
    );
    expect(merged.className).toBe("injected own");
    expect(merged.style).toEqual({ color: "blue", margin: 1 });
  });

  test("arrays and react elements are replaced, not merged", () => {
    const element = { $$typeof: Symbol.for("react.element"), props: {} };
    const merged = mergeSlotProps(
      { items: [1, 2], icon: { $$typeof: Symbol.for("react.element") } },
      { items: [3], icon: element },
    );
    expect(merged.items).toEqual([3]);
    expect(merged.icon).toBe(element);
  });

  test("refs compose into one that attaches both", () => {
    const injected = { current: null };
    const own = { current: null };
    const node = {};
    mergeSlotProps({ ref: injected }, { ref: own }).ref(node);
    expect(injected.current).toBe(node);
    expect(own.current).toBe(node);
  });

  test("an injected ref is routed to the prop that carries the dom ref", () => {
    const injected = { current: null };
    const own = { current: null };
    const node = {};

    const alone = mergeSlotProps({ ref: injected }, { id: "a" }, "inputRef");
    expect(alone).toEqual({ id: "a", inputRef: injected });

    const both = mergeSlotProps(
      { ref: injected },
      { inputRef: own },
      "inputRef",
    );
    expect("ref" in both).toBe(false);
    both.inputRef(node);
    expect(injected.current).toBe(node);
    expect(own.current).toBe(node);
  });
});

describe("refs", () => {
  test("getRefValue reads each kind of control", () => {
    expect(getRefValue(null)).toBeNull();
    expect(getRefValue({ current: null })).toBeNull();
    expect(getRefValue({ current: { type: "checkbox", checked: true } })).toBe(
      true,
    );
    expect(
      getRefValue({
        current: { className: "rt-SwitchRoot", ariaChecked: "false" },
      }),
    ).toBe(false);
    expect(getRefValue({ current: { value: "" } })).toBe("");
  });

  test("getRefValue reads a slider from its thumb and a radio group from its checked input", () => {
    const slider = document.createElement("div");
    slider.className = "rt-SliderRoot";
    slider.innerHTML = '<span class="rt-SliderThumb"></span>';
    slider.querySelector("span").ariaValueNow = "7";
    expect(getRefValue({ current: slider })).toBe("7");

    const group = document.createElement("div");
    group.innerHTML =
      '<input type="radio" name="r" value="a"><input type="radio" name="r" value="b" checked>';
    expect(getRefValue({ current: group })).toBe("b");
    expect(getRefValue({ current: document.createElement("div") })).toBeNull();
  });

  test("getRefValues reads a value, falling back to aria-valuenow", () => {
    const slider = document.createElement("div");
    slider.setAttribute("aria-valuenow", "3");
    expect(
      getRefValues([{ current: { value: "a" } }, { current: slider }, {}]),
    ).toEqual(["a", "3", null]);
    expect(getRefValues(undefined)).toBeUndefined();
  });
});

describe("form data", () => {
  const form = (html) => {
    const element = document.createElement("form");
    element.innerHTML = html;
    return element;
  };

  test("maps each field to its value", () => {
    expect(
      getFormData(form('<input name="a" value="1"><input name="b" value="2">')),
    ).toEqual({ a: "1", b: "2" });
  });

  test("a ref value replaces the entry the form submitted, and adds one it did not", () => {
    expect(
      getFormData(
        form('<input name="a" value="1"><input name="b" value="2">'),
        {
          a: true,
          c: "ref",
        },
      ),
    ).toEqual({ a: true, b: "2", c: "ref" });
  });

  test("a repeated name keeps every entry on the wire, in order", () => {
    const data = getFormData(
      form(
        '<input name="tag" value="x"><input name="other" value="o"><input name="tag" value="y">',
      ),
      { tag: "ref" },
    );
    expect(data).toEqual({ tag: "y", other: "o" });
    const event = { name: "submit", payload: { form_data: data, flag: 1 } };
    const encoded = encodeFormDataArgs(event);
    expect(encoded).toEqual({
      name: "submit",
      payload: {
        form_data: {
          __reflex_form_data__: [
            ["tag", "x"],
            ["other", "o"],
            ["tag", "y"],
          ],
        },
        flag: 1,
      },
    });
    expect(event.payload.form_data).toBe(data);
  });

  test("an event without form data is passed through as is", () => {
    const event = { name: "click", payload: { a: { b: 1 } } };
    expect(encodeFormDataArgs(event)).toBe(event);
    const bare = { name: "click" };
    expect(encodeFormDataArgs(bare)).toBe(bare);
  });
});

describe("session", () => {
  test("generateUUID produces distinct ids shaped like a version 4 uuid", () => {
    const ids = new Set(Array.from({ length: 200 }, generateUUID));
    expect(ids.size).toBe(200);
    for (const id of ids) {
      expect(id).toMatch(
        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}$/,
      );
    }
  });

  // Known bug: the variant digit is masked with 0x7 where RFC 9562 needs 0x3,
  // so about half the ids carry a reserved variant (c-f) and are not valid
  // version 4 uuids. `test.fails` turns red once that is fixed; make it a
  // plain test then.
  test.fails("generateUUID sets the RFC 9562 variant", () => {
    for (const id of Array.from({ length: 200 }, generateUUID)) {
      expect(id[19]).toMatch(/[89ab]/);
    }
  });

  test("getToken saves one token for the tab and keeps returning it", () => {
    const token = getToken();
    expect(sessionStorage.getItem("token")).toBe(token);
    expect(getToken()).toBe(token);
  });

  test("isBackendDisabled reads the backend-enabled cookie", () => {
    expect(isBackendDisabled()).toBe(false);
    document.cookie = "other=1";
    document.cookie = "backend-enabled=true";
    expect(isBackendDisabled()).toBe(false);
    document.cookie = "backend-enabled=false";
    expect(isBackendDisabled()).toBe(true);
  });

  test("getBackendURL points a wildcard bind address at the page's host", () => {
    expect(getBackendURL("http://0.0.0.0:8000/ping").href).toBe(
      `http://${window.location.hostname}:8000/ping`,
    );
  });

  // Known bug: `URL.hostname` keeps the brackets of an IPv6 address ("[::]"),
  // so the "::" and "0:0:0:0:0:0:0:0" entries of SAME_DOMAIN_HOSTNAMES never
  // match and an IPv6 wildcard backend is not pointed at the page's host.
  // `test.fails` turns red once that is fixed; make it a plain test then.
  test.fails("getBackendURL treats the IPv6 wildcard like 0.0.0.0", () => {
    expect(getBackendURL("ws://[::]:8000/_event").hostname).toBe(
      window.location.hostname,
    );
  });

  test("getBackendURL leaves a real backend host alone and defaults to ping", () => {
    expect(getBackendURL("https://api.example.com:8443/_upload").href).toBe(
      "https://api.example.com:8443/_upload",
    );
    expect(getBackendURL().pathname).toBe("/ping");
    expect(getBackendURL(null).pathname).toBe("/ping");
  });
});

describe("client storage", () => {
  test("hydrateClientStorage collects stored values under their state keys", () => {
    document.cookie = "named_cookie=cookie%20value";
    localStorage.setItem("state.local", "local value");
    sessionStorage.setItem("named_session", "session value");
    expect(
      hydrateClientStorage({
        cookies: {
          "state.cookie": { name: "named_cookie" },
          "state.unset_cookie": {},
        },
        local_storage: { "state.local": {}, "state.unset_local": {} },
        session_storage: {
          "state.session": { name: "named_session" },
          "state.unset_session": {},
        },
      }),
    ).toEqual({
      "state.cookie": "cookie value",
      "state.local": "local value",
      "state.session": "session value",
    });
  });

  test("hydrateClientStorage sends nothing for an app without client storage", () => {
    expect(hydrateClientStorage({})).toEqual({});
  });
});

describe("applyDelta", () => {
  test("a delta that changes nothing returns the same state", () => {
    const state = { substate: { count: 1, items: [1, { a: 1 }] } };
    expect(applyDelta(state, {})).toBe(state);
    expect(
      applyDelta(state, { substate: { count: 1, items: [1, { a: 1 }] } }),
    ).toBe(state);
  });

  test("unchanged values keep their identity beside the ones that changed", () => {
    const items = [1, { a: 1 }];
    const other = { value: "kept" };
    const state = { substate: { count: 1, items }, other };
    const next = applyDelta(state, {
      substate: { count: 2, items: [1, { a: 1 }] },
    });
    expect(next).not.toBe(state);
    expect(next.substate).toEqual({ count: 2, items });
    expect(next.substate.items).toBe(items);
    expect(next.other).toBe(other);
    expect(state.substate.count).toBe(1);
  });

  test("a substate the state has not seen is added", () => {
    expect(applyDelta({ a: { x: 1 } }, { b: { y: 2 } })).toEqual({
      a: { x: 1 },
      b: { y: 2 },
    });
  });
});

describe("events", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  test("ReflexEvent leaves out what is empty", () => {
    expect(ReflexEvent("state.handler")).toEqual({ name: "state.handler" });
    expect(ReflexEvent("state.handler", {}, {}, null)).toEqual({
      name: "state.handler",
    });
    expect(
      ReflexEvent("state.handler", { a: 1 }, { debounce: 5 }, "uploadFiles"),
    ).toEqual({
      name: "state.handler",
      payload: { a: 1 },
      event_actions: { debounce: 5 },
      handler: "uploadFiles",
    });
  });

  test("nothing is stateful while the queue is empty", () => {
    expect(isStateful()).toBe(false);
  });

  test("applyEventActions calls the target with the args and returns its result", () => {
    const target = vi.fn((a, b) => a + b);
    expect(applyEventActions(target, {}, [1, 2])).toBe(3);
    expect(applyEventActions(target, undefined, 1)).toBeNaN();
    expect(target).toHaveBeenLastCalledWith(1);
  });

  test("preventDefault and stopPropagation act on the dom event among the args", () => {
    const domEvent = { preventDefault: vi.fn(), stopPropagation: vi.fn() };
    const target = vi.fn();
    applyEventActions(target, { preventDefault: true }, ["value", domEvent]);
    expect(domEvent.preventDefault).toHaveBeenCalledTimes(1);
    expect(domEvent.stopPropagation).not.toHaveBeenCalled();
    applyEventActions(target, { stopPropagation: true }, [domEvent]);
    expect(domEvent.stopPropagation).toHaveBeenCalledTimes(1);
    expect(target).toHaveBeenCalledTimes(2);
  });

  test("a temporal event is dropped while its handler says the backend is away", () => {
    const target = vi.fn();
    applyEventActions(target, { temporal: true }, [], null, () => false);
    expect(target).not.toHaveBeenCalled();
    applyEventActions(target, { temporal: true }, [], null, () => true);
    applyEventActions(target, {}, [], null, () => false);
    expect(target).toHaveBeenCalledTimes(2);
  });

  test("throttle drops calls inside the window, keyed by the action key", () => {
    const target = vi.fn();
    const actions = { throttle: 100 };
    applyEventActions(target, actions, [], "throttled-a");
    applyEventActions(target, actions, [], "throttled-a");
    applyEventActions(target, actions, [], "throttled-b");
    expect(target).toHaveBeenCalledTimes(2);
    vi.advanceTimersByTime(100);
    applyEventActions(target, actions, [], "throttled-a");
    expect(target).toHaveBeenCalledTimes(3);
  });

  test("debounce runs the last call with its own args once the delay passes", () => {
    const target = vi.fn();
    const actions = { debounce: 100 };
    expect(applyEventActions(target, actions, ["first"], "debounced")).toBe(
      undefined,
    );
    vi.advanceTimersByTime(50);
    applyEventActions(target, actions, ["second"], "debounced");
    vi.advanceTimersByTime(99);
    expect(target).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(target.mock.calls).toEqual([["second"]]);
  });
});
