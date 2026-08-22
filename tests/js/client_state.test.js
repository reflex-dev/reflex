/**
 * Unit tests for `utils/client_state.js`.
 *
 * These cover the parts the Python and Playwright suites structurally cannot:
 * teardown when several providers share one store, SSR store isolation, and the
 * per-slot subscription behavior the design rests on.
 */
import { readFileSync } from "node:fs";

import { act } from "react";
import { createElement, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  CLIENT_STATE_REF,
  ClientStateProvider,
  createClientStateStore,
  getClientState,
  getClientStore,
  setClientState,
  useClientState,
} from "$/utils/client_state";

// React 19 wants this set when driving roots manually.
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

/** Mount a tree into a detached root, returning it and its container. */
const mount = (element, { strict = false } = {}) => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => {
    root.render(strict ? createElement(StrictMode, null, element) : element);
  });
  return {
    container,
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
};

/** A stand-in for the global object the app publishes the store on. */
let registry;

beforeEach(() => {
  registry = {};
});

describe("store slots", () => {
  test("a named slot is shared and seeded by the first default", () => {
    const store = createClientStateStore();
    const first = store.slot("shared", "initial");
    const second = store.slot("shared", "ignored");

    expect(second).toBe(first);
    expect(store.get("shared")).toBe("initial");
  });

  test("an unnamed slot is private and unaddressable by name", () => {
    const store = createClientStateStore();
    const a = store.slot(undefined, "a");
    const b = store.slot(undefined, "b");

    expect(a).not.toBe(b);
    a.set("changed");
    expect(b.getSnapshot()).toBe("b");
    // Anonymous slots are never registered, so nothing can reach them by name.
    expect(store.get(undefined)).toBeUndefined();
  });

  test("writing one var does not notify another var's subscribers", () => {
    const store = createClientStateStore();
    const watched = vi.fn();
    const unrelated = vi.fn();
    store.slot("a", 0).subscribe(watched);
    store.slot("b", 0).subscribe(unrelated);

    store.set("a", 1);

    expect(watched).toHaveBeenCalledTimes(1);
    expect(unrelated).not.toHaveBeenCalled();
  });

  test("a function value is applied as an updater", () => {
    const store = createClientStateStore();
    store.slot("n", 1);

    store.set("n", (previous) => previous + 41);

    expect(store.get("n")).toBe(42);
  });

  test("setting an equal value notifies nobody", () => {
    const store = createClientStateStore();
    const listener = vi.fn();
    store.slot("n", 7).subscribe(listener);

    store.set("n", 7);

    expect(listener).not.toHaveBeenCalled();
    expect(store.get("n")).toBe(7);
  });

  test("writing an unknown name creates the slot", () => {
    // A value pushed from the backend before any component mounts has to be
    // retained, so the component picks it up when it does mount.
    const store = createClientStateStore();

    store.set("later", "pushed early");

    expect(store.get("later")).toBe("pushed early");
    expect(store.slot("later", "default ignored").getSnapshot()).toBe(
      "pushed early",
    );
  });

  test("unsubscribing detaches the listener", () => {
    const store = createClientStateStore();
    const listener = vi.fn();
    const unsubscribe = store.slot("n", 0).subscribe(listener);

    unsubscribe();
    store.set("n", 1);

    expect(listener).not.toHaveBeenCalled();
  });
});

describe("getClientStore", () => {
  test("is a singleton on the client", () => {
    expect(getClientStore()).toBe(getClientStore());
  });

  test("is per-call on the server, so nothing leaks between requests", () => {
    const realDocument = globalThis.document;
    // The module keys off `typeof document`, which is how it tells SSR apart.
    // @ts-expect-error - deleting a global for the duration of the test.
    delete globalThis.document;
    try {
      const first = getClientStore();
      first.set("leaky", "request one");

      const second = getClientStore();

      expect(second).not.toBe(first);
      expect(second.get("leaky")).toBeUndefined();
    } finally {
      globalThis.document = realDocument;
    }
  });
});

describe("ClientStateProvider", () => {
  test("publishes the store on the registry it is given", () => {
    expect(registry[CLIENT_STATE_REF]).toBeUndefined();

    const { unmount } = mount(createElement(ClientStateProvider, { registry }));

    expect(registry[CLIENT_STATE_REF]).toBe(getClientStore());

    unmount();

    expect(registry[CLIENT_STATE_REF]).toBeUndefined();
  });

  test("keeps the entry until the last provider unmounts", () => {
    // Two app roots on one page (an embedded app beside a main app) share the
    // client singleton, so the first teardown must not strand the other.
    const first = mount(createElement(ClientStateProvider, { registry }));
    const second = mount(createElement(ClientStateProvider, { registry }));

    first.unmount();

    expect(registry[CLIENT_STATE_REF]).toBe(getClientStore());

    second.unmount();

    expect(registry[CLIENT_STATE_REF]).toBeUndefined();
  });

  test("survives StrictMode's double mount", () => {
    const { unmount } = mount(
      createElement(ClientStateProvider, { registry }),
      {
        strict: true,
      },
    );

    expect(registry[CLIENT_STATE_REF]).toBe(getClientStore());

    unmount();

    expect(registry[CLIENT_STATE_REF]).toBeUndefined();
  });
});

describe("useClientState", () => {
  /** Render `useClientState(default, name)` and report renders and value. */
  const probe = (defaultValue, name, id) => {
    const renders = { count: 0, value: undefined, set: undefined };
    const Probe = () => {
      const [value, set] = useClientState(defaultValue, name);
      renders.count += 1;
      renders.value = value;
      renders.set = set;
      return createElement("span", { id }, String(value));
    };
    return { renders, element: createElement(Probe) };
  };

  test("shares a named var across components", () => {
    const a = probe("initial", "shared", "a");
    const b = probe("initial", "shared", "b");
    const { unmount } = mount(
      createElement(ClientStateProvider, { registry }, a.element, b.element),
    );

    act(() => a.renders.set("typed"));

    expect(a.renders.value).toBe("typed");
    expect(b.renders.value).toBe("typed");

    unmount();
  });

  test("keeps unnamed vars private to each component", () => {
    const a = probe("", undefined, "a");
    const b = probe("", undefined, "b");
    const { unmount } = mount(
      createElement(ClientStateProvider, { registry }, a.element, b.element),
    );

    act(() => a.renders.set("mine"));

    expect(a.renders.value).toBe("mine");
    expect(b.renders.value).toBe("");

    unmount();
  });

  test("does not re-render a component reading an unrelated var", () => {
    // The property the whole store design exists for.
    const watched = probe(0, "watched", "watched");
    const unrelated = probe(0, "unrelated", "unrelated");
    const { unmount } = mount(
      createElement(
        ClientStateProvider,
        { registry },
        watched.element,
        unrelated.element,
      ),
    );
    const before = unrelated.renders.count;

    act(() => watched.renders.set(1));

    expect(watched.renders.value).toBe(1);
    expect(unrelated.renders.count).toBe(before);

    unmount();
  });

  test("a late mount reads the current value, not the default", () => {
    const early = probe("default", "late", "early");
    const first = mount(
      createElement(ClientStateProvider, { registry }, early.element),
    );
    act(() => early.renders.set("current"));

    const late = probe("default", "late", "late");
    const second = mount(
      createElement(ClientStateProvider, { registry }, late.element),
    );

    expect(late.renders.value).toBe("current");

    second.unmount();
    first.unmount();
  });

  test("accepts a functional updater", () => {
    const counter = probe(1, "counter", "counter");
    const { unmount } = mount(
      createElement(ClientStateProvider, { registry }, counter.element),
    );

    act(() => counter.renders.set((previous) => previous + 41));

    expect(counter.renders.value).toBe(42);

    unmount();
  });
});

describe("non-React escape hatch", () => {
  test("reads and writes the store the hooks are bound to", () => {
    const renders = { count: 0, value: undefined };
    const Probe = () => {
      const [value] = useClientState("initial", "escaped");
      renders.count += 1;
      renders.value = value;
      return null;
    };
    const { unmount } = mount(
      createElement(ClientStateProvider, { registry }, createElement(Probe)),
    );

    expect(getClientState("escaped")).toBe("initial");

    act(() => setClientState("escaped", "from plain js"));

    expect(renders.value).toBe("from plain js");
    expect(getClientState("escaped")).toBe("from plain js");

    unmount();
  });
});

test("CLIENT_STATE_REF matches the key state.js reads", () => {
  // The runtime reaches the store through the object it is handed, so the key
  // is duplicated on the reading side and has to stay in sync.
  const stateJs = readFileSync(`${__WEB_ROOT__}utils/state.js`, "utf8");

  expect(stateJs).toContain(`refs["${CLIENT_STATE_REF}"]`);
});
