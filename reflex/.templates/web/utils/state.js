// State management for Reflex web apps.
import io from "socket.io-client";
import JSON5 from "json5";
import env from "$/env.json";
import reflexEnvironment from "$/reflex.json";
import Cookies from "universal-cookie";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  useLocation,
  useNavigate,
  useSearchParams,
  useParams,
} from "react-router";
import {
  initialEvents,
  initialState,
  onLoadInternalEvent,
  state_name,
  exception_state_name,
} from "$/utils/context";
import debounce from "$/utils/helpers/debounce";
import throttle from "$/utils/helpers/throttle";
import { uploadFiles } from "$/utils/helpers/upload";

// Endpoint URLs.
const EVENTURL = env.EVENT;

// These hostnames indicate that the backend and frontend are reachable via the same domain.
const SAME_DOMAIN_HOSTNAMES = ["localhost", "0.0.0.0", "::", "0:0:0:0:0:0:0:0"];

// Global variable to hold the token.
let token;

// Key for the token in the session storage.
const TOKEN_KEY = "token";

// create cookie instance
const cookies = new Cookies();

// Dictionary holding component references.
export const refs = {};

// Flag ensures that only one event is processing on the backend concurrently.
let event_processing = false;
// Array holding pending events to be processed.
const event_queue = [];

/**
 * Generate a UUID (Used for session tokens).
 * Taken from: https://stackoverflow.com/questions/105034/how-do-i-create-a-guid-uuid
 * @returns A UUID.
 */
export const generateUUID = () => {
  let d = new Date().getTime(),
    d2 = (performance && performance.now && performance.now() * 1000) || 0;
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    let r = Math.random() * 16;
    if (d > 0) {
      r = (d + r) % 16 | 0;
      d = Math.floor(d / 16);
    } else {
      r = (d2 + r) % 16 | 0;
      d2 = Math.floor(d2 / 16);
    }
    return (c == "x" ? r : (r & 0x7) | 0x8).toString(16);
  });
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
    if (!window.sessionStorage.getItem(TOKEN_KEY)) {
      window.sessionStorage.setItem(TOKEN_KEY, generateUUID());
    }
    token = window.sessionStorage.getItem(TOKEN_KEY);
  }
  return token;
};

/**
 * Get the URL for the backend server
 * @param url_str The URL string to parse.
 * @returns The given URL modified to point to the actual backend server.
 */
export const getBackendURL = (url_str) => {
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

/**
 * Check if the backend is disabled.
 *
 * @returns True if the backend is disabled, false otherwise.
 */
export const isBackendDisabled = () => {
  const cookie = document.cookie
    .split("; ")
    .find((row) => row.startsWith("backend-enabled="));
  return cookie !== undefined && cookie.split("=")[1] == "false";
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
  return event_queue.some((event) => event.name.startsWith("reflex___state"));
};

/**
 * Apply a delta to the state.
 * @param state The state to apply the delta to.
 * @param delta The delta to apply.
 */
export const applyDelta = (state, delta) => {
  return { ...state, ...delta };
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
  const encodedJs = encodeURIComponent(component);
  const dataUri = "data:text/javascript;charset=utf-8," + encodedJs;
  const module = await eval(`import(dataUri)`);
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
  await queueEvents(events, socket, navigate, params);
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
  return undefined;
}

/**
 * Handle frontend event or send the event to the backend via Websocket.
 * @param event The event to send.
 * @param socket The socket object to send the event on.
 * @param navigate The navigate function from useNavigate
 * @param params The params object from useParams
 *
 * @returns True if the event was sent, false if it was handled locally.
 */
export const applyEvent = async (event, socket, navigate, params) => {
  // Handle special events
  if (event.name == "_redirect") {
    if ((event.payload.path ?? undefined) === undefined) {
      return false;
    }
    if (event.payload.external) {
      window.open(
        event.payload.path,
        "_blank",
        "noopener" + (event.payload.popup ? ",popup" : ""),
      );
      return false;
    }
    const url = urlFrom(event.payload.path);
    let pathname = event.payload.path;
    if (url) {
      if (url.host !== window.location.host) {
        // External URL
        window.location.assign(event.payload.path);
        return false;
      } else {
        pathname = url.pathname + url.search + url.hash;
      }
    }
    if (event.payload.replace) {
      navigate(pathname, { replace: true });
    } else {
      navigate(pathname);
    }
    return false;
  }

  if (event.name == "_remove_cookie") {
    cookies.remove(event.payload.key, { ...event.payload.options });
    queueEventIfSocketExists(initialEvents(), socket, navigate, params);
    return false;
  }

  if (event.name == "_clear_local_storage") {
    localStorage.clear();
    queueEventIfSocketExists(initialEvents(), socket, navigate, params);
    return false;
  }

  if (event.name == "_remove_local_storage") {
    localStorage.removeItem(event.payload.key);
    queueEventIfSocketExists(initialEvents(), socket, navigate, params);
    return false;
  }

  if (event.name == "_clear_session_storage") {
    sessionStorage.clear();
    queueEvents(initialEvents(), socket, navigate, params);
    return false;
  }

  if (event.name == "_remove_session_storage") {
    sessionStorage.removeItem(event.payload.key);
    queueEvents(initialEvents(), socket, navigate, params);
    return false;
  }

  if (event.name == "_download") {
    const a = document.createElement("a");
    a.hidden = true;
    a.href = event.payload.url;
    // Special case when linking to uploaded files
    if (a.href.includes("getBackendURL(env.UPLOAD)")) {
      a.href = eval?.(
        event.payload.url.replace(
          "getBackendURL(env.UPLOAD)",
          `"${getBackendURL(env.UPLOAD)}"`,
        ),
      );
    }
    a.download = event.payload.filename;
    a.click();
    a.remove();
    return false;
  }

  if (event.name == "_set_focus") {
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
    return false;
  }

  if (event.name == "_blur_focus") {
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
    return false;
  }

  if (event.name == "_set_value") {
    const ref =
      event.payload.ref in refs ? refs[event.payload.ref] : event.payload.ref;
    if (ref.current) {
      ref.current.value = event.payload.value;
    }
    return false;
  }

  if (
    event.name == "_call_function" &&
    typeof event.payload.function !== "string"
  ) {
    try {
      const eval_result = event.payload.function();
      if (event.payload.callback) {
        const final_result =
          !!eval_result && typeof eval_result.then === "function"
            ? await eval_result
            : eval_result;
        const callback =
          typeof event.payload.callback === "string"
            ? eval(event.payload.callback)
            : event.payload.callback;
        callback(final_result);
      }
    } catch (e) {
      console.log("_call_function", e);
      if (window && window?.onerror) {
        window.onerror(e.message, null, null, null, e);
      }
    }
    return false;
  }

  if (event.name == "_call_script" || event.name == "_call_function") {
    try {
      const eval_result =
        event.name == "_call_script"
          ? eval(event.payload.javascript_code)
          : eval(event.payload.function)();

      if (event.payload.callback) {
        const final_result =
          !!eval_result && typeof eval_result.then === "function"
            ? await eval_result
            : eval_result;
        const callback =
          typeof event.payload.callback === "string"
            ? eval(event.payload.callback)
            : event.payload.callback;
        callback(final_result);
      }
    } catch (e) {
      console.log("_call_script", e);
      if (window && window?.onerror) {
        window.onerror(e.message, null, null, null, e);
      }
    }
    return false;
  }

  // Update token and router data (if missing).
  event.token = getToken();
  if (
    event.router_data === undefined ||
    Object.keys(event.router_data).length === 0
  ) {
    // Since we don't have router directly, we need to get info from our hooks
    event.router_data = {
      pathname: window.location.pathname,
      query: {
        ...Object.fromEntries(new URLSearchParams(window.location.search)),
        ...params(),
      },
      asPath:
        window.location.pathname +
        window.location.search +
        window.location.hash,
    };
  }

  // Send the event to the server.
  if (socket) {
    socket.emit("event", event);
    return true;
  }

  return false;
};

/**
 * Send an event to the server via REST.
 * @param event The current event.
 * @param socket The socket object to send the response event(s) on.
 * @param navigate The navigate function from React Router
 * @param params The params object from React Router
 *
 * @returns Whether the event was sent.
 */
export const applyRestEvent = async (event, socket, navigate, params) => {
  let eventSent = false;
  if (event.handler === "uploadFiles") {
    if (event.payload.files === undefined || event.payload.files.length === 0) {
      // Submit the event over the websocket to trigger the event handler.
      return await applyEvent(
        ReflexEvent(event.name, { files: [] }),
        socket,
        navigate,
        params,
      );
    }

    // Start upload, but do not wait for it, which would block other events.
    uploadFiles(
      event.name,
      event.payload.files,
      event.payload.upload_id,
      event.payload.on_upload_progress,
      event.payload.extra_headers,
      socket,
      refs,
      getBackendURL,
      getToken,
    );
    return false;
  }
  return eventSent;
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
  if (prepend) {
    // Drain the existing queue and place it after the given events.
    events = [
      ...events,
      ...Array.from({ length: event_queue.length }).map(() =>
        event_queue.shift(),
      ),
    ];
  }
  event_queue.push(...events.filter((e) => e !== undefined && e !== null));
  await processEvent(socket.current, navigate, params);
};

/**
 * Process an event off the event queue.
 * @param socket The socket object to send the event on.
 * @param navigate The navigate function from React Router
 * @param params The params object from React Router
 */
export const processEvent = async (socket, navigate, params) => {
  // Only proceed if the socket is up or no event in the queue uses state, otherwise we throw the event into the void
  if (isStateful() && !(socket && socket.connected)) {
    return;
  }

  // Only proceed if we're not already processing an event.
  if (event_queue.length === 0 || event_processing) {
    return;
  }

  // Set processing to true to block other events from being processed.
  event_processing = true;

  // Apply the next event in the queue.
  const event = event_queue.shift();

  let eventSent = false;
  // Process events with handlers via REST and all others via websockets.
  if (event.handler) {
    eventSent = await applyRestEvent(event, socket, navigate, params);
  } else {
    eventSent = await applyEvent(event, socket, navigate, params);
  }
  // If no event was sent, set processing to false.
  if (!eventSent) {
    event_processing = false;
    // recursively call processEvent to drain the queue, since there is
    // no state update to trigger the useEffect event loop.
    await processEvent(socket, navigate, params);
  }
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
      socket.current.reconnect();
    }
    return;
  }

  // Get backend URL object from the endpoint.
  const endpoint = getBackendURL(EVENTURL);
  const on_hydrated_queue = [];

  // Create the socket.
  socket.current = io(endpoint.href, {
    path: endpoint["pathname"],
    transports: transports,
    protocols: [reflexEnvironment.version],
    autoUnref: false,
    query: { token: getToken() },
    reconnection: false, // Reconnection will be handled manually.
  });
  socket.current.wait_connect = !socket.current.connected;
  // Ensure undefined fields in events are sent as null instead of removed
  socket.current.io.encoder.replacer = (k, v) => (v === undefined ? null : v);
  socket.current.io.decoder.tryParse = (str) => {
    try {
      return JSON5.parse(str);
    } catch (e) {
      return false;
    }
  };
  // Set up a reconnect helper function
  socket.current.reconnect = () => {
    if (
      socket.current &&
      !socket.current.connected &&
      !socket.current.wait_connect
    ) {
      socket.current.wait_connect = true;
      socket.current.io.opts.query = { token: getToken() }; // Update token for reconnect.
      socket.current.connect();
    }
  };

  function checkVisibility() {
    if (document.visibilityState === "visible") {
      if (!socket.current) {
        connect(
          socket,
          dispatch,
          transports,
          setConnectErrors,
          client_storage,
          navigate,
          params,
        );
      } else if (!socket.current.connected) {
        console.log("Socket is disconnected, attempting to reconnect ");
        socket.current.reconnect();
      } else {
        console.log("Socket is reconnected ");
      }
    }
  }

  const disconnectTrigger = (event) => {
    if (socket.current?.connected) {
      console.log("Disconnect websocket on unload");
      socket.current.disconnect();
    }
  };

  const pagehideHandler = (event) => {
    if (event.persisted && socket.current?.connected) {
      console.log("Disconnect backend before bfcache on navigation");
      socket.current.disconnect();
    }
  };

  // Once the socket is open, hydrate the page.
  socket.current.on("connect", async () => {
    socket.current.wait_connect = false;
    setConnectErrors([]);
    window.addEventListener("pagehide", pagehideHandler);
    window.addEventListener("beforeunload", disconnectTrigger);
    window.addEventListener("unload", disconnectTrigger);
    // Drain any initial events from the queue.
    while (event_queue.length > 0 && !event_processing) {
      await processEvent(socket.current, navigate, () => params.current);
    }
  });

  socket.current.on("connect_error", (error) => {
    socket.current.wait_connect = false;
    let n_connect_errors = 0;
    setConnectErrors((connectErrors) => {
      const new_errors = [...connectErrors.slice(-9), error];
      n_connect_errors = new_errors.length;
      return new_errors;
    });
    window.setTimeout(() => {
      if (socket.current && !socket.current.connected) {
        socket.current.reconnect();
      }
    }, 200 * n_connect_errors); // Incremental backoff
  });

  // When the socket disconnects reset the event_processing flag
  socket.current.on("disconnect", (reason, details) => {
    socket.current.wait_connect = false;
    const try_reconnect =
      reason !== "io server disconnect" && reason !== "io client disconnect";
    event_processing = false;
    window.removeEventListener("unload", disconnectTrigger);
    window.removeEventListener("beforeunload", disconnectTrigger);
    window.removeEventListener("pagehide", pagehideHandler);
    if (try_reconnect) {
      // Attempt to reconnect transient non-intentional disconnects.
      socket.current.reconnect();
    }
  });

  // On each received message, queue the updates and events.
  socket.current.on("event", async (update) => {
    for (const substate in update.delta) {
      dispatch[substate](update.delta[substate]);
      // handle events waiting for `is_hydrated`
      if (
        substate === state_name &&
        update.delta[substate]?.is_hydrated_rx_state_
      ) {
        queueEvents(on_hydrated_queue, socket, false, navigate, params);
        on_hydrated_queue.length = 0;
      }
    }
    applyClientStorageDelta(client_storage, update.delta);
    event_processing = !update.final;
    if (update.events) {
      queueEvents(update.events, socket, false, navigate, params);
    }
  });
  socket.current.on("reload", async (event) => {
    event_processing = false;
    on_hydrated_queue.push(event);
    queueEvents(initialEvents(), socket, true, navigate, params);
  });
  socket.current.on("new_token", async (new_token) => {
    token = new_token;
    window.sessionStorage.setItem(TOKEN_KEY, new_token);
  });

  document.addEventListener("visibilitychange", checkVisibility);
};

/**
 * Create an event object.
 * @param {string} name The name of the event.
 * @param {Object.<string, Any>} payload The payload of the event.
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
  return { name, payload, handler, event_actions };
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
      const cookie_value = cookies.get(cookie_name, { doNotParse: true });
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
  if (client_storage.session_storage && typeof window != "undefined") {
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
      if (client_storage.cookies && state_key in client_storage.cookies) {
        const cookie_options = { ...client_storage.cookies[state_key] };
        const cookie_name = cookie_options.name || state_key;
        delete cookie_options.name; // name is not a valid cookie option
        cookies.set(cookie_name, delta[substate][key], cookie_options);
      } else if (
        client_storage.local_storage &&
        state_key in client_storage.local_storage &&
        typeof window !== "undefined"
      ) {
        const options = client_storage.local_storage[state_key];
        localStorage.setItem(options.name || state_key, delta[substate][key]);
      } else if (
        client_storage.session_storage &&
        state_key in client_storage.session_storage &&
        typeof window !== "undefined"
      ) {
        const session_options = client_storage.session_storage[state_key];
        sessionStorage.setItem(
          session_options.name || state_key,
          delta[substate][key],
        );
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
  const params = useRef(paramsR);
  const mounted = useRef(false);

  useEffect(() => {
    const { "*": splat, ...remainingParams } = paramsR;
    if (splat) {
      params.current = { ...remainingParams, splat: splat.split("/") };
    } else {
      params.current = remainingParams;
    }
  }, [paramsR]);

  const ensureSocketConnected = useCallback(async () => {
    if (!mounted.current) {
      // During hot reload, some components may still have a reference to
      // addEvents, so avoid reconnecting the socket of an unmounted event loop.
      return;
    }
    // only use websockets if state is present and backend is not disabled (reflex cloud).
    if (
      Object.keys(initialState).length > 1 &&
      !isBackendDisabled() &&
      !socket.current?.connected
    ) {
      // Initialize the websocket connection.
      await connect(
        socket,
        dispatch,
        ["websocket"],
        setConnectErrors,
        client_storage,
        navigate,
        () => params.current,
      );
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
    const _events = events.filter((e) => e !== undefined && e !== null);
    if (!event_actions?.temporal) {
      // Reconnect socket if needed for non-temporal events.
      ensureSocketConnected();
    }

    if (!(args instanceof Array)) {
      args = [args];
    }

    event_actions = _events.reduce(
      (acc, e) => ({ ...acc, ...e.event_actions }),
      event_actions ?? {},
    );

    const _e = args.filter((o) => o?.preventDefault !== undefined)[0];

    if (event_actions?.preventDefault && _e?.preventDefault) {
      _e.preventDefault();
    }
    if (event_actions?.stopPropagation && _e?.stopPropagation) {
      _e.stopPropagation();
    }
    const combined_name = _events.map((e) => e.name).join("+++");
    if (event_actions?.temporal) {
      if (!socket.current || !socket.current.connected) {
        return; // don't queue when the backend is not connected
      }
    }
    if (event_actions?.throttle) {
      // If throttle returns false, the events are not added to the queue.
      if (!throttle(combined_name, event_actions.throttle)) {
        return;
      }
    }
    if (event_actions?.debounce) {
      // If debounce is used, queue the events after some delay
      debounce(
        combined_name,
        () =>
          queueEvents(_events, socket, false, navigate, () => params.current),
        event_actions.debounce,
      );
    } else {
      queueEvents(_events, socket, false, navigate, () => params.current);
    }
  }, []);

  const sentHydrate = useRef(false); // Avoid double-hydrate due to React strict-mode
  useEffect(() => {
    if (!sentHydrate.current) {
      queueEvents(
        initial_events(),
        socket,
        true,
        navigate,
        () => params.current,
      );
      sentHydrate.current = true;
    }
  }, []);

  // Handle frontend errors and send them to the backend via websocket.
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.onerror = function (msg, url, lineNo, columnNo, error) {
      addEvents([
        ReflexEvent(`${exception_state_name}.handle_frontend_exception`, {
          info: error.name + ": " + error.message + "\n" + error.stack,
          component_stack: "",
        }),
      ]);
      return false;
    };

    //NOTE: Only works in Chrome v49+
    //https://github.com/mknichel/javascript-errors?tab=readme-ov-file#promise-rejection-events
    window.onunhandledrejection = function (event) {
      addEvents([
        ReflexEvent(`${exception_state_name}.handle_frontend_exception`, {
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
    ensureSocketConnected();

    // Cleanup function.
    return () => {
      mounted.current = false;
      if (socket.current) {
        socket.current.disconnect();
        socket.current.off();
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
    (async () => {
      // Process all outstanding events.
      while (event_queue.length > 0 && !event_processing) {
        await ensureSocketConnected();
        await processEvent(socket.current, navigate, () => params.current);
      }
    })();
  });

  // localStorage event handling
  useEffect(() => {
    const storage_to_state_map = {};

    if (client_storage.local_storage && typeof window !== "undefined") {
      for (const state_key in client_storage.local_storage) {
        const options = client_storage.local_storage[state_key];
        if (options.sync) {
          const local_storage_value_key = options.name || state_key;
          storage_to_state_map[local_storage_value_key] = state_key;
        }
      }
    }

    // e is StorageEvent
    const handleStorage = (e) => {
      if (storage_to_state_map[e.key]) {
        const vars = {};
        vars[storage_to_state_map[e.key]] = e.newValue;
        const event = ReflexEvent(
          `${state_name}.reflex___state____update_vars_internal_state.update_vars_internal`,
          { vars: vars },
        );
        addEvents([event], e);
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
    addEvents(onLoadInternalEvent());

    // Update the ref
    prevLocationRef.current = location;
  }, [location, dispatch, onLoadInternalEvent, addEvents]);

  return [addEvents, connectErrors];
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

/**
 * Get the value from a ref.
 * @param ref The ref to get the value from.
 * @returns The value.
 */
export const getRefValue = (ref) => {
  if (!ref || !ref.current) {
    return;
  }
  if (ref.current.type == "checkbox") {
    return ref.current.checked; // chakra
  } else if (
    ref.current.className?.includes("rt-CheckboxRoot") ||
    ref.current.className?.includes("rt-SwitchRoot")
  ) {
    return ref.current.ariaChecked == "true"; // radix
  } else if (ref.current.className?.includes("rt-SliderRoot")) {
    // find the actual slider
    return ref.current.querySelector(".rt-SliderThumb")?.ariaValueNow;
  } else {
    //querySelector(":checked") is needed to get value from radio_group
    return (
      ref.current.value ||
      (ref.current.querySelector &&
        ref.current.querySelector(":checked") &&
        ref.current.querySelector(":checked")?.value)
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
