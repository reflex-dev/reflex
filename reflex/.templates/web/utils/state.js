// State management for Reflex web apps.
import axios from "axios";
import io from "socket.io-client";
import JSON5 from "json5";
import env from "$/env.json";
import reflexEnvironment from "$/reflex.json";
import Cookies from "universal-cookie";
import { useEffect, useRef, useState } from "react";
import Router, { useRouter } from "next/router";
import {
  initialEvents,
  initialState,
  onLoadInternalEvent,
  state_name,
  exception_state_name,
} from "$/utils/context.js";
import debounce from "$/utils/helpers/debounce";
import throttle from "$/utils/helpers/throttle";

// Endpoint URLs.
const EVENTURL = env.EVENT;
const UPLOADURL = env.UPLOAD;

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
 *
 * @returns Adds event to queue and processes it if websocket exits, does nothing otherwise.
 */
export const queueEventIfSocketExists = async (events, socket) => {
  if (!socket) {
    return;
  }
  await queueEvents(events, socket);
};

/**
 * Handle frontend event or send the event to the backend via Websocket.
 * @param event The event to send.
 * @param socket The socket object to send the event on.
 *
 * @returns True if the event was sent, false if it was handled locally.
 */
export const applyEvent = async (event, socket) => {
  // Handle special events
  if (event.name == "_redirect") {
    if (event.payload.external) {
      window.open(event.payload.path, "_blank");
    } else if (event.payload.replace) {
      Router.replace(event.payload.path);
    } else {
      Router.push(event.payload.path);
    }
    return false;
  }

  if (event.name == "_remove_cookie") {
    cookies.remove(event.payload.key, { ...event.payload.options });
    queueEventIfSocketExists(initialEvents(), socket);
    return false;
  }

  if (event.name == "_clear_local_storage") {
    localStorage.clear();
    queueEventIfSocketExists(initialEvents(), socket);
    return false;
  }

  if (event.name == "_remove_local_storage") {
    localStorage.removeItem(event.payload.key);
    queueEventIfSocketExists(initialEvents(), socket);
    return false;
  }

  if (event.name == "_clear_session_storage") {
    sessionStorage.clear();
    queueEvents(initialEvents(), socket);
    return false;
  }

  if (event.name == "_remove_session_storage") {
    sessionStorage.removeItem(event.payload.key);
    queueEvents(initialEvents(), socket);
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
    ref.current.focus();
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
        if (!!eval_result && typeof eval_result.then === "function") {
          event.payload.callback(await eval_result);
        } else {
          event.payload.callback(eval_result);
        }
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
        if (!!eval_result && typeof eval_result.then === "function") {
          eval(event.payload.callback)(await eval_result);
        } else {
          eval(event.payload.callback)(eval_result);
        }
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
    event.router_data = (({ pathname, query, asPath }) => ({
      pathname,
      query,
      asPath,
    }))(Router);
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
 *
 * @returns Whether the event was sent.
 */
export const applyRestEvent = async (event, socket) => {
  let eventSent = false;
  if (event.handler === "uploadFiles") {
    if (event.payload.files === undefined || event.payload.files.length === 0) {
      // Submit the event over the websocket to trigger the event handler.
      return await applyEvent(Event(event.name), socket);
    }

    // Start upload, but do not wait for it, which would block other events.
    uploadFiles(
      event.name,
      event.payload.files,
      event.payload.upload_id,
      event.payload.on_upload_progress,
      socket,
    );
    return false;
  }
  return eventSent;
};

/**
 * Queue events to be processed and trigger processing of queue.
 * @param events Array of events to queue.
 * @param socket The socket object to send the event on.
 */
export const queueEvents = async (events, socket) => {
  event_queue.push(...events);
  await processEvent(socket.current);
};

/**
 * Process an event off the event queue.
 * @param socket The socket object to send the event on.
 */
export const processEvent = async (socket) => {
  // Only proceed if the socket is up and no event in the queue uses state, otherwise we throw the event into the void
  if (!socket && isStateful()) {
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
    eventSent = await applyRestEvent(event, socket);
  } else {
    eventSent = await applyEvent(event, socket);
  }
  // If no event was sent, set processing to false.
  if (!eventSent) {
    event_processing = false;
    // recursively call processEvent to drain the queue, since there is
    // no state update to trigger the useEffect event loop.
    await processEvent(socket);
  }
};

/**
 * Connect to a websocket and set the handlers.
 * @param socket The socket object to connect.
 * @param dispatch The function to queue state update
 * @param transports The transports to use.
 * @param setConnectErrors The function to update connection error value.
 * @param client_storage The client storage object from context.js
 */
export const connect = async (
  socket,
  dispatch,
  transports,
  setConnectErrors,
  client_storage = {},
) => {
  // Get backend URL object from the endpoint.
  const endpoint = getBackendURL(EVENTURL);

  // Create the socket.
  socket.current = io(endpoint.href, {
    path: endpoint["pathname"],
    transports: transports,
    protocols: [reflexEnvironment.version],
    autoUnref: false,
  });
  // Ensure undefined fields in events are sent as null instead of removed
  socket.current.io.encoder.replacer = (k, v) => (v === undefined ? null : v);
  socket.current.io.decoder.tryParse = (str) => {
    try {
      return JSON5.parse(str);
    } catch (e) {
      return false;
    }
  };

  function checkVisibility() {
    if (document.visibilityState === "visible") {
      if (!socket.current.connected) {
        console.log("Socket is disconnected, attempting to reconnect ");
        socket.current.connect();
      } else {
        console.log("Socket is reconnected ");
      }
    }
  }

  const pagehideHandler = (event) => {
    if (event.persisted && socket.current?.connected) {
      console.log("Disconnect backend before bfcache on navigation");
      socket.current.disconnect();
    }
  };

  // Once the socket is open, hydrate the page.
  socket.current.on("connect", () => {
    setConnectErrors([]);
    window.addEventListener("pagehide", pagehideHandler);
  });

  socket.current.on("connect_error", (error) => {
    setConnectErrors((connectErrors) => [connectErrors.slice(-9), error]);
  });

  // When the socket disconnects reset the event_processing flag
  socket.current.on("disconnect", () => {
    event_processing = false;
    window.removeEventListener("pagehide", pagehideHandler);
  });

  // On each received message, queue the updates and events.
  socket.current.on("event", async (update) => {
    for (const substate in update.delta) {
      dispatch[substate](update.delta[substate]);
    }
    applyClientStorageDelta(client_storage, update.delta);
    event_processing = !update.final;
    if (update.events) {
      queueEvents(update.events, socket);
    }
  });
  socket.current.on("reload", async (event) => {
    event_processing = false;
    queueEvents([...initialEvents(), event], socket);
  });

  document.addEventListener("visibilitychange", checkVisibility);
};

/**
 * Upload files to the server.
 *
 * @param state The state to apply the delta to.
 * @param handler The handler to use.
 * @param upload_id The upload id to use.
 * @param on_upload_progress The function to call on upload progress.
 * @param socket the websocket connection
 *
 * @returns The response from posting to the UPLOADURL endpoint.
 */
export const uploadFiles = async (
  handler,
  files,
  upload_id,
  on_upload_progress,
  socket,
) => {
  // return if there's no file to upload
  if (files === undefined || files.length === 0) {
    return false;
  }

  const upload_ref_name = `__upload_controllers_${upload_id}`;

  if (refs[upload_ref_name]) {
    console.log("Upload already in progress for ", upload_id);
    return false;
  }

  // Track how many partial updates have been processed for this upload.
  let resp_idx = 0;
  const eventHandler = (progressEvent) => {
    const event_callbacks = socket._callbacks.$event;
    // Whenever called, responseText will contain the entire response so far.
    const chunks = progressEvent.event.target.responseText.trim().split("\n");
    // So only process _new_ chunks beyond resp_idx.
    chunks.slice(resp_idx).map((chunk_json) => {
      try {
        const chunk = JSON5.parse(chunk_json);
        event_callbacks.map((f, ix) => {
          f(chunk)
            .then(() => {
              if (ix === event_callbacks.length - 1) {
                // Mark this chunk as processed.
                resp_idx += 1;
              }
            })
            .catch((e) => {
              if (progressEvent.progress === 1) {
                // Chunk may be incomplete, so only report errors when full response is available.
                console.log("Error processing chunk", chunk, e);
              }
              return;
            });
        });
      } catch (e) {
        if (progressEvent.progress === 1) {
          console.log("Error parsing chunk", chunk_json, e);
        }
        return;
      }
    });
  };

  const controller = new AbortController();
  const config = {
    headers: {
      "Reflex-Client-Token": getToken(),
      "Reflex-Event-Handler": handler,
    },
    signal: controller.signal,
    onDownloadProgress: eventHandler,
  };
  if (on_upload_progress) {
    config["onUploadProgress"] = on_upload_progress;
  }
  const formdata = new FormData();

  // Add the token and handler to the file name.
  files.forEach((file) => {
    formdata.append("files", file, file.path || file.name);
  });

  // Send the file to the server.
  refs[upload_ref_name] = controller;

  try {
    return await axios.post(getBackendURL(UPLOADURL), formdata, config);
  } catch (error) {
    if (error.response) {
      // The request was made and the server responded with a status code
      // that falls out of the range of 2xx
      console.log(error.response.data);
    } else if (error.request) {
      // The request was made but no response was received
      // `error.request` is an instance of XMLHttpRequest in the browser and an instance of
      // http.ClientRequest in node.js
      console.log(error.request);
    } else {
      // Something happened in setting up the request that triggered an Error
      console.log(error.message);
    }
    return false;
  } finally {
    delete refs[upload_ref_name];
  }
};

/**
 * Create an event object.
 * @param {string} name The name of the event.
 * @param {Object.<string, Any>} payload The payload of the event.
 * @param {Object.<string, (number|boolean)>} event_actions The actions to take on the event.
 * @param {string} handler The client handler to process event.
 * @returns The event object.
 */
export const Event = (
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
      const cookie_value = cookies.get(cookie_name);
      if (cookie_value !== undefined) {
        client_storage_values[state_key] = cookies.get(cookie_name);
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
    if (main_state.is_hydrated !== undefined && !main_state.is_hydrated) {
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
 * Establish websocket event loop for a NextJS page.
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
  const router = useRouter();
  const [connectErrors, setConnectErrors] = useState([]);

  // Function to add new events to the event queue.
  const addEvents = (events, args, event_actions) => {
    if (!(args instanceof Array)) {
      args = [args];
    }

    event_actions = events.reduce(
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
    const combined_name = events.map((e) => e.name).join("+++");
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
        () => queueEvents(events, socket),
        event_actions.debounce,
      );
    } else {
      queueEvents(events, socket);
    }
  };

  const sentHydrate = useRef(false); // Avoid double-hydrate due to React strict-mode
  useEffect(() => {
    if (router.isReady && !sentHydrate.current) {
      const events = initial_events();
      addEvents(
        events.map((e) => ({
          ...e,
          router_data: (({ pathname, query, asPath }) => ({
            pathname,
            query,
            asPath,
          }))(router),
        })),
      );
      sentHydrate.current = true;
    }
  }, [router.isReady]);

  // Handle frontend errors and send them to the backend via websocket.
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.onerror = function (msg, url, lineNo, columnNo, error) {
      addEvents([
        Event(`${exception_state_name}.handle_frontend_exception`, {
          stack: error.stack,
          component_stack: "",
        }),
      ]);
      return false;
    };

    //NOTE: Only works in Chrome v49+
    //https://github.com/mknichel/javascript-errors?tab=readme-ov-file#promise-rejection-events
    window.onunhandledrejection = function (event) {
      addEvents([
        Event(`${exception_state_name}.handle_frontend_exception`, {
          stack: event.reason?.stack,
          component_stack: "",
        }),
      ]);
      return false;
    };
  }, []);

  // Handle socket connect/disconnect.
  useEffect(() => {
    // only use websockets if state is present and backend is not disabled (reflex cloud).
    if (Object.keys(initialState).length > 1 && !isBackendDisabled()) {
      // Initialize the websocket connection.
      if (!socket.current) {
        connect(
          socket,
          dispatch,
          ["websocket"],
          setConnectErrors,
          client_storage,
        );
      }
    }

    // Cleanup function.
    return () => {
      if (socket.current) {
        socket.current.disconnect();
      }
    };
  }, []);

  // Main event loop.
  useEffect(() => {
    // Skip if the router is not ready.
    if (!router.isReady || isBackendDisabled()) {
      return;
    }
    (async () => {
      // Process all outstanding events.
      while (event_queue.length > 0 && !event_processing) {
        await processEvent(socket.current);
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
        const event = Event(
          `${state_name}.reflex___state____update_vars_internal_state.update_vars_internal`,
          { vars: vars },
        );
        addEvents([event], e);
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  });

  // Route after the initial page hydration.
  useEffect(() => {
    const change_start = () => {
      const main_state_dispatch = dispatch["reflex___state____state"];
      if (main_state_dispatch !== undefined) {
        main_state_dispatch({ is_hydrated: false });
      }
    };
    const change_complete = () => addEvents(onLoadInternalEvent());
    const change_error = () => {
      // Remove cached error state from router for this page, otherwise the
      // page will never send on_load events again.
      if (router.components[router.pathname].error) {
        delete router.components[router.pathname].error;
      }
    };
    router.events.on("routeChangeStart", change_start);
    router.events.on("routeChangeComplete", change_complete);
    router.events.on("routeChangeError", change_error);
    return () => {
      router.events.off("routeChangeStart", change_start);
      router.events.off("routeChangeComplete", change_complete);
      router.events.off("routeChangeError", change_error);
    };
  }, [router]);

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
