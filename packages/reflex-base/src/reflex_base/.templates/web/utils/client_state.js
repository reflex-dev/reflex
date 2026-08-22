/**
 * Client-only state, scoped by name down the component tree.
 *
 * `useClientState` is the only thing compiled components call. Everything else
 * here is the bookkeeping it needs: independently-subscribable slots, the scope
 * chain that decides which slot a name resolves to, and a module-level door for
 * JS that runs outside the React tree (`getClientState` / `setClientState`).
 *
 * Scoping: a scope owns some names and delegates the rest to its parent. The
 * first component in a tree to use a name claims it for its descendants, so
 * separate instances of a boundary get separate state while everything under one
 * boundary shares. Compiler-inserted `ClientStateScope` elements create the
 * boundaries; boundaries that only exist as a compiler optimization do not, so
 * splitting a subtree across memo modules is semantically invisible.
 *
 * Each slot owns its own listener set, so writing one var only re-renders the
 * components subscribed to *that* var.
 */
import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useRef,
  useSyncExternalStore,
} from "react";

/**
 * Key under which the provider publishes its store on the `registry` object it
 * is handed, for backend-evaluated code and devtools introspection.
 */
export const CLIENT_STATE_REF = "__client_state";

/**
 * Create a slot: one piece of client state, with its own subscribers.
 * @param value The initial value.
 * @returns The slot.
 */
const createSlot = (value) => {
  const listeners = new Set();
  const slot = {
    value,
    // Stable identities: useSyncExternalStore requires them.
    subscribe: (onStoreChange) => {
      listeners.add(onStoreChange);
      return () => listeners.delete(onStoreChange);
    },
    getSnapshot: () => slot.value,
    set: (next) => {
      // Match the useState contract: a function is an updater, not a value.
      const resolved = typeof next === "function" ? next(slot.value) : next;
      if (Object.is(resolved, slot.value)) {
        return;
      }
      slot.value = resolved;
      listeners.forEach((listener) => listener());
    },
  };
  return slot;
};

/**
 * Create a scope: a node in the ownership chain.
 * @param parent The enclosing scope, or null for a root.
 * @returns The scope.
 */
const createScope = (parent) => {
  const owned = new Map();
  const scope = {
    parent,
    owned,
    /**
     * Claim `name` in this scope, or return the slot already claimed here.
     *
     * Get-or-create, so a double invocation under StrictMode or a re-entrant
     * render converges on one slot rather than replacing it.
     * @param name The client state name.
     * @param defaultValue Initial value, used only when claiming.
     * @returns The slot this scope owns for `name`.
     */
    own: (name, defaultValue) => {
      let slot = owned.get(name);
      if (slot === undefined) {
        slot = createSlot(defaultValue);
        owned.set(name, slot);
      }
      return slot;
    },
    /**
     * Find the slot an ancestor (or this scope) already owns for `name`.
     * @param name The client state name.
     * @returns The slot, or undefined when nothing in the chain owns it.
     */
    find: (name) => {
      for (let current = scope; current !== null; current = current.parent) {
        const found = current.owned.get(name);
        if (found !== undefined) {
          return found;
        }
      }
      return undefined;
    },
  };
  return scope;
};

/**
 * Walk to the root of a scope chain.
 * @param scope Any scope in the chain.
 * @returns The root scope.
 */
const rootOf = (scope) => {
  let current = scope;
  while (current.parent !== null) {
    current = current.parent;
  }
  return current;
};

/**
 * Create a store: the root scope, plus the by-name access the backend uses.
 * @returns The store.
 */
export const createClientStateStore = () => {
  const root = createScope(null);
  return {
    root,
    /**
     * Read a name from the root scope.
     * @param name The client state name.
     * @returns The value, or undefined if nothing owns the name yet.
     */
    get: (name) => root.owned.get(name)?.value,
    /**
     * Write a name in the root scope, claiming it if needed, so a value pushed
     * before any component mounts is picked up on mount.
     * @param name The client state name.
     * @param value The value, or an updater function.
     */
    set: (name, value) => {
      root.own(name, undefined).set(value);
    },
  };
};

let _clientStore = null;

/**
 * The client-side store singleton.
 *
 * Shared so that non-React callers and the hooks operate on the same slots
 * regardless of mount order. On the server a fresh store is returned every
 * call and never memoized, so no value can leak between requests.
 * @returns The store.
 */
export const getClientStore = () => {
  if (typeof document === "undefined") {
    return createClientStateStore();
  }
  if (_clientStore === null) {
    _clientStore = createClientStateStore();
  }
  return _clientStore;
};

/** The nearest owning scope. Null outside any provider. */
export const ClientStateScopeContext = createContext(null);

/**
 * Read a globally-named client state var from outside the React tree.
 *
 * A point-in-time snapshot with no reactivity; prefer the value returned by
 * `useClientState` inside components. Only names declared as global resolve
 * here — tree-scoped vars are deliberately unreachable from outside their tree.
 * @param name The client state var name.
 * @returns The current value.
 */
export const getClientState = (name) => getClientStore().get(name);

/**
 * Write a globally-named client state var from outside the React tree.
 *
 * Every subscribed component re-renders. Use this to drive client state from
 * third-party library callbacks or other non-React JS.
 * @param name The client state var name.
 * @param value The value, or an updater function.
 */
export const setClientState = (name, value) => {
  getClientStore().set(name, value);
};

let _mountedProviders = 0;

/**
 * Provide the root scope to the tree.
 * @param props The component props.
 * @param props.children The children to render.
 * @param props.registry Optional object to publish the store on, under
 *   `CLIENT_STATE_REF`, so code running outside the React tree can reach it.
 *   Passed in by the caller rather than imported, so this module stays
 *   independent of where that lives.
 * @returns The provider element.
 */
export function ClientStateProvider({ children, registry }) {
  const storeRef = useRef(null);
  if (storeRef.current === null) {
    // On the client this is the shared singleton, so `setClientState` and the
    // hooks reach the same slots; on the server it is per-render.
    storeRef.current = getClientStore();
  }
  const store = storeRef.current;

  useEffect(() => {
    if (registry === undefined) {
      return undefined;
    }
    // In an effect, so the store is never published during an SSR render.
    registry[CLIENT_STATE_REF] = store;
    _mountedProviders += 1;
    return () => {
      _mountedProviders -= 1;
      // Several providers can share one store, so only the last one out clears
      // the entry.
      if (_mountedProviders === 0 && registry[CLIENT_STATE_REF] === store) {
        delete registry[CLIENT_STATE_REF];
      }
    };
  }, [store, registry]);

  return createElement(
    ClientStateScopeContext.Provider,
    { value: store.root },
    children,
  );
}

/**
 * Open a client state scope around a subtree.
 *
 * Emitted by the compiler at component-instance boundaries. Names first used
 * inside are owned here, so each mounted instance gets its own state and its
 * descendants share it.
 * @param props The component props.
 * @param props.children The children to render.
 * @returns The provider element.
 */
export function ClientStateScope({ children }) {
  const parent = useContext(ClientStateScopeContext);
  const scopeRef = useRef(null);
  if (scopeRef.current === null || scopeRef.current.parent !== parent) {
    scopeRef.current = createScope(parent ?? getClientStore().root);
  }
  return createElement(
    ClientStateScopeContext.Provider,
    { value: scopeRef.current },
    children,
  );
}

/**
 * Wrap a component so each mounted instance gets its own client state scope.
 *
 * The scope must sit *above* the component, not inside what it returns: a
 * component's hooks run before the elements it returns are mounted, so a
 * provider in its own output would leave its own `useClientState` calls
 * resolving against the enclosing scope and sharing state across instances.
 *
 * The compiler applies this to memo definitions that are real component
 * instance boundaries, leaving optimizer-generated ones untouched so they stay
 * semantically invisible.
 * @param Component The component to wrap.
 * @returns The wrapped component.
 */
export const withClientStateScope = (Component) => {
  const Wrapped = (props) =>
    createElement(ClientStateScope, null, createElement(Component, props));
  Wrapped.displayName = `withClientStateScope(${
    Component.displayName ?? Component.name ?? "Component"
  })`;
  return Wrapped;
};

/**
 * Subscribe to a piece of client state.
 * @param defaultValue The initial value.
 * @param name The name identifying this var. Compiler-generated when the caller
 *   did not choose one, and always a compile-time constant.
 * @param isGlobal When true the name resolves in the root scope, ignoring any
 *   enclosing boundary, so it is shared app-wide and reachable from the backend.
 * @returns A `[value, setValue]` pair, like `useState`.
 */
export function useClientState(defaultValue, name, isGlobal) {
  const contextScope = useContext(ClientStateScopeContext);
  const nearest = contextScope ?? getClientStore().root;
  const scope = isGlobal ? rootOf(nearest) : nearest;

  const bindingRef = useRef(null);
  if (bindingRef.current === null || bindingRef.current.scope !== scope) {
    // Re-resolve when the scope identity changes: binding once would strand a
    // mounted hook on a slot from a scope that no longer applies.
    bindingRef.current = {
      scope,
      slot: scope.find(name) ?? scope.own(name, defaultValue),
    };
  }
  const { slot } = bindingRef.current;

  const value = useSyncExternalStore(
    slot.subscribe,
    slot.getSnapshot,
    slot.getSnapshot,
  );
  return [value, slot.set];
}
