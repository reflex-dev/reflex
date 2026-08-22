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
  ClientStateScope,
  createClientStateStore,
  getClientState,
  getClientStore,
  setClientState,
  useClientState,
  withClientStateScope,
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
  test("a name is claimed once and seeded by the first default", () => {
    const store = createClientStateStore();
    const first = store.root.own("shared", "initial");
    const second = store.root.own("shared", "ignored");

    expect(second).toBe(first);
    expect(store.get("shared")).toBe("initial");
  });

  test("a child scope shadows nothing it does not own", () => {
    const store = createClientStateStore();
    const parentSlot = store.root.own("shared", "from parent");

    // A child that has not claimed the name resolves to the parent's slot.
    const child = { parent: store.root, owned: new Map() };
    expect(store.root.find("shared")).toBe(parentSlot);
    expect(child.parent.find("shared")).toBe(parentSlot);
  });

  test("writing one var does not notify another var's subscribers", () => {
    const store = createClientStateStore();
    const watched = vi.fn();
    const unrelated = vi.fn();
    store.root.own("a", 0).subscribe(watched);
    store.root.own("b", 0).subscribe(unrelated);

    store.set("a", 1);

    expect(watched).toHaveBeenCalledTimes(1);
    expect(unrelated).not.toHaveBeenCalled();
  });

  test("a function value is applied as an updater", () => {
    const store = createClientStateStore();
    store.root.own("n", 1);

    store.set("n", (previous) => previous + 41);

    expect(store.get("n")).toBe(42);
  });

  test("setting an equal value notifies nobody", () => {
    const store = createClientStateStore();
    const listener = vi.fn();
    store.root.own("n", 7).subscribe(listener);

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
    expect(store.root.own("later", "default ignored").getSnapshot()).toBe(
      "pushed early",
    );
  });

  test("unsubscribing detaches the listener", () => {
    const store = createClientStateStore();
    const listener = vi.fn();
    const unsubscribe = store.root.own("n", 0).subscribe(listener);

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
  const probe = (defaultValue, name, id, isGlobal) => {
    const renders = { count: 0, value: undefined, set: undefined };
    const Probe = () => {
      const [value, set] = useClientState(defaultValue, name, isGlobal);
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

  test("shares one scope between siblings under the same boundary", () => {
    // Two consumers of the same name with no boundary between them: the
    // enclosing scope owns it, so an auto-memo split stays invisible.
    const a = probe("", "sibling", "a");
    const b = probe("", "sibling", "b");
    const { unmount } = mount(
      createElement(ClientStateProvider, { registry }, a.element, b.element),
    );

    act(() => a.renders.set("shared"));

    expect(a.renders.value).toBe("shared");
    expect(b.renders.value).toBe("shared");

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

describe("scope chain", () => {
  /** Render `useClientState` and report renders, value and setter. */
  const probe = (defaultValue, name, isGlobal) => {
    const renders = { count: 0, value: undefined, set: undefined };
    const Probe = () => {
      const [value, set] = useClientState(defaultValue, name, isGlobal);
      renders.count += 1;
      renders.value = value;
      renders.set = set;
      return null;
    };
    return { renders, element: createElement(Probe) };
  };

  test("a descendant inherits the slot its ancestor scope owns", () => {
    // The boundary's own consumer claims the name; a component further down
    // resolves up the chain to that same slot.
    const owner = probe("initial", "claimed");
    const descendant = probe("initial", "claimed");
    const { unmount } = mount(
      createElement(
        ClientStateProvider,
        { registry },
        createElement(
          ClientStateScope,
          null,
          owner.element,
          createElement(ClientStateScope, null, descendant.element),
        ),
      ),
    );

    act(() => owner.renders.set("written by owner"));

    expect(descendant.renders.value).toBe("written by owner");

    unmount();
  });

  test("sibling boundaries get separate slots for the same name", () => {
    const first = probe("initial", "perInstance");
    const second = probe("initial", "perInstance");
    const { unmount } = mount(
      createElement(
        ClientStateProvider,
        { registry },
        createElement(ClientStateScope, null, first.element),
        createElement(ClientStateScope, null, second.element),
      ),
    );

    act(() => first.renders.set("only mine"));

    expect(first.renders.value).toBe("only mine");
    expect(second.renders.value).toBe("initial");

    unmount();
  });

  test("a nested boundary claims a name its ancestors have not", () => {
    const outer = probe("initial", "onlyInner");
    const inner = probe("initial", "onlyInner");
    const { unmount } = mount(
      createElement(
        ClientStateProvider,
        { registry },
        createElement(
          ClientStateScope,
          null,
          createElement(ClientStateScope, null, inner.element),
          outer.element,
        ),
      ),
    );

    // The inner boundary rendered first and claimed it there, so the outer
    // consumer -- which is not a descendant of it -- is unaffected.
    act(() => inner.renders.set("inner only"));

    expect(inner.renders.value).toBe("inner only");
    expect(outer.renders.value).toBe("initial");

    unmount();
  });

  test("a global name stays global inside a boundary", () => {
    const scoped = probe("initial", "globalName", true);
    const atRoot = probe("initial", "globalName", true);
    const { unmount } = mount(
      createElement(
        ClientStateProvider,
        { registry },
        createElement(ClientStateScope, null, scoped.element),
        atRoot.element,
      ),
    );

    act(() => scoped.renders.set("from inside a boundary"));

    expect(atRoot.renders.value).toBe("from inside a boundary");
    // Reachable from outside React, which is the point of being global.
    expect(getClientState("globalName")).toBe("from inside a boundary");

    unmount();
  });

  test("a scoped name is not reachable from outside the tree", () => {
    const scoped = probe("initial", "treeOnly");
    const { unmount } = mount(
      createElement(
        ClientStateProvider,
        { registry },
        createElement(ClientStateScope, null, scoped.element),
      ),
    );

    act(() => scoped.renders.set("private"));

    expect(scoped.renders.value).toBe("private");
    expect(getClientState("treeOnly")).toBeUndefined();

    unmount();
  });

  test("writing in one boundary leaves a sibling boundary unrendered", () => {
    const first = probe(0, "isolated");
    const second = probe(0, "isolated");
    const { unmount } = mount(
      createElement(
        ClientStateProvider,
        { registry },
        createElement(ClientStateScope, null, first.element),
        createElement(ClientStateScope, null, second.element),
      ),
    );
    const before = second.renders.count;

    act(() => first.renders.set(1));

    expect(first.renders.value).toBe(1);
    expect(second.renders.count).toBe(before);

    unmount();
  });
});

describe("withClientStateScope", () => {
  test("gives each mounted instance its own state", () => {
    // The shape the compiler emits for a real component boundary. The scope has
    // to be outside the component, since its hooks run before its output
    // mounts -- inside, every instance would share the enclosing scope.
    // Track the LATEST value per instance: comparing first-render snapshots
    // passes even when the state is shared.
    const latest = {};
    const setters = {};
    const Counter = ({ which }) => {
      const [value, set] = useClientState(0, "perInstanceHoc");
      latest[which] = value;
      setters[which] = set;
      return null;
    };
    const Scoped = withClientStateScope(Counter);

    const { unmount } = mount(
      createElement(
        ClientStateProvider,
        { registry },
        createElement(Scoped, { which: "a" }),
        createElement(Scoped, { which: "b" }),
      ),
    );

    act(() => setters.a(1));

    expect(latest.a).toBe(1);
    expect(latest.b).toBe(0);

    unmount();
  });

  test("descendants of a wrapped instance share its state", () => {
    const parentSeen = [];
    const childSeen = [];
    const Child = () => {
      const [value] = useClientState("initial", "sharedWithChild");
      childSeen.push(value);
      return null;
    };
    const Parent = () => {
      const [value, set] = useClientState("initial", "sharedWithChild");
      parentSeen.push({ value, set });
      return createElement(Child);
    };
    const Scoped = withClientStateScope(Parent);

    const { unmount } = mount(
      createElement(ClientStateProvider, { registry }, createElement(Scoped)),
    );

    act(() => parentSeen[0].set("from parent"));

    expect(childSeen.at(-1)).toBe("from parent");

    unmount();
  });
});

test("CLIENT_STATE_REF matches the key state.js reads", () => {
  // The runtime reaches the store through the object it is handed, so the key
  // is duplicated on the reading side and has to stay in sync.
  const stateJs = readFileSync(`${__WEB_ROOT__}utils/state.js`, "utf8");

  expect(stateJs).toContain(`refs["${CLIENT_STATE_REF}"]`);
});
