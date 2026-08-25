// Applying state deltas received from the backend.
//
// Deltas are JSON, so every incoming value is a fresh object/array reference
// even when it is structurally identical to what the frontend already holds.
// Handing those new references to React invalidates every memoized consumer of
// the var, so values that did not actually change are dropped here instead.

/**
 * Compare two delta/state values structurally.
 *
 * Only JSON-shaped values (primitives, arrays and plain objects) are compared
 * by content; anything else falls back to reference equality, which is safe
 * because a false negative just means the delta gets applied as before.
 * @param a The value currently held in the state.
 * @param b The value received in the delta.
 * @returns Whether the two values are equivalent.
 */
export const isEquivalent = (a, b) => {
  if (a === b) {
    return true;
  }
  if (
    typeof a !== "object" ||
    typeof b !== "object" ||
    a === null ||
    b === null
  ) {
    return false;
  }
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) {
      return false;
    }
    for (let i = 0; i < a.length; i++) {
      if (!isEquivalent(a[i], b[i])) {
        return false;
      }
    }
    return true;
  }
  // Dates, Maps, class instances and the like are not structurally comparable.
  if (
    Object.getPrototypeOf(a) !== Object.prototype ||
    Object.getPrototypeOf(b) !== Object.prototype
  ) {
    return false;
  }
  const a_keys = Object.keys(a);
  if (a_keys.length !== Object.keys(b).length) {
    return false;
  }
  for (const key of a_keys) {
    if (!Object.hasOwn(b, key) || !isEquivalent(a[key], b[key])) {
      return false;
    }
  }
  return true;
};

/**
 * Apply a delta to the state.
 *
 * Keys whose incoming value is equivalent to the one already held are skipped,
 * keeping the existing reference. When the whole delta is a no-op the original
 * state object is returned, so `useReducer` bails out of the re-render.
 * @param state The state to apply the delta to.
 * @param delta The delta to apply.
 * @returns The updated state, or the given state if nothing changed.
 */
export const applyDelta = (state, delta) => {
  let next;
  for (const key in delta) {
    if (Object.hasOwn(state, key) && isEquivalent(state[key], delta[key])) {
      continue;
    }
    (next ??= { ...state })[key] = delta[key];
  }
  return next ?? state;
};
