/**
 * Client-only state, shared by name across components without a backend rx.State.
 *
 * `useClientState` is the only thing compiled components call. Everything else
 * here is the bookkeeping it needs: a store of independently-subscribable slots,
 * the context that delivers it, and a module-level door for JS that runs outside
 * the React tree (see `getClientState` / `setClientState`).
 *
 * Each slot owns its own listener set, so writing one var only re-renders the
 * components subscribed to *that* var. The context value is the store object
 * itself and never changes identity, so mounting the provider never cascades.
 */
import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useRef,
  useSyncExternalStore,
} from "react";

import { refs } from "$/utils/state";

/** The single `refs` key holding the live store, for devtools introspection. */
export const CLIENT_STATE_REF = "__client_state";

/**
 * Create a slot: one named (or anonymous) piece of client state.
 * @param value The initial value.
 * @returns A slot with its own listener set.
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
 * Create a store of client state slots.
 * @returns The store.
 */
export const createClientStateStore = () => {
  const slots = new Map();

  /**
   * Get the slot for `name`, creating it if absent.
   * @param name The slot name.
   * @param defaultValue Initial value, used only when creating the slot.
   * @returns The named slot.
   */
  const namedSlot = (name, defaultValue) => {
    let slot = slots.get(name);
    if (slot === undefined) {
      slot = createSlot(defaultValue);
      slots.set(name, slot);
    }
    return slot;
  };

  return {
    /**
     * Resolve the slot a `useClientState` call should bind to.
     * @param name The shared name, or a falsy value for a private slot.
     * @param defaultValue The initial value.
     * @returns A shared slot when named, else a fresh anonymous one.
     */
    slot: (name, defaultValue) =>
      name ? namedSlot(name, defaultValue) : createSlot(defaultValue),
    /**
     * Read a named slot's current value.
     * @param name The slot name.
     * @returns The value, or undefined if the slot does not exist yet.
     */
    get: (name) => slots.get(name)?.value,
    /**
     * Write a named slot, creating it if it does not exist yet, so a value
     * pushed before any component mounts is picked up on mount.
     * @param name The slot name.
     * @param value The value, or an updater function.
     */
    set: (name, value) => {
      namedSlot(name, undefined).set(value);
    },
  };
};

let _clientStore = null;

// How many providers are currently mounted. Several can share one store (an
// embedded app rendered alongside a main app), so the `refs` entry must survive
// until the last of them unmounts.
let _mountedProviders = 0;

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

export const ClientStateContext = createContext(null);

/**
 * Read a named client state var from outside the React tree.
 *
 * A point-in-time snapshot with no reactivity; prefer the value returned by
 * `useClientState` inside components.
 * @param name The client state var name.
 * @returns The current value.
 */
export const getClientState = (name) => getClientStore().get(name);

/**
 * Write a named client state var from outside the React tree.
 *
 * Every subscribed component re-renders. Use this to drive client state from
 * third-party library callbacks or other non-React JS.
 * @param name The client state var name.
 * @param value The value, or an updater function.
 */
export const setClientState = (name, value) => {
  getClientStore().set(name, value);
};

/**
 * Provide the client state store to the tree.
 * @param props The component props.
 * @param props.children The children to render.
 * @returns The provider element.
 */
export function ClientStateProvider({ children }) {
  const storeRef = useRef(null);
  if (storeRef.current === null) {
    // On the client this is the shared singleton, so `setClientState` and the
    // hooks reach the same slots; on the server it is per-render.
    storeRef.current = getClientStore();
  }
  const store = storeRef.current;

  useEffect(() => {
    // Client-only, so the server's module-scope `refs` is never written.
    refs[CLIENT_STATE_REF] = store;
    _mountedProviders += 1;
    return () => {
      _mountedProviders -= 1;
      if (_mountedProviders === 0 && refs[CLIENT_STATE_REF] === store) {
        delete refs[CLIENT_STATE_REF];
      }
    };
  }, [store]);

  return createElement(ClientStateContext.Provider, { value: store }, children);
}

/**
 * Subscribe to a piece of client state.
 * @param defaultValue The initial value.
 * @param name Shared name, or omitted for state private to this component.
 * @returns A `[value, setValue]` pair, like `useState`.
 */
export function useClientState(defaultValue, name) {
  const store = useContext(ClientStateContext) ?? getClientStore();
  const slotRef = useRef(null);
  if (slotRef.current === null) {
    // `name` is a compile-time constant per call site, so the slot a mounted
    // hook is bound to can never change.
    slotRef.current = store.slot(name, defaultValue);
  }
  const slot = slotRef.current;
  const value = useSyncExternalStore(
    slot.subscribe,
    slot.getSnapshot,
    slot.getSnapshot,
  );
  return [value, slot.set];
}
