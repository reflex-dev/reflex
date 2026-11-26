// The connection of a Reflex app to its backend: the socket, hydration, state
// deltas, browser storage synced with state vars, uploads and cookies. Apps
// without state never import it. Nothing here runs when the module loads, so
// a build can drop it, and socket.io with it, when nothing calls into it.
import io from "socket.io-client";
import env from "$/env.json";
import Cookies from "universal-cookie";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  useLocation,
  useNavigate,
  useSearchParams,
  useParams,
} from "react-router";
import { app } from "$/utils/context-registry";
// Every export of utils/state.js, passed to server-provided scripts by runScript.
import * as stateExports from "$/utils/state";
import {
  ReflexEvent,
  applyEventActions,
  applyFrontendEvent,
  encodeFormDataArgs,
  generateUUID,
  isFrontendEvent,
  normalizeEvents,
  refs,
} from "$/utils/runtime";
import { parseJson } from "$/utils/helpers/json";
import { uploadFiles } from "$/utils/helpers/upload";

// Endpoint URLs.
const EVENTURL = env.EVENT;

// Socket event names (must match reflex_base/constants/event.py SocketEvent)
const CLIENT_ERROR_EVENT = "client_error";
const STATE_MISMATCH_EVENT = "state_mismatch";
const SESSION_REFRESH_EVENT = "session_refresh";

// sessionStorage key with the time of the last automatic reload (must match
// LAST_RELOADED_KEY in reflex/state.py: the reload on a frontend error and the
// reload on a state mismatch share one cooldown, so neither can loop).
const LAST_RELOADED_KEY = "reflex_last_reloaded_on_error";

// The id of the banner offering a reload when one already happened recently.
const NEW_VERSION_BANNER_ID = "reflex-new-version-banner";

// The cancelable window event dispatched before a prod page acts on a state
// mismatch; a listener calling preventDefault() handles the mismatch instead.
const STATE_MISMATCH_WINDOW_EVENT = "reflex:state-mismatch";

// Client error types (must match reflex_base/constants/event.py ClientErrorType)
const ERROR_TYPE_DISPATCH_MISSING = "dispatch_function_missing";
const ERROR_TYPE_STATE_UPDATE = "state_update_processing_error";
const ERROR_TYPE_HYDRATION_PAYLOAD_TOO_LARGE = "hydration_payload_too_large";

// These hostnames indicate that the backend and frontend are reachable via the same domain.
// They are compared with URL.hostname, which gives an IPv6 address in brackets
// and in its shortest form: "[::]" is every spelling of the IPv6 wildcard.
const SAME_DOMAIN_HOSTNAMES = ["localhost", "0.0.0.0", "[::]"];

// Global variable to hold the token.
let token;

// Share cookie exchange and refresh requests in this tab.
let initialSessionExchange;

// The cookie instance, created on first use.
let cookies;
const getCookies = () => (cookies ??= new Cookies());

// Array holding pending events to be processed.
const event_queue = [];

// The event that sends browser storage values to the backend.
const UPDATE_VARS_INTERNAL =
  "reflex___state____update_vars_internal_state.update_vars_internal";
// A frontend event naming one synced localStorage var, turned into an
// UPDATE_VARS_INTERNAL event when it is sent: see syncLocalStorageEvent.
const SYNC_LOCAL_STORAGE = "_sync_local_storage";

// Synced localStorage values sent to the backend and not yet echoed back, by
// state key, oldest first, with this tab's localStorage write count at the send.
const sentStorageValues = {};
// Bounds a key whose echoes a get_delta override changes, so they never match.
const MAX_SENT_STORAGE_VALUES = 256;
// This tab's localStorage write count, and its last write by storage name
// (vars of different state keys may share one).
let localStorageWrites = 0;
const lastLocalStorageWrites = {};

// Mirrors the data router's location so applyEvent can populate router_data
// with the in-widget URL. In embed mode the host page's window.location is
// unrelated to the Reflex route, so the backend's on_load and dynamic-route
// matching rely on this ref instead. Updated by useEventLoop once mounted;
// pre-seeded in embed mode with the memory router's initial path (see
// initialEntries in entry.client.embed.js) so events dispatched before the
// first effect commit don't briefly fall back to the host page's URL.
const locationRef = {
  current: env.MOUNT_TARGET ? { pathname: "/", search: "", hash: "" } : null,
};

/**
 * Get the token for the current session.
 * @returns The token.
 */
export const getToken = () => {
  if (token) {
    return token;
  }
  if (typeof window !== "undefined") {
    token =
      window.sessionStorage.getItem(clientTokenStorageKey()) ||
      window.sessionStorage.getItem(LEGACY_TOKEN_STORAGE_KEY) ||
      "";
  }
  return token || "";
};

/** Get the saved client token to warm the transport before the app mounts. */
const peekToken = () =>
  token ||
  window.sessionStorage.getItem(clientTokenStorageKey()) ||
  window.sessionStorage.getItem(LEGACY_TOKEN_STORAGE_KEY) ||
  "";

/**
 * Get the URL for the backend server
 * @param url_str The URL string to parse.
 * @returns The given URL modified to point to the actual backend server.
 */
export const getBackendURL = (url_str) => {
  if ((url_str ?? undefined) === undefined) {
    url_str = env.PING;
  }
  // Get backend URL object from the endpoint.
  const endpoint = new URL(url_str);
  if (
    typeof window !== "undefined" &&
    SAME_DOMAIN_HOSTNAMES.includes(endpoint.hostname)
  ) {
    // Use the frontend domain to access the backend
    const frontend_hostname = window.location.hostname;
    endpoint.hostname = frontend_hostname;
    if (window.location.protocol === "https:") {
      if (endpoint.protocol === "ws:") {
        endpoint.protocol = "wss:";
      } else if (endpoint.protocol === "http:") {
        endpoint.protocol = "https:";
      }
      endpoint.port = ""; // Assume websocket is on https port via load balancer.
    }
  }
  return endpoint;
};

/** Namespace browser state by the backend URL, including its port and path. */
const sessionStorageKey = () => `reflex:${getBackendURL(EVENTURL).href}`;
const LEGACY_TOKEN_STORAGE_KEY = "token";
const clientTokenStorageKey = () => `${sessionStorageKey()}:token`;
const sessionRefreshStorageKey = () => `${sessionStorageKey()}:expires_at`;

/** Store only the non-secret tab routing token in JavaScript-accessible storage. */
const setToken = (value) => {
  token = value;
  window.sessionStorage.setItem(clientTokenStorageKey(), value);
};

/** Wait until credentialed HTTP calls can use the initial session cookie. */
export const waitForSession = async () => {
  await initialSessionExchange;
};

/** Exchange an in-band credential or refresh the HTTP-only session cookie. */
const ensureSession = async (sessionCredential, controller) => {
  const endpoint = getBackendURL(EVENTURL);
  endpoint.protocol = endpoint.protocol === "wss:" ? "https:" : "http:";
  endpoint.pathname = endpoint.pathname.replace(
    /\/_event\/?$/,
    "/_reflex/session",
  );
  endpoint.search = "";
  const headers = { "Content-Type": "application/json" };
  const previousToken = getToken();
  if (previousToken) headers["Reflex-Client-Token"] = previousToken;
  // Abort a stalled cookie exchange after ten seconds.
  const timeout = window.setTimeout(() => controller.abort(), 10000);
  try {
    const response = await window.fetch(endpoint.href, {
      method: "POST",
      credentials: "include",
      headers,
      body: JSON.stringify(
        sessionCredential ? { session_token: sessionCredential } : {},
      ),
      signal: controller.signal,
    });
    if (!response.ok) {
      /** @type {Error & { status?: number }} */
      const error = new Error(`Session request failed: ${response.status}`);
      error.status = response.status;
      throw error;
    }
    const session = await response.json();
    if (
      typeof session.client_token !== "string" ||
      !session.client_token ||
      !Number.isFinite(session.expires_in) ||
      session.expires_in <= 0
    ) {
      throw new Error("Invalid session response");
    }
    return session;
  } finally {
    window.clearTimeout(timeout);
  }
};

/**
 * Check if the backend is disabled.
 *
 * @returns True if the backend is disabled, false otherwise.
 */
export const isBackendDisabled = () => {
  const cookie = document.cookie
    .split("; ")
    .find((row) => row.startsWith("backend-enabled="));
  return cookie !== undefined && cookie.split("=")[1] === "false";
};

/**
 * Create a socket without starting its namespace or hydration events.
 * @param endpoint The backend URL.
 * @param transports The configured transports.
 * @param token The session token the backend links the connection to.
 * @returns The disconnected socket.
 */
const createSocket = (endpoint, transports, token) =>
  io(endpoint.href, {
    path: endpoint.pathname,
    transports,
    protocols: [env.REFLEX_VERSION],
    autoUnref: false,
    autoConnect: false,
    withCredentials: true,
    query: { token },
    reconnection: false,
  });

/**
 * Measure encoded text the way the Engine.IO server limits a frame.
 * @param frame The encoded text.
 * @param transport The transport that carries it.
 * @returns The code points for a websocket text frame, or the UTF-8 bytes for a polling body.
 */
const frameSize = (frame, transport) => {
  if (transport !== "websocket") {
    return new TextEncoder().encode(frame).byteLength;
  }
  let size = 0;
  for (const _ of frame) size++;
  return size;
};

let warmSocket = null;
let cancelWarmup = () => {};
let socketStarted = false;

/** Close an unclaimed transport and remove its cleanup handlers. */
const discardWarmSocket = () => {
  const socket = warmSocket;
  warmSocket = null;
  cancelWarmup();
  socket?.disconnect();
};

/**
 * Start only the transport while React is still preparing to mount.
 *
 * The namespace stays disconnected until connect() installs all its handlers.
 * The context module of an app with state calls this once it has registered
 * the app; deferred past module evaluation, so every module has loaded.
 */
export const warmUpTransport = () => {
  if (typeof window !== "undefined") {
    queueMicrotask(() => {
      if (
        socketStarted ||
        Object.keys(app.initialState ?? {}).length <= 1 ||
        isBackendDisabled() ||
        document.visibilityState === "hidden"
      ) {
        return;
      }
      try {
        // A cold transport would capture cookies before the shared session lock.
        if (
          !(
            Number(window.localStorage.getItem(sessionRefreshStorageKey())) >
            Date.now()
          )
        ) {
          return;
        }
        warmSocket = createSocket(
          getBackendURL(EVENTURL),
          [env.TRANSPORT],
          peekToken(),
        );
      } catch {
        // Speculative setup may fail (for example, blocked session storage).
        // The normal connection path will report failures when the app mounts.
        return;
      }
      const timeout = setTimeout(discardWarmSocket, 10000);
      window.addEventListener("pagehide", discardWarmSocket);
      cancelWarmup = () => {
        clearTimeout(timeout);
        window.removeEventListener("pagehide", discardWarmSocket);
      };
      warmSocket.io.open((error) => {
        if (error) discardWarmSocket();
      });
    });
  }

  if (import.meta.hot) {
    import.meta.hot.dispose(() => {
      socketStarted = true;
      discardWarmSocket();
    });
  }
};

/**
 * Determine if any event in the event queue is stateful.
 *
 * @returns True if there's any event that requires state and False if none of them do.
 */
export const isStateful = () => {
  if (event_queue.length === 0) {
    return false;
  }
  return event_queue.some(
    (event) =>
      typeof event?.name === "string" &&
      (event.name.startsWith("reflex___state") ||
        event.name === SYNC_LOCAL_STORAGE),
  );
};

/**
 * Whether a value is a plain object (not an array, Date or class instance).
 * @param value The value to check.
 * @returns True if the value is a plain object.
 */
const isPlainObject = (value) => {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
};

/**
 * Structurally share the parts of next that deep-equal prev.
 *
 * Plain objects and arrays whose contents are unchanged keep the identity of
 * the previous value, so memoized components and caches keyed on identity
 * still hit. Any other value is taken from next as is.
 * @param prev The previous value.
 * @param next The new value.
 * @returns prev if deep-equal to next, otherwise next with unchanged parts shared from prev.
 */
const replaceEqualDeep = (prev, next) => {
  // Object.is, unlike ===, tells -0 from 0 and treats NaN as equal to itself.
  if (Object.is(prev, next)) {
    return prev;
  }
  if (Array.isArray(prev) && Array.isArray(next)) {
    // Allocate only once an element differs; until then prev is the result.
    let out;
    for (let i = 0; i < next.length; i++) {
      const value = replaceEqualDeep(prev[i], next[i]);
      if (out === undefined && !Object.is(value, prev[i])) {
        out = prev.slice(0, i);
      }
      out?.push(value);
    }
    if (out !== undefined) {
      return out;
    }
    return prev.length === next.length ? prev : prev.slice(0, next.length);
  }
  if (isPlainObject(prev) && isPlainObject(next)) {
    const keys = Object.keys(next);
    /** @type {Record<string, any>} */
    let out;
    // Spreading next keeps a JSON "__proto__" key an own data property, so the
    // assignments below never hit the prototype setter.
    const copyPrefix = (end) => {
      out = { ...next };
      for (let j = 0; j < end; j++) {
        out[keys[j]] = prev[keys[j]];
      }
    };
    for (let i = 0; i < keys.length; i++) {
      const key = keys[i];
      if (!Object.hasOwn(prev, key)) {
        if (out === undefined) {
          copyPrefix(i);
        }
        continue;
      }
      const value = replaceEqualDeep(prev[key], next[key]);
      if (out === undefined && !Object.is(value, prev[key])) {
        copyPrefix(i);
      }
      if (out !== undefined) {
        out[key] = value;
      }
    }
    if (out !== undefined) {
      return out;
    }
    // Mappings render in key order, so prev is only reused with the same keys
    // in the same order.
    const prevKeys = Object.keys(prev);
    if (
      prevKeys.length === keys.length &&
      prevKeys.every((key, i) => key === keys[i])
    ) {
      return prev;
    }
    // Keys were removed or reordered; every remaining value is unchanged.
    copyPrefix(keys.length);
    return out;
  }
  return next;
};

/**
 * Apply a delta to the state.
 *
 * Unchanged values keep their previous identity, and a delta that changes
 * nothing returns the same state object so useReducer skips the render.
 * @param state The state to apply the delta to.
 * @param delta The delta to apply.
 * @returns The new state, or state itself if nothing changed.
 */
export const applyDelta = (state, delta) => {
  let out;
  for (const key in delta) {
    const own = Object.hasOwn(state, key);
    const value = own ? replaceEqualDeep(state[key], delta[key]) : delta[key];
    if (!own || !Object.is(value, state[key])) {
      out ??= { ...state };
      out[key] = value;
    }
  }
  return out ?? state;
};

/**
 * Evaluate a dynamic component.
 * @param component The component to evaluate.
 * @returns The evaluated component.
 */
export const evalReactComponent = async (component) => {
  if (!window.React && window.__reflex) {
    window.React = window.__reflex.react;
  }
  // The library list is always on the first line of the generated module.
  const marker = "//__reflex_evaluate:";
  if (component.startsWith(marker)) {
    const libraries = component.slice(marker.length, component.indexOf("\n"));
    await window.__reflex_load?.(JSON.parse(libraries));
  }
  const encodedJs = encodeURIComponent(component);
  const dataUri = "data:text/javascript;charset=utf-8," + encodedJs;
  const module = await import(/* @vite-ignore */ dataUri);
  return module.default;
};

/**
 * Only Queue and process events when websocket connection exists.
 * @param event The event to queue.
 * @param socket The socket object to send the event on.
 * @param navigate The navigate function from React Router
 * @param params The params object from React Router
 *
 * @returns Adds event to queue and processes it if websocket exits, does nothing otherwise.
 */
export const queueEventIfSocketExists = async (
  events,
  socket,
  navigate,
  params,
) => {
  if (!socket) {
    return;
  }
  await queueEvents(events, socket, false, navigate, params);
};

/**
 * Run server-provided JavaScript with the exports of utils/state.js in scope.
 *
 * Callback strings and `rx.call_script` code reference helpers compiled
 * pages import from there (`ReflexEvent`, `pyMod`, `isTrue`, ...), and apps
 * written against the former direct eval also use `socket`, `navigate`,
 * `params` and `token`. A direct eval would see them, but it also stops the
 * minifier from mangling every name in the chunk that holds it, so the code
 * is compiled with the Function constructor and those names are passed in as
 * parameters. The eval inside the body still runs the code as a strict
 * script, so statements keep their completion value.
 *
 * Compiled on first use: a Content Security Policy without `unsafe-eval`
 * rejects the Function constructor, and apps that never send scripts must
 * still load.
 *
 * @param code The JavaScript source to run.
 * @param addEvents The late-bound event dispatcher for this call.
 * @param socket The socket object to send events on.
 * @param navigate The navigate function from useNavigate.
 * @param params The params object from useParams.
 * @returns The completion value of the script.
 */
let evalInScope;
const runScript = (code, addEvents, socket, navigate, params) => {
  evalInScope ??= new Function(
    ...Object.keys(stateExports),
    "addEvents",
    "socket",
    "navigate",
    "params",
    "token",
    "code",
    '"use strict"; return eval(code);',
  );
  return evalInScope(
    ...Object.values(stateExports),
    addEvents,
    socket,
    navigate,
    params,
    token,
    code,
  );
};

/**
 * Build the update_vars_internal event for a synced localStorage var.
 *
 * The value is read when the event is sent, so it and the write count recorded
 * with it come from the same moment.
 * @param payload The storage name and the state keys of the vars that use it.
 * @returns The update_vars_internal event.
 */
const syncLocalStorageEvent = ({ key, state_keys }) => {
  const value = localStorage.getItem(key);
  return ReflexEvent(`${app.state_name}.${UPDATE_VARS_INTERNAL}`, {
    vars: Object.fromEntries(
      state_keys.map((state_key) => [
        state_key,
        value ?? storageDefault(state_key),
      ]),
    ),
  });
};

/**
 * Get the compiled default of a browser storage var.
 *
 * A removed storage key resets its vars to their defaults, as a page load does.
 * @param state_key The state key of the browser storage var.
 * @returns The default value.
 */
const storageDefault = (state_key) => {
  const dot = state_key.lastIndexOf(".");
  return app.initialState[state_key.slice(0, dot)][state_key.slice(dot + 1)];
};

/**
 * Handle frontend event or send the event to the backend via Websocket.
 * @param event The event to send.
 * @param socket The socket object to send the event on.
 * @param navigate The navigate function from useNavigate
 * @param params The params object from useParams
 */
export const applyEvent = async (event, socket, navigate, params) => {
  // Special case when linking to uploaded files
  if (
    event.name === "_download" &&
    typeof event.payload.url === "string" &&
    event.payload.url.includes("getBackendURL(env.UPLOAD)")
  ) {
    event = {
      ...event,
      payload: {
        ...event.payload,
        url: eval?.(
          event.payload.url.replace(
            "getBackendURL(env.UPLOAD)",
            `"${getBackendURL(env.UPLOAD)}"`,
          ),
        ),
      },
    };
  }

  if (isFrontendEvent(event)) {
    const storageChanged = await applyFrontendEvent(
      event,
      navigate,
      (code, addEvents) => runScript(code, addEvents, socket, navigate, params),
    );
    if (storageChanged) {
      // Hydrate again so the state's browser storage vars see the change.
      void queueEventIfSocketExists(
        app.initialEvents(),
        socket,
        navigate,
        params,
      );
    }
    return;
  }

  // Send the event to the server.
  if (socket) {
    const routed_event = withRouterData(
      event.name === SYNC_LOCAL_STORAGE
        ? syncLocalStorageEvent(event.payload)
        : event,
      params,
    );
    recordSentStorageValues(routed_event);
    // Instrumentation hook (installed by reflex-otel): may add a traceparent.
    window.__reflex_otel?.onEventSend?.(routed_event);
    socket.emit("event", encodeFormDataArgs(routed_event));
  }
};

/**
 * Fill in the event's router data from the current location, if missing.
 * @param event The event to send.
 * @param params The params object from useParams
 * @returns The same event, with router_data populated.
 */
const withRouterData = (event, params) => {
  if (
    event.router_data === undefined ||
    Object.keys(event.router_data).length === 0
  ) {
    const loc = locationRef.current ?? window.location;
    // React Router's location (mirrored in locationRef) does not observe direct
    // window.history.pushState/replaceState calls (e.g. via rx.call_script), so
    // read the live query string and hash to keep router_data in sync. The
    // pathname stays basename-relative (from React Router) so the backend's
    // frontend_path prefix is not applied twice. In embed mode the host page's
    // window.location is unrelated to the in-widget memory router, so use the
    // mirrored location there.
    const liveLoc = env.MOUNT_TARGET ? loc : window.location;
    const search = liveLoc.search ?? "";
    const hash = liveLoc.hash ?? "";
    event.router_data = {
      pathname: loc.pathname,
      asPath: loc.pathname + search + hash,
    };
    const query = {
      ...Object.fromEntries(new URLSearchParams(search)),
      ...params.current,
    };
    if (query && Object.keys(query).length > 0) {
      event.router_data.query = query;
    }
  }
  return event;
};

const currentRouteKey = () => {
  const loc = locationRef.current ?? window.location;
  const liveLoc = env.MOUNT_TARGET ? loc : window.location;
  return loc.pathname + (liveLoc.search ?? "");
};

/**
 * Send an event to the server via REST.
 * @param event The current event.
 * @param socket The socket object to send the response event(s) on.
 * @param navigate The navigate function from React Router
 * @param params The params object from React Router
 */
export const applyRestEvent = async (event, socket, navigate, params) => {
  if (event.handler === "uploadFiles") {
    // The compiled event names its extra bound handler args; collect just those
    // so they reach the backend handler (no need to know the reserved keys).
    const extra_args = {};
    for (const name of event.payload.__reflex_event_arg_names ?? []) {
      extra_args[name] = event.payload[name];
    }
    // The helper reserves its cancellation controller before waiting for cookies.
    // Do not await it here: ordinary WebSocket events must keep draining.
    void uploadFiles(
      event.name,
      event.payload.files,
      event.payload.upload_id,
      event.payload.on_upload_progress,
      event.payload.extra_headers,
      extra_args,
      socket,
      refs,
      getBackendURL,
      getToken,
      waitForSession,
      app.isDevMode,
    );
  }
};

/**
 * Resolve a socket reference to the actual socket object.
 * Handles both ref objects ({ current: Socket }) and raw sockets.
 * @param socket Either a ref object or raw socket.
 * @returns The actual socket object.
 */
const resolveSocket = (socket) => {
  return socket?.current ?? socket;
};

/**
 * Queue events to be processed and trigger processing of queue.
 * @param events Array of events to queue.
 * @param socket The socket object to send the event on.
 * @param prepend Whether to place the events at the beginning of the queue.
 * @param navigate The navigate function from React Router
 * @param params The params object from React Router
 */
export const queueEvents = async (
  events,
  socket,
  prepend,
  navigate,
  params,
) => {
  const normalized = normalizeEvents(events);
  if (prepend) {
    event_queue.unshift(...normalized);
  } else {
    event_queue.push(...normalized);
  }
  await processEvent(resolveSocket(socket), navigate, params);
};

/**
 * Process an event off the event queue.
 * @param socket The socket object to send the event on.
 * @param navigate The navigate function from React Router
 * @param params The params object from React Router
 */
export const processEvent = async (socket, navigate, params) => {
  // A connected socket can dispatch without inspecting the queued event types.
  if (!socket?.connected && isStateful()) {
    return;
  }

  // Only proceed if we're not already processing an event.
  if (event_queue.length === 0) {
    return;
  }

  // Apply the next event in the queue.
  const event = event_queue.shift();

  try {
    // Process events with handlers via REST and all others via websockets.
    if (event.handler) {
      await applyRestEvent(event, socket, navigate, params);
    } else {
      await applyEvent(event, socket, navigate, params);
    }
  } finally {
    // Continue draining queued events even if this dispatch fails.
    if (event_queue.length > 0) {
      await processEvent(socket, navigate, params);
    }
  }
};

/**
 * Reload the page for a new version of the app, restarting the reload cooldown.
 */
const reloadForNewVersion = () => {
  window.sessionStorage.setItem(LAST_RELOADED_KEY, Date.now().toString());
  window.location.reload();
};

/**
 * Show a banner saying a new version is available, with a reload button.
 *
 * Plain DOM rather than a React component: it must show whatever the app
 * renders, and stay up while the page keeps working as well as it can.
 */
const showNewVersionBanner = () => {
  if (document.getElementById(NEW_VERSION_BANNER_ID)) {
    return;
  }
  const banner = document.createElement("div");
  banner.id = NEW_VERSION_BANNER_ID;
  banner.setAttribute("role", "alert");
  banner.style.cssText =
    "position:fixed;top:0;left:0;right:0;z-index:2147483647;display:flex;" +
    "justify-content:center;align-items:center;gap:1rem;padding:0.5rem 1rem;" +
    "background:#1c2024;color:#fff;font:1rem system-ui,sans-serif;";
  banner.append("A new version of this app is available.");
  const button = document.createElement("button");
  button.textContent = "Reload";
  button.style.cssText =
    "padding:0.25rem 0.75rem;border:1px solid #fff;border-radius:4px;" +
    "background:transparent;color:inherit;font:inherit;cursor:pointer;";
  button.onclick = reloadForNewVersion;
  banner.append(button);
  document.body.append(banner);
};

/**
 * Handle the backend reporting that this bundle was compiled for another
 * state tree than the one it runs (sent on connect, see EventNamespace.on_connect).
 *
 * In prod the page reloads once per cooldown window. A mismatch inside the
 * window means the reload landed on the same skew (a cached bundle, or several
 * backend versions behind one load balancer), so a banner with a reload button
 * shows instead and the page never loops. The app can take over first: a
 * listener on the window's STATE_MISMATCH_WINDOW_EVENT that calls
 * preventDefault() skips both. In dev a backend hot reload can reconnect
 * before Vite serves the rebuilt bundle, so it only warns.
 * @param info The backend's state schema hash and the reload cooldown in ms.
 */
const handleStateMismatch = (info) => {
  const message =
    "This page was built for another version of the app than the backend it " +
    `connected to (state schema ${app.stateSchema}, backend ${info.backend}).`;
  if (app.isDevMode) {
    console.warn(
      message +
        " Reload the page if it stays out of date once the frontend rebuilds.",
    );
    return;
  }
  console.warn(message);
  const event = new CustomEvent(STATE_MISMATCH_WINDOW_EVENT, {
    cancelable: true,
    detail: { frontend: app.stateSchema, backend: info.backend },
  });
  if (!window.dispatchEvent(event)) {
    return;
  }
  const last_reload =
    parseInt(window.sessionStorage.getItem(LAST_RELOADED_KEY), 10) || 0;
  if (Date.now() - last_reload > info.reload_cooldown_ms) {
    reloadForNewVersion();
    return;
  }
  showNewVersionBanner();
};

/**
 * Connect to a websocket and set the handlers.
 * @param socket The socket object to connect.
 * @param dispatch The function to queue state update
 * @param transports The transports to use.
 * @param setConnectErrors The function to update connection error value.
 * @param client_storage The client storage object from context.js
 * @param navigate The navigate function from React Router
 * @param params The params object from React Router
 */
export const connect = async (
  socket,
  dispatch,
  transports,
  setConnectErrors,
  client_storage = {},
  navigate,
  params,
) => {
  // Socket already allocated, just reconnect it if needed.
  if (socket.current) {
    if (!socket.current.connected) {
      await socket.current.reconnect();
    }
    return;
  }

  // Get backend URL object from the endpoint.
  const endpoint = getBackendURL(EVENTURL);
  let bootRoute;

  // The hydrate event rides in the socket.io CONNECT packet, so the backend
  // starts loading state as soon as the namespace connects instead of after
  // an extra round trip for the connect acknowledgement. The keys are read by
  // the backend as CompileVars.CONNECT_AUTH_EVENT and CONNECT_AUTH_STATE_SCHEMA;
  // the state schema goes along on every (re)connect, since a reconnect can
  // land on another backend version.
  const bootAuth = (first) => (callback) => {
    const boot_event = withRouterData(app.initialEvents(first)[0], params);
    bootRoute = currentRouteKey();
    recordSentStorageValues(boot_event);
    // Instrumentation hook (installed by reflex-otel): may add a traceparent.
    window.__reflex_otel?.onEventSend?.(boot_event);
    callback({ event: boot_event, state_schema: app.stateSchema });
  };

  // Create the socket. A new session's token is saved here, once the app has
  // mounted, even when a transport warmed up with it earlier.
  socketStarted = true;
  const session_token = getToken();
  if (
    warmSocket &&
    (warmSocket.io.opts.query.token !== session_token ||
      warmSocket.io.opts.transports.length !== transports.length ||
      transports.some(
        (transport, i) => transport !== warmSocket.io.opts.transports[i],
      ))
  ) {
    discardWarmSocket();
  }
  socket.current =
    warmSocket ?? createSocket(endpoint, transports, session_token);
  warmSocket = null;
  cancelWarmup();
  socket.current.wait_connect = false;
  let firstConnect = true;
  let finishBootstrap;
  let reconnectingSession = false;
  let sessionTimer;
  // The abort controller of the exchange in progress, if any.
  let sessionController;
  let resolveSession;
  let rejectSession;
  let sessionFailures = 0;
  // Whether the backend denied the exchange for this page's origin.
  let sessionRejected = false;
  const currentSocket = socket.current;
  const requestSessionRefresh = () => {
    window.clearTimeout(sessionTimer);
    // A denied exchange gets the same answer until the backend reconnects.
    if (sessionRejected) return;
    if (socket.current === currentSocket && currentSocket.connected) {
      currentSocket.emit(SESSION_REFRESH_EVENT);
    }
  };
  // Ask for a new credential once the wait has passed. A browser runs a timer
  // over 2**31 - 1 ms with no delay, so the wait is capped.
  const scheduleSessionRefresh = (
    wait = Number(window.localStorage.getItem(sessionRefreshStorageKey())) -
      Date.now(),
  ) => {
    window.clearTimeout(sessionTimer);
    if (wait > 0) {
      sessionTimer = window.setTimeout(
        requestSessionRefresh,
        Math.min(wait, 2 ** 31 - 1),
      );
    } else {
      requestSessionRefresh();
    }
  };
  const finishSessionExchange = () => {
    resolveSession?.();
    resolveSession = rejectSession = undefined;
    initialSessionExchange = undefined;
  };
  const stopSessionExchange = (preserveReadiness = false) => {
    window.clearTimeout(sessionTimer);
    sessionController?.abort();
    sessionController = undefined;
    if (!preserveReadiness) {
      reconnectingSession = false;
      rejectSession?.(new Error("Session connection closed"));
      resolveSession = rejectSession = undefined;
      initialSessionExchange = undefined;
    }
  };
  const releaseBootstrap = () => {
    finishBootstrap?.();
    finishBootstrap = null;
  };
  socket.current.releaseSessionBootstrap = () => {
    stopSessionExchange();
    releaseBootstrap();
  };
  // Ensure undefined fields in events are sent as null instead of removed
  socket.current.io.encoder.replacer = (k, v) => (v === undefined ? null : v);
  // The server drops a transport whose frame exceeds the limit its handshake
  // announced, so a CONNECT packet (type 0) that carries an oversized hydrate
  // is reported instead of sent. The page stays offline until browser storage
  // shrinks and it reloads: wait_connect stays set, so reconnect() does not
  // rebuild the hydrate.
  const { encoder } = socket.current.io;
  const encode = encoder.encode.bind(encoder);
  encoder.encode = (packet) => {
    const encoded = encode(packet);
    if (packet.type !== 0) {
      return encoded;
    }
    // socket.io-client is pinned; test_hydration_storage.py covers these internals.
    const { engine } = socket.current.io;
    const transport = engine.transport.name;
    // The Engine.IO message type ("4") prefixes the encoded packet.
    const size = 1 + frameSize(encoded[0], transport);
    if (size > engine._maxPayload) {
      const unit = transport === "websocket" ? "characters" : "bytes";
      /** @type {Error & { code?: string }} */
      const error = new Error(
        `Hydration payload (${size} ${unit}) exceeds the server limit (${engine._maxPayload} ${unit}). Reduce browser storage data and reload.`,
      );
      error.code = ERROR_TYPE_HYDRATION_PAYLOAD_TOO_LARGE;
      console.error(error.message);
      setConnectErrors((errors) => [...errors.slice(-9), error]);
      // No connect or disconnect event follows, so free the cold-tab lock here.
      releaseBootstrap();
      socket.current.disconnect();
      return [];
    }
    return encoded;
  };
  socket.current.io.decoder.tryParse = (str) => {
    try {
      return parseJson(str);
    } catch {
      return false;
    }
  };
  // Set up a reconnect helper function
  socket.current.reconnect = async () => {
    if (
      socket.current &&
      !socket.current.connected &&
      !socket.current.wait_connect
    ) {
      socket.current.wait_connect = true;
      const current = socket.current;
      const start = () => {
        if (socket.current !== current) {
          releaseBootstrap();
          return;
        }
        current.io.opts.query = { token: getToken() };
        current.auth = bootAuth(firstConnect);
        current.connect();
      };
      const key = sessionStorageKey();
      if (
        window.navigator?.locks &&
        !(
          Number(window.localStorage.getItem(sessionRefreshStorageKey())) >
          Date.now()
        )
      ) {
        // Only cold tabs wait. The first socket hydrates while its in-band
        // credential becomes a cookie; the next tab then shares that cookie.
        window.navigator.locks
          .request(
            `${key}:session`,
            () =>
              new Promise((resolve) => {
                finishBootstrap = resolve;
                start();
              }),
          )
          .catch((error) => {
            if (socket.current === current) retryConnect(error);
          });
      } else {
        start();
      }
    }
  };

  function checkVisibility() {
    if (!socket.current) {
      // The socket was released without stopWatchingVisibility being called.
      // Connecting here would open a socket nothing listens to any more.
      document.removeEventListener("visibilitychange", checkVisibility);
      return;
    }
    if (document.visibilityState === "visible") {
      if (!socket.current.connected) {
        console.log("Socket is disconnected, attempting to reconnect ");
        socket.current.reconnect();
      } else if (!sessionController) {
        // A timer that the browser suspended can be past its refresh time.
        scheduleSessionRefresh();
      }
    }
  }

  const disconnectTrigger = (event) => {
    if (socket.current?.connected) {
      console.log("Disconnect websocket on page navigation");
      socket.current.disconnect();
    }
  };

  const pagehideHandler = (event) => {
    if (!socket.current?.connected) {
      return;
    }
    if (event.persisted) {
      console.log("Disconnect backend before bfcache on navigation");
    } else {
      console.log("Disconnect websocket on pagehide");
    }
    socket.current.disconnect();
  };

  // Unknown substates already reported on this connection.
  const reported_missing_substates = new Set();
  // Failed connection attempts since the last connect, for the retry backoff.
  let failed_attempts = 0;
  // The scheduled retry of the last failed attempt.
  let retry_timer;

  // Once the socket is open, hydrate the page.
  socket.current.on("connect", async () => {
    if (reconnectingSession) {
      reconnectingSession = false;
      if (!sessionController) finishSessionExchange();
    }
    if (!sessionController) {
      releaseBootstrap();
      // The backend can trust this origin after a restart with new settings.
      sessionRejected = false;
      scheduleSessionRefresh();
    }
    firstConnect = false;
    socket.current.wait_connect = false;
    reported_missing_substates.clear();
    failed_attempts = 0;
    window.clearTimeout(retry_timer);
    retry_timer = undefined;
    setConnectErrors([]);
    window.__reflex_otel?.onSocketConnect?.();
    window.addEventListener("pagehide", pagehideHandler);
    window.addEventListener("beforeunload", disconnectTrigger);
    // The connection auth event already loads its route, and every queued
    // on_load loads the route current when it is sent. Keep the last queued
    // on_load, after every navigation's storage update, only if the route
    // changed after the auth event was built.
    let keepOnLoad = bootRoute !== currentRouteKey();
    for (let i = event_queue.length - 1; i >= 0; i--) {
      if (event_queue[i].name !== app.on_load_internal_event) continue;
      if (keepOnLoad) {
        keepOnLoad = false;
      } else {
        event_queue.splice(i, 1);
      }
    }
    // Drain any initial events from the queue. One call is the whole drain:
    // processEvent goes on until the queue is empty, or until the socket has
    // dropped again with a stateful event waiting. Looping on the queue length
    // would spin in that second case, since nothing can shrink the queue then.
    await processEvent(socket.current, navigate, params);
  });

  // Record a failed connection attempt and retry it with incremental backoff.
  const retryConnect = (error) => {
    releaseBootstrap();
    socket.current.wait_connect = false;
    failed_attempts = Math.min(failed_attempts + 1, 10);
    setConnectErrors((connectErrors) => [...connectErrors.slice(-9), error]);
    window.clearTimeout(retry_timer);
    retry_timer = window.setTimeout(() => {
      retry_timer = undefined;
      if (socket.current && !socket.current.connected) {
        return socket.current.reconnect();
      }
    }, 200 * failed_attempts); // Incremental backoff
  };

  socket.current.on("connect_error", retryConnect);

  socket.current.on("disconnect", (reason, details) => {
    stopSessionExchange(
      reconnectingSession && reason === "io client disconnect",
    );
    releaseBootstrap();
    firstConnect = false;
    // A transport closed before the namespace connected is a failed attempt,
    // e.g. a CONNECT packet over the server or a proxy message size limit.
    if (socket.current.wait_connect) {
      retryConnect(
        new Error(`connection closed before connecting (${reason})`),
      );
      return;
    }
    // A transport error reports connect_error first, which scheduled the retry.
    if (retry_timer !== undefined) {
      return;
    }
    window.__reflex_otel?.onSocketDisconnect?.(reason);
    const try_reconnect =
      reason !== "io server disconnect" && reason !== "io client disconnect";
    window.removeEventListener("beforeunload", disconnectTrigger);
    window.removeEventListener("pagehide", pagehideHandler);
    if (try_reconnect) {
      // Attempt to reconnect transient non-intentional disconnects.
      socket.current.reconnect();
    }
  });

  // Report a failure to process a state update to the backend, so it surfaces
  // in the terminal logs instead of only in the browser console.
  const reportStateUpdateError = (error) => {
    console.error("Error processing state update:", error);
    socket.current?.emit(CLIENT_ERROR_EVENT, {
      message: error?.message || String(error),
      error_type: ERROR_TYPE_STATE_UPDATE,
    });
  };

  // Warn about unknown substates and surface them in the backend terminal
  // logs, once per substate per connection.
  const reportUnknownSubstates = (substates) => {
    const unreported = substates.filter(
      (substate) => !reported_missing_substates.has(substate),
    );
    if (unreported.length === 0) {
      return;
    }
    for (const substate of unreported) {
      reported_missing_substates.add(substate);
    }
    const errorMsg = `Skipping state update for unknown substate(s): no dispatch function for "${unreported.join(
      '", "',
    )}". Try refreshing the page or clearing your browser cache. This usually indicates a mismatch between frontend and backend state definitions. If you are the developer of this app, rebuild the frontend and check that api_url is correct.`;
    console.warn(errorMsg);
    socket.current.emit(CLIENT_ERROR_EVENT, {
      message: errorMsg,
      substate: unreported.join(", "),
      error_type: ERROR_TYPE_DISPATCH_MISSING,
    });
  };

  // Drop and report substates without a dispatch function. Only a mismatched
  // delta is copied; the received update is not mutated.
  const withoutUnknownSubstates = (delta) => {
    let unknown;
    for (const substate in delta) {
      if (typeof dispatch[substate] !== "function") {
        unknown ??= [];
        unknown.push(substate);
      }
    }
    if (unknown === undefined) {
      return delta;
    }
    reportUnknownSubstates(unknown);
    const known = { ...delta };
    for (const substate of unknown) {
      delete known[substate];
    }
    return known;
  };

  // On each received message, queue the updates and events.
  socket.current.on("event", (update) => {
    // Skip unknown substates in both reducer and client-storage updates.
    const delta = withoutUnknownSubstates(update.delta);
    try {
      if (delta) {
        for (const substate in delta) {
          dispatch[substate](delta[substate]);
        }
        applyClientStorageDelta(client_storage, delta);
      }
      if (update.events && update.events.length > 0) {
        queueEvents(update.events, socket, false, navigate, params).catch(
          reportStateUpdateError,
        );
      }
    } catch (error) {
      reportStateUpdateError(error);
    }
  });
  socket.current.on("new_token", async (new_token) => {
    setToken(new_token);
  });
  socket.current.on(SESSION_REFRESH_EVENT, requestSessionRefresh);
  socket.current.on("session_token", async (sessionCredential) => {
    if (sessionController) return;
    const controller = new AbortController();
    sessionController = controller;
    window.clearTimeout(sessionTimer);
    // HTTP calls wait while a credential from the socket is exchanged for
    // the cookie. After a lasting failure the retries go on, but they hold
    // nothing.
    if (!resolveSession && sessionCredential && sessionFailures < 3) {
      initialSessionExchange = new Promise((resolve, reject) => {
        resolveSession = resolve;
        rejectSession = reject;
      });
      // Readiness may have no HTTP consumer when the connection closes.
      initialSessionExchange.catch(() => {});
    }
    try {
      const previousToken = getToken();
      const session = await ensureSession(sessionCredential, controller);
      if (sessionController !== controller) return;
      setToken(session.client_token);
      const refreshDelay =
        (session.refresh_in ?? session.expires_in / 2) * 1000;
      sessionRejected = false;
      try {
        window.localStorage.setItem(
          sessionRefreshStorageKey(),
          String(Date.now() + refreshDelay),
        );
      } catch {
        // The cookie is set; the refresh time is only a hint for later loads.
      }
      sessionFailures = 0;
      setConnectErrors([]);
      scheduleSessionRefresh(refreshDelay);
      if (currentSocket.connected && getToken() !== previousToken) {
        // Keep waiting HTTP calls queued until this cookie's socket is accepted.
        reconnectingSession = true;
        currentSocket.disconnect();
        await currentSocket.reconnect();
      } else {
        finishSessionExchange();
      }
    } catch (error) {
      if (sessionController !== controller) return;
      window.localStorage.removeItem(sessionRefreshStorageKey());
      if (error.status === 403) {
        // The backend does not trust this page's origin, so a retry gets the
        // same answer. The socket works without the cookie: release HTTP calls.
        console.error(
          `${error.message}. The backend does not trust the origin ${window.location.origin}; ` +
            "add it to deploy_url or cors_allowed_origins to persist the browser session.",
        );
        sessionRejected = true;
        finishSessionExchange();
        return;
      }
      setConnectErrors((errors) => [...errors.slice(-9), error]);
      // Retry on the live socket after one second, backing off to thirty seconds.
      // Each attempt requests a fresh credential, including after cookie expiry.
      const delay = Math.min(30000, 1000 * 2 ** Math.min(sessionFailures++, 5));
      sessionTimer = window.setTimeout(requestSessionRefresh, delay);
      // A failure that lasts is not transient, for example a proxy that does
      // not forward this route. Stop holding HTTP calls; the retry goes on.
      if (sessionFailures >= 3) finishSessionExchange();
    } finally {
      if (sessionController === controller) {
        sessionController = undefined;
        releaseBootstrap();
      }
    }
  });

  socket.current.on(STATE_MISMATCH_EVENT, handleStateMismatch);

  document.addEventListener("visibilitychange", checkVisibility);
  // Called by whoever releases the socket: the listener lives on the document,
  // so it would otherwise outlive the socket and everything it closes over.
  socket.current.stopWatchingVisibility = () =>
    document.removeEventListener("visibilitychange", checkVisibility);
  await socket.current.reconnect();
};

/**
 * Package client-side storage values as payload to send to the
 * backend with the hydrate event
 * @param client_storage The client storage object from context.js
 * @returns payload dict of client storage values
 */
export const hydrateClientStorage = (client_storage) => {
  const client_storage_values = {};
  if (client_storage.cookies) {
    for (const state_key in client_storage.cookies) {
      const cookie_options = client_storage.cookies[state_key];
      const cookie_name = cookie_options.name || state_key;
      const cookie_value = getCookies().get(cookie_name, { doNotParse: true });
      if (cookie_value !== undefined) {
        client_storage_values[state_key] = cookie_value;
      }
    }
  }
  if (client_storage.local_storage && typeof window !== "undefined") {
    for (const state_key in client_storage.local_storage) {
      const options = client_storage.local_storage[state_key];
      const local_storage_value = localStorage.getItem(
        options.name || state_key,
      );
      if (local_storage_value !== null) {
        client_storage_values[state_key] = local_storage_value;
      }
    }
  }
  if (client_storage.session_storage && typeof window !== "undefined") {
    for (const state_key in client_storage.session_storage) {
      const session_options = client_storage.session_storage[state_key];
      const session_storage_value = sessionStorage.getItem(
        session_options.name || state_key,
      );
      if (session_storage_value != null) {
        client_storage_values[state_key] = session_storage_value;
      }
    }
  }
  if (
    client_storage.cookies ||
    client_storage.local_storage ||
    client_storage.session_storage
  ) {
    return client_storage_values;
  }
  return {};
};

/**
 * Remember the synced localStorage values an event sends, to recognise their echoes.
 *
 * Only synced vars: the tab sends another tab's newer value only for those.
 * @param event The event about to be sent.
 */
const recordSentStorageValues = (event) => {
  // ReflexEvent leaves out an empty payload.
  const vars = event.payload?.vars;
  if (
    vars === undefined ||
    (event.name !== `${app.state_name}.hydrate_and_load` &&
      event.name !== `${app.state_name}.${UPDATE_VARS_INTERNAL}`)
  ) {
    return;
  }
  const local_storage = app.clientStorage.local_storage;
  for (const [state_key, value] of Object.entries(vars)) {
    if (!local_storage?.[state_key]?.sync) {
      continue;
    }
    const sent = (sentStorageValues[state_key] ??= []);
    sent.push({ value, writes: localStorageWrites });
    if (sent.length > MAX_SENT_STORAGE_VALUES) {
      sent.shift();
    }
  }
};

/**
 * Take the sent value that a backend value echoes, and the older ones with it.
 * @param state_key The state key of the browser storage var.
 * @param value The value the backend sent for it.
 * @returns The sent value's entry, or undefined if the value is no echo.
 */
const takeEcho = (state_key, value) => {
  const sent = sentStorageValues[state_key];
  const index = sent?.findIndex((entry) => entry.value === value) ?? -1;
  // Older values were echoed already, or changed by an override on the way.
  return index === -1 ? undefined : sent.splice(0, index + 1)[index];
};

/**
 * Update client storage values based on backend state delta.
 * @param client_storage The client storage object from context.js
 * @param delta The state update from the backend
 */
const applyClientStorageDelta = (client_storage, delta) => {
  // find the main state and check for is_hydrated
  const unqualified_states = Object.keys(delta).filter(
    (key) => key.split(".").length === 1,
  );
  if (unqualified_states.length === 1) {
    const main_state = delta[unqualified_states[0]];
    if (
      main_state.is_hydrated_rx_state_ !== undefined &&
      !main_state.is_hydrated_rx_state_
    ) {
      // skip if the state is not hydrated yet, since all client storage
      // values are sent in the hydrate event
      return;
    }
  }
  // Save known client storage values to cookies and localStorage.
  for (const substate in delta) {
    for (const key in delta[substate]) {
      const state_key = `${substate}.${key}`;
      const value = delta[substate][key];
      if (client_storage.cookies && state_key in client_storage.cookies) {
        const cookie_options = { ...client_storage.cookies[state_key] };
        const cookie_name = cookie_options.name || state_key;
        delete cookie_options.name; // name is not a valid cookie option
        getCookies().set(cookie_name, value, cookie_options);
      } else if (
        client_storage.local_storage &&
        state_key in client_storage.local_storage &&
        typeof window !== "undefined"
      ) {
        const name = client_storage.local_storage[state_key].name || state_key;
        const echo = takeEcho(state_key, value);
        const last = lastLocalStorageWrites[name];
        // Write an echo only over this tab's own later write, which the backend
        // applied before the echoed event. Otherwise storage holds the sent
        // value or another tab's newer one.
        if (
          !echo ||
          (last?.writes > echo.writes &&
            localStorage.getItem(name) === last.value)
        ) {
          localStorage.setItem(name, value);
          lastLocalStorageWrites[name] = {
            value,
            writes: ++localStorageWrites,
          };
        }
      } else if (
        client_storage.session_storage &&
        state_key in client_storage.session_storage &&
        typeof window !== "undefined"
      ) {
        const session_options = client_storage.session_storage[state_key];
        sessionStorage.setItem(session_options.name || state_key, value);
      }
    }
  }
};

/**
 * Establish websocket event loop for a React Router page.
 * @param dispatch The reducer dispatch function to update state.
 * @param initial_events The initial app events.
 * @param client_storage The client storage object from context.js
 *
 * @returns [addEvents, connectErrors] -
 *   addEvents is used to queue an event, and
 *   connectErrors is an array of reactive js error from the websocket connection (or null if connected).
 */
export const useEventLoop = (
  dispatch,
  initial_events = () => [],
  client_storage = {},
) => {
  const socket = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const paramsR = useParams();
  const prevLocationRef = useRef(location);
  const [searchParams] = useSearchParams();
  const [connectErrors, setConnectErrors] = useState([]);
  // A splat route's segments are kept as a list, so the values are not all strings.
  const params = useRef(
    /** @type {Record<string, string | string[] | undefined>} */ (paramsR),
  );
  const mounted = useRef(false);

  useEffect(() => {
    const { "*": splat, ...remainingParams } = paramsR;
    if (splat) {
      params.current = { ...remainingParams, splat: splat.split("/") };
    } else {
      params.current = remainingParams;
    }
  }, [paramsR]);

  useEffect(() => {
    locationRef.current = location;
  }, [location]);

  const ensureSocketConnected = useCallback(async () => {
    if (!mounted.current) {
      // During hot reload, some components may still have a reference to
      // addEvents, so avoid reconnecting the socket of an unmounted event loop.
      return;
    }
    try {
      // only use websockets if state is present and backend is not disabled (reflex cloud).
      if (
        Object.keys(app.initialState).length > 1 &&
        !isBackendDisabled() &&
        !socket.current?.connected
      ) {
        // Initialize the websocket connection.
        await connect(
          socket,
          dispatch,
          [env.TRANSPORT],
          setConnectErrors,
          client_storage,
          navigate,
          params,
        );
      }
    } catch (error) {
      // A connection that cannot even be attempted (the browser blocks the
      // storage that holds the token, say) is a connection error like any
      // other. It must not reject: callers do not await this, and the handler
      // for unhandled rejections reports through addEvents, which calls back
      // into here and would fail the same way, forever.
      setConnectErrors((errors) => [...errors.slice(-9), error]);
    }
  }, [
    socket,
    dispatch,
    setConnectErrors,
    client_storage,
    navigate,
    params,
    mounted,
  ]);

  // Function to add new events to the event queue.
  const addEvents = useCallback((events, args, event_actions) => {
    const _events = normalizeEvents(events);

    event_actions = Object.assign(
      {},
      event_actions,
      ..._events.map((e) => e.event_actions),
    );

    if (!event_actions?.temporal) {
      // Reconnect socket if needed for non-temporal events.
      void ensureSocketConnected();
    }

    return applyEventActions(
      () => queueEvents(_events, socket, false, navigate, params),
      event_actions,
      args,
      _events.map((e) => e.name).join("+++"),
      () => !!socket.current?.connected,
    );
  }, []);

  // Handle frontend errors and send them to the backend via websocket.
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.onerror = function (msg, url, lineNo, columnNo, error) {
      addEvents([
        ReflexEvent(`${app.exception_state_name}.handle_frontend_exception`, {
          // Some error events (e.g. a ResizeObserver loop) have no Error object.
          info: error
            ? error.name + ": " + error.message + "\n" + error.stack
            : msg + "\n    at " + url + ":" + lineNo + ":" + columnNo,
          component_stack: "",
        }),
      ]);
      return false;
    };

    //NOTE: Only works in Chrome v49+
    //https://github.com/mknichel/javascript-errors?tab=readme-ov-file#promise-rejection-events
    window.onunhandledrejection = function (event) {
      addEvents([
        ReflexEvent(`${app.exception_state_name}.handle_frontend_exception`, {
          info:
            event.reason?.name +
            ": " +
            event.reason?.message +
            "\n" +
            event.reason?.stack,
          component_stack: "",
        }),
      ]);
      return false;
    };
  }, []);

  // Handle socket connect/disconnect.
  useEffect(() => {
    // Initialize the websocket connection.
    mounted.current = true;
    void ensureSocketConnected();

    // Cleanup function.
    return () => {
      mounted.current = false;
      if (socket.current) {
        socket.current.releaseSessionBootstrap?.();
        socket.current.disconnect();
        socket.current.off();
        socket.current.stopWatchingVisibility();
        socket.current = null;
      }
    };
  }, []);

  // Main event loop.
  useEffect(() => {
    // Skip if the backend is disabled
    if (isBackendDisabled() || !socket.current || !socket.current.connected) {
      return;
    }
    void (async () => {
      // Process all outstanding events. processEvent drains the queue itself,
      // and stops at a stateful event when the socket has dropped; the connect
      // handler sends what is left once it is back.
      if (event_queue.length > 0) {
        await ensureSocketConnected();
        await processEvent(socket.current, navigate, params);
      }
    })();
  });

  // localStorage event handling
  useEffect(() => {
    // A Map, so a storage name like "constructor" is not an inherited property.
    const storage_to_state_map = new Map();

    if (client_storage.local_storage && typeof window !== "undefined") {
      for (const state_key in client_storage.local_storage) {
        const options = client_storage.local_storage[state_key];
        if (options.sync) {
          const local_storage_value_key = options.name || state_key;
          // Several vars can share one storage name; sync all of them.
          const state_keys = storage_to_state_map.get(local_storage_value_key);
          if (state_keys) {
            state_keys.push(state_key);
          } else {
            storage_to_state_map.set(local_storage_value_key, [state_key]);
          }
        }
      }
    }

    // e is StorageEvent
    const handleStorage = (e) => {
      // Session storage changes in same-origin frames raise storage events too.
      if (e.storageArea !== localStorage) {
        return;
      }
      // A clear() event has no key and affects every synced storage name.
      const entries =
        e.key === null
          ? storage_to_state_map.entries()
          : [[e.key, storage_to_state_map.get(e.key)]];
      const events = [];
      for (const [key, state_keys] of entries) {
        if (state_keys) {
          // Read the value when sent, just like individual-key updates.
          events.push(ReflexEvent(SYNC_LOCAL_STORAGE, { key, state_keys }));
        }
      }
      if (events.length) {
        addEvents(events, e);
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  });

  const handleNavigationEvents = useRef(false);
  // Route after the initial page hydration
  useEffect(() => {
    // The first time this effect runs is initial load, so don't handle
    // any navigation events.
    if (!handleNavigationEvents.current) {
      handleNavigationEvents.current = true;
      return;
    }
    if (location.state?.fromNotFound) {
      // If the redirect is from a 404 page, we skip onLoadInternalEvent,
      // since it was already run when the 404 page was first rendered.
      return;
    }
    // This will run when the location changes
    if (
      location.pathname + location.search ===
      prevLocationRef.current.pathname + prevLocationRef.current.search
    ) {
      if (location.hash) {
        // If the hash is the same, we don't need to do anything.
        return;
      }
    }

    // Equivalent to routeChangeStart - runs when navigation begins
    const main_state_dispatch = dispatch["reflex___state____state"];
    if (main_state_dispatch !== undefined) {
      main_state_dispatch({ is_hydrated_rx_state_: false });
    }

    // Equivalent to routeChangeComplete - runs after navigation completes
    addEvents(app.onLoadInternalEvent());

    // Update the ref
    prevLocationRef.current = location;
  }, [location, dispatch, addEvents]);

  return [addEvents, connectErrors];
};
