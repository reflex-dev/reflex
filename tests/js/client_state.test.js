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
  ScopedValues,
  createClientStateStore,
  getClientState,
  getClientStore,
  setClientState,
  useClientState,
  useScopedValue,
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
    // Re-render into the same root, so React reconciles rather than remounting
    // -- which is what the tests about list churn need to observe.
    rerender: (next) => {
      act(() => {
        root.render(strict ? createElement(StrictMode, null, next) : next);
      });
    },
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
};

/** Values every rendered `ItemState` has reported, oldest first. */
const itemValues = [];

/** Setter belonging to the most recently rendered `ItemState`. */
let lastItemSetter;

/** An unnamed client state var, as a loop body would declare one. */
const ItemState = () => {
  const [value, set] = useClientState("default", "item_cs0");
  itemValues.push(value);
  lastItemSetter = set;
  return null;
};

/** A stand-in for the global object the app publishes the store on. */
let registry;

beforeEach(() => {
  registry = {};
  itemValues.length = 0;
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

describe("scoped values", () => {
  /** Render a component that reads one scoped value by name. */
  const reader = (name) => {
    const seen = [];
    const Reader = () => {
      seen.push(useScopedValue(name));
      return null;
    };
    return { seen, element: createElement(Reader) };
  };

  test("a descendant component reads a value it never received as a prop", () => {
    // The shape a loop emits: the value lives in context, so a descendant that
    // compiled into its own component can still see it.
    const item = reader("item0");
    const { unmount } = mount(
      createElement(ScopedValues, { values: { item0: "a" } }, item.element),
    );

    expect(item.seen.at(-1)).toBe("a");

    unmount();
  });

  test("a nested provider still exposes the outer values", () => {
    const outer = reader("outer0");
    const inner = reader("inner0");
    const { unmount } = mount(
      createElement(
        ScopedValues,
        { values: { outer0: "out" } },
        createElement(
          ScopedValues,
          { values: { inner0: "in" } },
          outer.element,
          inner.element,
        ),
      ),
    );

    expect(outer.seen.at(-1)).toBe("out");
    expect(inner.seen.at(-1)).toBe("in");

    unmount();
  });

  test("a nearer provider shadows the same name", () => {
    const item = reader("item0");
    const { unmount } = mount(
      createElement(
        ScopedValues,
        { values: { item0: "outer" } },
        createElement(
          ScopedValues,
          { values: { item0: "inner" } },
          item.element,
        ),
      ),
    );

    expect(item.seen.at(-1)).toBe("inner");

    unmount();
  });

  test("an unprovided name reads undefined rather than throwing", () => {
    const item = reader("missing");
    const { unmount } = mount(
      createElement(ScopedValues, { values: {} }, item.element),
    );

    expect(item.seen.at(-1)).toBeUndefined();

    unmount();
  });

  test("reading outside any provider is undefined", () => {
    const item = reader("orphan");
    const { unmount } = mount(item.element);

    expect(item.seen.at(-1)).toBeUndefined();

    unmount();
  });

  test("a re-render with new values is seen by descendants", () => {
    // A loop re-renders with a new item on every list change, so the provided
    // value must not be frozen at first render.
    const item = reader("item0");
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    const render = (value) =>
      act(() => {
        root.render(
          createElement(
            ScopedValues,
            { values: { item0: value } },
            item.element,
          ),
        );
      });

    render("first");
    expect(item.seen.at(-1)).toBe("first");

    render("second");
    expect(item.seen.at(-1)).toBe("second");

    act(() => root.unmount());
    container.remove();
  });

  test("each provided subtree owns its unnamed client state", () => {
    // One rendered item is one component instance, so an unnamed var used in a
    // loop body must not be shared between items.
    const stateProbe = () => {
      const renders = { value: undefined, set: undefined };
      const Probe = () => {
        const [value, set] = useClientState("", "cs0");
        renders.value = value;
        renders.set = set;
        return null;
      };
      return { renders, element: createElement(Probe) };
    };
    const first = stateProbe();
    const second = stateProbe();
    const { unmount } = mount(
      createElement(
        ClientStateProvider,
        { registry },
        createElement(ScopedValues, { values: { item0: "a" } }, first.element),
        createElement(ScopedValues, { values: { item0: "b" } }, second.element),
      ),
    );

    act(() => first.renders.set("typed into the first"));

    expect(first.renders.value).toBe("typed into the first");
    expect(second.renders.value).toBe("");

    unmount();
  });

  test("sibling providers give each subtree its own value", () => {
    // One loop, two items: each item's subtree sees only its own value.
    const first = reader("item0");
    const second = reader("item0");
    const { unmount } = mount(
      createElement(
        "div",
        null,
        createElement(ScopedValues, { values: { item0: "a" } }, first.element),
        createElement(ScopedValues, { values: { item0: "b" } }, second.element),
      ),
    );

    expect(first.seen.at(-1)).toBe("a");
    expect(second.seen.at(-1)).toBe("b");

    unmount();
  });
});

describe("slot lifetime", () => {
  test("a consumer unsubscribes from its slot when it unmounts", () => {
    // Root-scope slots live for the page, so a listener that outlived its
    // component would pin that component's React internals forever.
    const slot = getClientStore().root.own("lifetime_global", "seed");
    let live = 0;
    const realSubscribe = slot.subscribe;
    slot.subscribe = (onStoreChange) => {
      live += 1;
      const off = realSubscribe(onStoreChange);
      return () => {
        live -= 1;
        off();
      };
    };

    const Reader = () => {
      useClientState("seed", "lifetime_global", true);
      return null;
    };
    const { unmount } = mount(
      createElement(ClientStateProvider, { registry }, createElement(Reader)),
    );

    expect(live).toBe(1);

    unmount();

    expect(live).toBe(0);
    slot.subscribe = realSubscribe;
  });

  test("per-item state is claimed in the item's scope, never at the root", () => {
    // Otherwise a loop would append a root entry per rendered item and the
    // store would grow without bound as the list churned.
    const root = getClientStore().root;
    const before = root.owned.size;
    const rows = (list) =>
      createElement(
        ClientStateProvider,
        { registry },
        ...list.map((item) =>
          createElement(
            ScopedValues,
            { key: item, values: { item0: item } },
            createElement(ItemState),
          ),
        ),
      );
    const { rerender, unmount } = mount(rows(["a", "b", "c"]));

    expect(root.owned.size).toBe(before);

    rerender(rows(["d", "e", "f"]));
    expect(root.owned.size).toBe(before);

    unmount();
    expect(root.owned.size).toBe(before);
  });

  test("an item's state is released once that item unmounts", () => {
    // Keying by identity means a changed list unmounts the old rows, so their
    // scopes -- and the slots those scopes own -- become unreachable. A new row
    // reaching the same name has to start from the default, not inherit.
    const rows = (list) =>
      createElement(
        ClientStateProvider,
        { registry },
        ...list.map((item) =>
          createElement(
            ScopedValues,
            { key: item, values: { item0: item } },
            createElement(ItemState),
          ),
        ),
      );
    const { rerender, unmount } = mount(rows(["a", "b", "c"]));

    act(() => lastItemSetter("written"));
    expect(itemValues.at(-1)).toBe("written");

    itemValues.length = 0;
    rerender(rows(["d", "e", "f"]));

    expect(itemValues).toEqual(["default", "default", "default"]);

    unmount();
  });

  test("under positional keys an item keeps its state across a list change", () => {
    // The counterpart, and the reason `key=` matters now that a loop item can
    // hold state: index keys reuse the component, so nothing unmounts and the
    // state stays with the position rather than the item.
    const rows = (list) =>
      createElement(
        ClientStateProvider,
        { registry },
        ...list.map((item, index) =>
          createElement(
            ScopedValues,
            { key: index, values: { item0: item } },
            createElement(ItemState),
          ),
        ),
      );
    const { rerender, unmount } = mount(rows(["a", "b", "c"]));

    act(() => lastItemSetter("written"));
    itemValues.length = 0;
    rerender(rows(["d", "e", "f"]));

    expect(itemValues).toEqual(["default", "default", "written"]);

    unmount();
  });
});

test("CLIENT_STATE_REF matches the Python constant", () => {
  // The key has exactly two definitions -- this one and the Python constant the
  // compiler emits `refs[...]` from -- because neither language can import the
  // other's. Everything else on either side references its own, so this is the
  // only seam left where a rename can drift.
  const constantsPy = readFileSync(__PY_CONSTANTS__, "utf8");
  const declared = constantsPy.match(/^CLIENT_STATE_REF = "(.*)"$/m);

  expect(declared, "no CLIENT_STATE_REF in constants/state.py").not.toBeNull();
  expect(declared[1]).toBe(CLIENT_STATE_REF);
});

test("state.js reads the store through the shared constant", () => {
  // Guards a regression back to a hardcoded copy: the reader outside the React
  // tree has to go through the constant, not re-spell the key.
  const stateJs = readFileSync(`${__WEB_ROOT__}utils/state.js`, "utf8");

  expect(stateJs).toContain("refs[CLIENT_STATE_REF]");
  expect(stateJs).not.toContain(`"${CLIENT_STATE_REF}"`);
});
