// What every Reflex app runs on: the helpers compiled pages call, events, and
// the events the browser applies itself. Apps import it through
// utils/state.js, which also re-exports the backend connection of
// utils/transport.js.
import { mergician } from "mergician";
import { useCallback, useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router";
import { eventLoop } from "$/utils/context-registry";
// This module's own exports, passed to the scripts runLocalScript runs.
import * as runtimeExports from "$/utils/runtime";
import {
  CLIENT_STATE_REF,
  getClientState,
  getClientStore,
  setClientState,
} from "$/utils/client_state";
import debounce from "$/utils/helpers/debounce";
import throttle from "$/utils/helpers/throttle";

// What `ClientStateVar.global_value` and `global_set` compile to, exported so
// the server-provided scripts runScript evaluates can call them too.
export { getClientState, setClientState };

// Dictionary holding component references. Internal: not covered by any
// compatibility guarantee. Framework vars reach it through `Var._as_ref()`,
// whose var data imports `refs`. It is also published as a global, only so
// code written against 0.10 that reads `refs[...]` without the import keeps
// working; a module that binds its own `refs` shadows the global.
export const refs = {};
globalThis.refs = refs;

/**
 * Create a ref and register it in `refs` under the given name.
 * @param name The registry key, e.g. "ref_my_id".
 * @returns The ref object.
 */
export const useRegisteredRef = (name) => {
  const ref = useRef(null);
  refs[name] = ref;
  return ref;
};

// The client state store, for code evaluated outside this module's scope: a
// `run_script` body pushing a value, or the devtools console. Client only, so
// a server render never shares a store between requests.
if (typeof document !== "undefined") {
  refs[CLIENT_STATE_REF] = getClientStore();
}

/**
 * Generate a UUID for component identifiers.
 * Taken from: https://stackoverflow.com/questions/105034/how-do-i-create-a-guid-uuid
 * @returns A UUID.
 */
export const generateUUID = () => {
  let d = Date.now(),
    d2 = performance?.now?.() * 1000 || 0;
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    let r = Math.random() * 16;
    if (d > 0) {
      r = ((d + r) % 16) | 0;
      d = Math.floor(d / 16);
    } else {
      r = ((d2 + r) % 16) | 0;
      d2 = Math.floor(d2 / 16);
    }
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
};

/** Append nested events to an output array in depth-first order. */
const appendEvents = (events, normalized) => {
  for (const event of events) {
    if (Array.isArray(event)) {
      appendEvents(event, normalized);
    } else if (event !== undefined && event !== null) {
      normalized.push(event);
    }
  }
};

/**
 * Flatten event lists and discard empty event values.
 * @param events Events or nested event lists.
 * @returns A flat array of events in depth-first order.
 */
export const normalizeEvents = (events) => {
  const normalized = [];
  appendEvents(events, normalized);
  return normalized;
};

/**
 * Check if a string is a valid HTTP URL.
 * @param string The string to check.
 *
 * @returns The URL object if valid, undefined otherwise.
 * */
function urlFrom(string) {
  try {
    return new URL(string);
  } catch {
    return undefined;
  }
}

/**
 * Invoke an event's result callback, if it declared one.
 *
 * A callback sent by the backend arrives as a string built by
 * ``format_queue_events``, which references ``addEvents`` and ``ReflexEvent``;
 * ``runScript`` provides them.
 * @param event The event whose callback to run.
 * @param eval_result The value to pass to the callback, awaited if thenable.
 * @param runScript Runs a script with the given ``addEvents`` in scope.
 */
const applyResultCallback = async (event, eval_result, runScript) => {
  if (!event.payload.callback) {
    return;
  }
  // User code dispatches through addEvents like compiled event triggers do;
  // late-bound so a remounted EventLoopProvider is picked up.
  const addEvents = (...args) => eventLoop.addEvents(...args);
  const final_result =
    !!eval_result && typeof eval_result.then === "function"
      ? await eval_result
      : eval_result;
  const callback =
    typeof event.payload.callback === "string"
      ? runScript(event.payload.callback, addEvents)
      : event.payload.callback;
  callback(final_result);
};

// The events the browser applies itself; any other goes to the backend.
const FRONTEND_EVENTS = new Set([
  "_redirect",
  "_download",
  "_set_focus",
  "_blur_focus",
  "_set_value",
  "_client_state_set",
  "_client_state_get",
  "_call_function",
  "_call_script",
]);

/**
 * Check whether the browser applies an event itself.
 * @param event The event to check.
 * @returns True for an event applyFrontendEvent applies, false for one that
 *   goes to the backend.
 */
export const isFrontendEvent = (event) => FRONTEND_EVENTS.has(event.name);

/**
 * Apply an event the browser handles without the backend.
 * @param event An event isFrontendEvent accepts.
 * @param navigate The navigate function from useNavigate.
 * @param runScript Runs a script with the given ``addEvents`` in scope.
 */
export const applyFrontendEvent = async (event, navigate, runScript) => {
  // User code dispatches through addEvents like compiled event triggers do;
  // late-bound so a remounted EventLoopProvider is picked up.
  const addEvents = (...args) => eventLoop.addEvents(...args);
  if (event.name === "_redirect") {
    if ((event.payload.path ?? undefined) === undefined) {
      return;
    }
    if (event.payload.external) {
      window.open(
        event.payload.path,
        "_blank",
        "noopener" + (event.payload.popup ? ",popup" : ""),
      );
      return;
    }
    const url = urlFrom(event.payload.path);
    let pathname = event.payload.path;
    if (url) {
      if (url.host !== window.location.host) {
        // External URL
        window.location.assign(event.payload.path);
        return;
      } else {
        pathname = url.pathname + url.search + url.hash;
      }
    }
    if (event.payload.replace) {
      navigate(pathname, { replace: true });
    } else {
      navigate(pathname);
    }
    return;
  }

  if (event.name === "_download") {
    const a = document.createElement("a");
    a.hidden = true;
    a.href = event.payload.url;
    a.download = event.payload.filename;
    a.click();
    a.remove();
    return;
  }

  if (event.name === "_set_focus") {
    const ref =
      event.payload.ref in refs ? refs[event.payload.ref] : event.payload.ref;
    const current = ref?.current;
    if (current === undefined || current?.focus === undefined) {
      console.error(
        `No element found for ref ${event.payload.ref} in _set_focus`,
      );
    } else {
      current.focus();
    }
    return;
  }

  if (event.name === "_blur_focus") {
    const ref =
      event.payload.ref in refs ? refs[event.payload.ref] : event.payload.ref;
    const current = ref?.current;
    if (current === undefined || current?.blur === undefined) {
      console.error(
        `No element found for ref ${event.payload.ref} in _blur_focus`,
      );
    } else {
      current.blur();
    }
    return;
  }

  if (event.name === "_set_value") {
    const ref =
      event.payload.ref in refs ? refs[event.payload.ref] : event.payload.ref;
    if (ref.current) {
      ref.current.value = event.payload.value;
    }
    return;
  }

  // Backend reads and writes go to the shared store directly, so a var that no
  // component renders is still reachable.
  if (event.name === "_client_state_set") {
    setClientState(event.payload.var_name, event.payload.value);
    return;
  }

  if (event.name === "_client_state_get") {
    try {
      await applyResultCallback(
        event,
        getClientState(event.payload.var_name),
        runScript,
      );
    } catch (e) {
      console.log("_client_state_get", e);
      if (window?.onerror) {
        window.onerror(e.message, null, null, null, e);
      }
    }
    return;
  }

  if (
    event.name === "_call_function" &&
    typeof event.payload.function !== "string"
  ) {
    try {
      await applyResultCallback(event, event.payload.function(), runScript);
    } catch (e) {
      console.log("_call_function", e);
      if (window?.onerror) {
        window.onerror(e.message, null, null, null, e);
      }
    }
    return;
  }

  if (event.name === "_call_script" || event.name === "_call_function") {
    try {
      const eval_result =
        event.name === "_call_script"
          ? runScript(event.payload.javascript_code, addEvents)
          : runScript(event.payload.function, addEvents)();

      await applyResultCallback(event, eval_result, runScript);
    } catch (e) {
      console.log("_call_script", e);
      if (window?.onerror) {
        window.onerror(e.message, null, null, null, e);
      }
    }
    return;
  }
};

/**
 * Run a script in an app without state.
 *
 * Like ``runScript`` in utils/transport.js, without the transport: the script
 * sees every export of this module (compiled callbacks call ``ReflexEvent``),
 * ``addEvents``, ``navigate`` and ``params``. The exports of utils/state.js
 * would keep the transport it re-exports in the bundle.
 * @param code The JavaScript source to run.
 * @param addEvents The late-bound event dispatcher for this call.
 * @param navigate The navigate function from useNavigate.
 * @param params The params object from useParams.
 * @returns The completion value of the script.
 */
let evalLocalScript;
const runLocalScript = (code, addEvents, navigate, params) => {
  evalLocalScript ??= new Function(
    ...Object.keys(runtimeExports),
    "addEvents",
    "navigate",
    "params",
    "code",
    '"use strict"; return eval(code);',
  );
  return evalLocalScript(
    ...Object.values(runtimeExports),
    addEvents,
    navigate,
    params,
    code,
  );
};

// The connection errors of an app without state: there is no connection.
const NO_CONNECT_ERRORS = Object.freeze([]);

/**
 * Establish the event loop of an app compiled without state.
 *
 * The app has no backend, so nothing connects: events the browser handles
 * itself are applied in order, and any other event is reported as an error.
 * @returns [addEvents, connectErrors], like useEventLoop in utils/transport.js.
 */
export const useLocalEventLoop = () => {
  const navigate = useNavigate();
  const paramsR = useParams();
  // A splat route's segments are kept as a list, so the values are not all strings.
  const params = useRef(
    /** @type {Record<string, string | string[] | undefined>} */ (paramsR),
  );

  useEffect(() => {
    const { "*": splat, ...remainingParams } = paramsR;
    if (splat) {
      params.current = { ...remainingParams, splat: splat.split("/") };
    } else {
      params.current = remainingParams;
    }
  }, [paramsR]);

  const addEvents = useCallback((events, args, event_actions) => {
    const _events = normalizeEvents(events);
    event_actions = Object.assign(
      {},
      event_actions,
      ..._events.map((e) => e.event_actions),
    );
    const runScript = (code, addEvents) =>
      runLocalScript(code, addEvents, navigate, params);
    return applyEventActions(
      async () => {
        for (const event of _events) {
          if (isFrontendEvent(event)) {
            await applyFrontendEvent(event, navigate, runScript);
          } else {
            console.error(
              `The event "${event.name}" needs the backend, but this app is compiled without state (rx.App(enable_state=False)).`,
            );
          }
        }
      },
      event_actions,
      args,
      _events.map((e) => e.name).join("+++"),
    );
  }, []);

  return [addEvents, NO_CONNECT_ERRORS];
};

/**
 * Create an event object.
 * @param {string} name The name of the event.
 * @param {Object.<string, any>} payload The payload of the event.
 * @param {Object.<string, (number|boolean)>} event_actions The actions to take on the event.
 * @param {string} handler The client handler to process event.
 * @returns The event object.
 */
export const ReflexEvent = (
  name,
  payload = {},
  event_actions = {},
  handler = null,
) => {
  const e = { name };
  if (payload && Object.keys(payload).length > 0) {
    e.payload = payload;
  }
  if (event_actions && Object.keys(event_actions).length > 0) {
    e.event_actions = event_actions;
  }
  if (handler !== null) {
    e.handler = handler;
  }
  return e;
};

/**
 * Apply event actions before invoking a target function.
 * @param {Function} target The function to invoke after applying event actions.
 * @param {{preventDefault?: boolean, stopPropagation?: boolean, temporal?: boolean, throttle?: number, debounce?: number}} event_actions The actions to apply.
 * @param {Array<any>|any} args The event args.
 * @param {string|null} action_key A stable key for debounce/throttle tracking.
 * @param {Function|null} temporal_handler Returns whether temporal actions may run.
 * @returns The target result, if it runs immediately.
 */
export const applyEventActions = (
  target,
  event_actions = {},
  args = [],
  action_key = null,
  temporal_handler = null,
) => {
  if (!Array.isArray(args)) {
    args = [args];
  }

  const _e = args.find((o) => o?.preventDefault !== undefined);

  if (event_actions?.preventDefault && _e?.preventDefault) {
    _e.preventDefault();
  }
  if (event_actions?.stopPropagation && _e?.stopPropagation) {
    _e.stopPropagation();
  }
  if (event_actions?.temporal && temporal_handler && !temporal_handler()) {
    return;
  }

  const invokeTarget = () => target(...args);
  const resolved_action_key = action_key ?? target.toString();

  if (event_actions?.throttle) {
    if (!throttle(resolved_action_key, event_actions.throttle)) {
      return;
    }
  }
  if (event_actions?.debounce) {
    debounce(resolved_action_key, invokeTarget, event_actions.debounce);
    return;
  }
  return invokeTarget();
};

/***
 * Check if a value is truthy in python.
 * @param val The value to check.
 * @returns True if the value is truthy, false otherwise.
 */
export const isTrue = (val) => {
  if (Array.isArray(val)) return val.length > 0;
  if (val === Object(val)) return Object.keys(val).length > 0;
  return Boolean(val);
};

/***
 * Check if a value is not null or undefined.
 * @param val The value to check.
 * @returns True if the value is not null or undefined, false otherwise.
 */
export const isNotNullOrUndefined = (val) => {
  return (val ?? undefined) !== undefined;
};

/***
 * Python-semantics OR: returns `a` if python-truthy, else evaluates and returns `b`.
 * `b` is a thunk so it is only evaluated when needed, preserving short-circuit.
 * @template A
 * @template B
 * @param {A} a The left-hand value.
 * @param {() => B} b Thunk producing the right-hand value.
 * @returns {A | B} `a` if python-truthy, otherwise the result of `b()`.
 */
export const pyOr = (a, b) => (isTrue(a) ? a : b());

/***
 * Python-semantics AND: returns `a` if python-falsy, else evaluates and returns `b`.
 * `b` is a thunk so it is only evaluated when needed, preserving short-circuit.
 * @template A
 * @template B
 * @param {A} a The left-hand value.
 * @param {() => B} b Thunk producing the right-hand value.
 * @returns {A | B} `a` if python-falsy, otherwise the result of `b()`.
 */
export const pyAnd = (a, b) => (isTrue(a) ? b() : a);

/***
 * Python-semantics modulo: the result takes the sign of the divisor
 * (`pyMod(-7, 3)` is 2), where JavaScript's `%` takes the dividend's (-1).
 * A zero result is 0, like Python's int `%`. With `float` set, it takes the
 * divisor's sign, like Python's float `%` (`6.0 % -3.0` is -0.0).
 * @param {number} a The dividend.
 * @param {number} b The divisor.
 * @param {boolean} [float] Whether an operand is a Python float.
 * @returns {number} The remainder of `a / b` with the sign of `b`.
 */
export const pyMod = (a, b, float = false) => {
  const r = a % b;
  if (r === 0) return float && b < 0 ? -0 : 0;
  return r < 0 !== b < 0 ? r + b : r;
};

/***
 * Python-semantics str.lstrip: remove leading characters in the given set.
 * @param {string} s The string to strip.
 * @param {string?} chars Characters to remove; null/undefined strips whitespace.
 * @returns {string} The stripped string.
 */
export const pyLstrip = (s, chars) => {
  if (chars == null) return s.trimStart();
  const charSet = new Set(chars);
  let start = 0;
  while (start < s.length) {
    const cp = String.fromCodePoint(s.codePointAt(start));
    if (!charSet.has(cp)) break;
    start += cp.length;
  }
  return s.slice(start);
};

/***
 * Python-semantics str.rstrip: remove trailing characters in the given set.
 * @param {string} s The string to strip.
 * @param {string?} chars Characters to remove; null/undefined strips whitespace.
 * @returns {string} The stripped string.
 */
export const pyRstrip = (s, chars) => {
  if (chars == null) return s.trimEnd();
  const charSet = new Set(chars);
  let end = s.length;
  while (end > 0) {
    // step back over a full code point (surrogate pairs are 2 units wide)
    let cp = s[end - 1];
    if (end > 1) {
      const pair = String.fromCodePoint(s.codePointAt(end - 2));
      if (pair.length === 2) cp = pair;
    }
    if (!charSet.has(cp)) break;
    end -= cp.length;
  }
  return s.slice(0, end);
};

/***
 * Python-semantics str.strip: remove leading and trailing characters in the given set.
 * @param {string} s The string to strip.
 * @param {string?} chars Characters to remove; null/undefined strips whitespace.
 * @returns {string} The stripped string.
 */
export const pyStrip = (s, chars) =>
  chars == null ? s.trim() : pyRstrip(pyLstrip(s, chars), chars);

const SURROGATE_RE = /[\uD800-\uDFFF]/;

/***
 * Python-semantics code points of a string, skipping the copy when possible.
 * A string without surrogates has one code unit per code point, so it is
 * returned as-is and its native length/at/slice already match Python.
 * @param {string?} s The string; null/undefined counts as "".
 * @returns {string | string[]} The string itself, or its code points.
 */
const codePoints = (s) => {
  s ??= "";
  return SURROGATE_RE.test(s) ? Array.from(s) : s;
};

/***
 * Python-semantics len(s): count code points, not UTF-16 code units.
 * @param {string?} s The string.
 * @returns {number} The number of code points.
 */
export const pyStrLength = (s) => codePoints(s).length;

/***
 * Python-semantics s[i]: index by code point.
 * @param {string?} s The string.
 * @param {number} i The index; negative counts from the end.
 * @returns {string | undefined} The code point, or undefined out of range.
 */
export const pyStrAt = (s, i) => codePoints(s).at(i);

/***
 * Python-semantics s[start:stop]: slice by code point.
 * @param {string?} s The string.
 * @param {number?} start The start index; null/undefined slices from the start.
 * @param {number?} stop The stop index; null/undefined slices to the end.
 * @returns {string} The sliced string.
 */
export const pyStrSlice = (s, start, stop) => {
  const chars = codePoints(s);
  const slice = chars.slice(start ?? 0, stop ?? chars.length);
  return typeof slice === "string" ? slice : slice.join("");
};

/***
 * Python-semantics list(s): split a string into code points.
 * @param {string?} s The string.
 * @returns {string[]} The code points.
 */
export const pyStrChars = (s) => {
  const chars = codePoints(s);
  return typeof chars === "string" ? chars.split("") : chars;
};

/***
 * JS s.split(sep), except that an empty separator splits by code point like
 * Python list(s).
 * @param {string?} s The string.
 * @param {string} sep The separator.
 * @returns {string[]} The parts.
 */
export const pyStrSplit = (s, sep) =>
  sep === "" ? pyStrChars(s) : s.split(sep);

/***
 * Python-semantics flat map: map each element through fn and concatenate the
 * results, iterating each one the way Python does (arrays yield their
 * elements, strings yield characters, objects yield their keys).
 * @param {Array} arr The array to map over.
 * @param {Function} fn The mapping function applied to each element.
 * @returns {Array} The flattened array of mapped results.
 */
export const pyFlatMap = (arr, fn) =>
  arr.flatMap((element) => {
    const value = fn(element);
    if (Array.isArray(value)) return value;
    if (typeof value === "string") return Array.from(value);
    if (value === Object(value)) return Object.keys(value);
    throw new TypeError(`flat_map value is not iterable: ${value}`);
  });

/**
 * Merge refs into a single callback ref, attaching the node to all of them.
 *
 * Handles ref objects and callback refs, including React 19 callback refs
 * that return a cleanup function.
 * @param refsToMerge The refs to merge.
 * @returns The merged callback ref.
 */
export const mergeRefs =
  (...refsToMerge) =>
  (node) => {
    const cleanups = refsToMerge.map((ref) => {
      if (ref == null) {
        return null;
      }
      if (typeof ref === "function") {
        const cleanup = ref(node);
        return typeof cleanup === "function" ? cleanup : () => ref(null);
      }
      ref.current = node;
      return () => {
        ref.current = null;
      };
    });
    return () => {
      for (const cleanup of cleanups) {
        cleanup?.();
      }
    };
  };

// Composed refs and event handlers, keyed by the identity of the (own,
// injected) pair they were built from. A mounted wrapper rerendering with
// stable inputs gets the same composed function back, so React sees an
// unchanged prop: refs are not detached and reattached (no callback cleanup,
// no transient nulling of object refs) and a memoized root keeps its bailout.
// Both levels are weak, so an entry dies with whichever input dies first.
const composedRefCache = new WeakMap();
const composedHandlerCache = new WeakMap();

const canWeakKey = (value) =>
  value !== null && (typeof value === "object" || typeof value === "function");

const composeCached = (cache, own, injected, compose) => {
  if (!canWeakKey(own) || !canWeakKey(injected)) {
    return compose(own, injected);
  }
  let byInjected = cache.get(own);
  if (byInjected === undefined) {
    byInjected = new WeakMap();
    cache.set(own, byInjected);
  }
  let composed = byInjected.get(injected);
  if (composed === undefined) {
    composed = compose(own, injected);
    byInjected.set(injected, composed);
  }
  return composed;
};

const composeHandlers =
  (own, injected) =>
  (...args) => {
    own(...args);
    injected(...args);
  };

// Props named `on` followed by an uppercase letter are event handlers and get
// composed rather than overridden. Hoisted because evaluating a regex literal
// allocates a new RegExp every time.
const EVENT_HANDLER_PROP = /^on[A-Z]/;

// Whether a prop value can be deeply merged: plain objects only — never
// arrays, React elements (tagged with $$typeof), or class instances.
const isPlainObjectProp = (value) => {
  if (
    typeof value !== "object" ||
    value === null ||
    value.$$typeof !== undefined
  ) {
    return false;
  }
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
};

/**
 * Merge props injected by a parent at runtime (e.g. a Radix Slot cloning its
 * child) with a component's own compiled-in props.
 *
 * Follows Radix Slot semantics with the own props in the child role: own
 * props win for plain props, `on*` event handlers compose (own handler first,
 * then the injected one), refs compose via `mergeRefs`, `className` strings
 * concatenate, and object-valued props (e.g. `style`) merge deeply via
 * `mergician` with own keys winning. A prop the own side declares but leaves
 * valueless falls through to the injected value.
 *
 * Composed refs and handlers keep a stable identity for as long as the props
 * they were composed from do, so merging never re-triggers a ref attach or
 * defeats a memoized root's bailout. With nothing injected the own props
 * object is returned unchanged, so the common (non-Slot) call site renders
 * exactly as it did before.
 * @param injectedProps The props injected by the parent at runtime.
 * @param ownProps The component's own compiled-in props.
 * @param refProp The prop carrying the root's DOM ref when the root does not
 * accept `ref` directly (e.g. DebounceInput's `inputRef`, a class component
 * whose `ref` would resolve to the instance). An injected ref is routed there
 * and `ref` itself is never emitted.
 * @returns The merged props object.
 */
export const mergeSlotProps = (injectedProps, ownProps, refProp) => {
  let hasInjected = false;
  for (const _ in injectedProps) {
    hasInjected = true;
    break;
  }
  if (!hasInjected) {
    return ownProps;
  }
  const merged = { ...injectedProps, ...ownProps };
  if (refProp !== undefined) {
    const injectedRef = injectedProps.ref;
    delete merged.ref;
    if (injectedRef != null) {
      const own = ownProps[refProp];
      merged[refProp] =
        own == null
          ? injectedRef
          : composeCached(composedRefCache, own, injectedRef, mergeRefs);
    }
  }
  for (const propName in ownProps) {
    const injected = injectedProps[propName];
    if (injected == null || propName === refProp) {
      continue;
    }
    const own = ownProps[propName];
    if (own == null) {
      // The own side has no value for this prop, so the spread above
      // shadowed the injection with null/undefined. Keep the injection.
      merged[propName] = injected;
    } else if (EVENT_HANDLER_PROP.test(propName)) {
      merged[propName] =
        own && injected
          ? composeCached(composedHandlerCache, own, injected, composeHandlers)
          : own || injected;
    } else if (propName === "ref") {
      merged[propName] = composeCached(
        composedRefCache,
        own,
        injected,
        mergeRefs,
      );
    } else if (propName === "className") {
      merged[propName] =
        own && injected ? injected + " " + own : own || injected;
    } else if (isPlainObjectProp(injected) && isPlainObjectProp(own)) {
      // Own is a fresh object literal every render, so there is no identity
      // to cache the merge under — merge directly.
      merged[propName] = mergician(injected, own);
    }
  }
  return merged;
};

/**
 * Get the value from a ref.
 * @param ref The ref to get the value from.
 * @returns The value.
 */
export const getRefValue = (ref) => {
  if (!ref || !ref.current) {
    return null;
  }
  if (ref.current.type === "checkbox") {
    return ref.current.checked; // chakra
  } else if (
    ref.current.className?.includes("rt-CheckboxRoot") ||
    ref.current.className?.includes("rt-SwitchRoot")
  ) {
    return ref.current.ariaChecked === "true"; // radix
  } else if (ref.current.className?.includes("rt-SliderRoot")) {
    // find the actual slider
    return ref.current.querySelector(".rt-SliderThumb")?.ariaValueNow;
  } else {
    //querySelector(":checked") is needed to get value from radio_group
    return (
      ref.current.value ??
      ref.current.querySelector?.(":checked")?.value ??
      null
    );
  }
};

/**
 * Get the values from a ref array.
 * @param refs The refs to get the values from.
 * @returns The values array.
 */
export const getRefValues = (refs) => {
  if (!refs) {
    return;
  }
  // getAttribute is used by RangeSlider because it doesn't assign value
  return refs.map((ref) =>
    ref.current
      ? ref.current.value || ref.current.getAttribute("aria-valuenow")
      : null,
  );
};

/**
 * Spread two arrays or two objects.
 * @param first The first array or object.
 * @param second The second array or object.
 * @returns The final merged array or object.
 */
export const spreadArraysOrObjects = (first, second) => {
  if (Array.isArray(first) && Array.isArray(second)) {
    return [...first, ...second];
  } else if (typeof first === "object" && typeof second === "object") {
    return { ...first, ...second };
  } else {
    throw new Error("Both parameters must be either arrays or objects.");
  }
};

// Wire key wrapping a form's ordered [name, value] entries; must match
// FORM_DATA_ENTRIES_KEY in reflex_base.utils.form.
const FORM_DATA_ENTRIES_KEY = "__reflex_form_data__";
const formDataEntries = Symbol("formDataEntries");

/**
 * Collect the fields of a submitted form.
 * @param form The form element.
 * @param refValues Values read from the refs of controls with an id, keyed by
 * the id. Each replaces the form's own entry of the same name, unless the form
 * submitted that name more than once.
 * @returns An object mapping each field name to its last value, which also
 * carries every entry so repeated names reach the backend.
 */
export const getFormData = (form, refValues = {}) => {
  const formEntries = [...new FormData(form).entries()];
  const counts = new Map();
  for (const [name] of formEntries) {
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  const refEntries = Object.entries(refValues).filter(
    ([name]) => !(counts.get(name) > 1),
  );
  // Replace submitted values in place, then add the refs the form did not
  // submit, as spreading the refs over the form's entries would.
  const replaced = new Map(refEntries);
  const entries = formEntries.map(([name, value]) => [
    name,
    replaced.has(name) ? replaced.get(name) : value,
  ]);
  entries.push(...refEntries.filter(([name]) => !counts.has(name)));
  return Object.defineProperty(Object.fromEntries(entries), formDataEntries, {
    value: entries,
  });
};

/**
 * Wrap the form data among an event's arguments as its ordered entries.
 *
 * Done before the event reaches Socket.IO: its binary attachment handling (a
 * form with a file input) copies objects without their symbol-keyed entries.
 * @param event The event to send.
 * @returns The event, copied with wrapped entries when it carries form data.
 */
export const encodeFormDataArgs = (event) => {
  let payload;
  for (const [name, value] of Object.entries(event.payload ?? {})) {
    const entries = value?.[formDataEntries];
    if (entries) {
      payload ??= { ...event.payload };
      payload[name] = { [FORM_DATA_ENTRIES_KEY]: entries };
    }
  }
  return payload ? { ...event, payload } : event;
};
