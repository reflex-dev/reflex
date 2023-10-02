// State management for Reflex web apps.
import axios from "axios";
import io from "socket.io-client";
import JSON5 from "json5";
import env from "env.json";
import Cookies from "universal-cookie";
import { useEffect, useReducer, useRef, useState } from "react";
import Router, { useRouter } from "next/router";


// Endpoint URLs.
const EVENTURL = env.EVENT
const UPLOADURL = env.UPLOAD

// Global variable to hold the token.
let token;

// Key for the token in the session storage.
const TOKEN_KEY = "token";

// create cookie instance
const cookies = new Cookies();

// Dictionary holding component references.
export const refs = {};

// Flag ensures that only one event is processing on the backend concurrently.
let event_processing = false
// Array holding pending events to be processed.
const event_queue = [];

/**
 * Generate a UUID (Used for session tokens).
 * Taken from: https://stackoverflow.com/questions/105034/how-do-i-create-a-guid-uuid
 * @returns A UUID.
 */
const generateUUID = () => {
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
  if (window) {
    if (!window.sessionStorage.getItem(TOKEN_KEY)) {
      window.sessionStorage.setItem(TOKEN_KEY, generateUUID());
    }
    token = window.sessionStorage.getItem(TOKEN_KEY);
  }
  return token;
};

/**
 * Apply a delta to the state.
 * @param state The state to apply the delta to.
 * @param delta The delta to apply.
 */
export const applyDelta = (state, delta) => {
  const new_state = { ...state }
  for (const substate in delta) {
    let s = new_state;
    const path = substate.split(".").slice(1);
    while (path.length > 0) {
      s = s[path.shift()];
    }
    for (const key in delta[substate]) {
      s[key] = delta[substate][key];
    }
  }
  return new_state
};


/**
 * Get all local storage items in a key-value object.
 * @returns object of items in local storage.
 */
export const getAllLocalStorageItems = () => {
  var localStorageItems = {};

  for (var i = 0, len = localStorage.length; i < len; i++) {
    var key = localStorage.key(i);
    localStorageItems[key] = localStorage.getItem(key);
  }

  return localStorageItems;
}


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
    if (event.payload.external)
      window.open(event.payload.path, "_blank");
    else
      Router.push(event.payload.path);
    return false;
  }

  if (event.name == "_console") {
    console.log(event.payload.message);
    return false;
  }

  if (event.name == "_set_cookie") {
    cookies.set(event.payload.key, event.payload.value, { path: "/" });
    return false;
  }

  if (event.name == "_remove_cookie") {
    cookies.remove(event.payload.key, { path: "/", ...event.payload.options })
    return false;
  }

  if (event.name == "_set_local_storage") {
    localStorage.setItem(event.payload.key, event.payload.value);
    return false;
  }

  if (event.name == "_clear_local_storage") {
    localStorage.clear();
    return false;
  }

  if (event.name == "_remove_local_storage") {
    localStorage.removeItem(event.payload.key);
    return false;
  }

  if (event.name == "_set_clipboard") {
    const content = event.payload.content;
    navigator.clipboard.writeText(content);
    return false;
  }
  if (event.name == "_download") {
    const a = document.createElement('a');
    a.hidden = true;
    a.href = event.payload.url;
    a.download = event.payload.filename;
    a.click();
    a.remove();
    return false;
  }

  if (event.name == "_alert") {
    alert(event.payload.message);
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
    ref.current.value = event.payload.value;
    return false;
  }

  if (event.name == "_call_script") {
    try {
      eval(event.payload.javascript_code);
    } catch (e) {
      console.log("_call_script", e);
    }
    return false;
  }

  // Update token and router data (if missing).
  event.token = getToken()
  if (event.router_data === undefined || Object.keys(event.router_data).length === 0) {
    event.router_data = (({ pathname, query, asPath }) => ({ pathname, query, asPath }))(Router)
  }

  // Send the event to the server.
  if (socket) {
    socket.emit("event", JSON.stringify(event));
    return true;
  }

  return false;
};

/**
 * Send an event to the server via REST.
 * @param event The current event.
 * @param state The state with the event queue.
 *
 * @returns Whether the event was sent.
 */
export const applyRestEvent = async (event) => {
  let eventSent = false;
  if (event.handler == "uploadFiles") {
    eventSent = await uploadFiles(event.name, event.payload.files);
  }
  return eventSent;
};

/**
 * Queue events to be processed and trigger processing of queue.
 * @param events Array of events to queue.
 * @param socket The socket object to send the event on.
 */
export const queueEvents = async (events, socket) => {
  event_queue.push(...events)
  await processEvent(socket.current)
}

/**
 * Process an event off the event queue.
 * @param socket The socket object to send the event on.
 */
export const processEvent = async (
  socket
) => {
  // Only proceed if the socket is up, otherwise we throw the event into the void
  if (!socket) {
    return;
  }

  // Only proceed if we're not already processing an event.
  if (event_queue.length === 0 || event_processing) {
    return;
  }

  // Set processing to true to block other events from being processed.
  event_processing = true

  // Apply the next event in the queue.
  const event = event_queue.shift();

  let eventSent = false
  // Process events with handlers via REST and all others via websockets.
  if (event.handler) {
    eventSent = await applyRestEvent(event);
  } else {
    eventSent = await applyEvent(event, socket);
  }
  // If no event was sent, set processing to false.
  if (!eventSent) {
    event_processing = false;
    // recursively call processEvent to drain the queue, since there is
    // no state update to trigger the useEffect event loop.
    await processEvent(socket)
  }
}

/**
 * Connect to a websocket and set the handlers.
 * @param socket The socket object to connect.
 * @param dispatch The function to queue state update
 * @param transports The transports to use.
 * @param setConnectError The function to update connection error value.
 * @param client_storage The client storage object from context.js
 */
export const connect = async (
  socket,
  dispatch,
  transports,
  setConnectError,
  client_storage = {},
) => {
  // Get backend URL object from the endpoint.
  const endpoint = new URL(EVENTURL);
  // Create the socket.
  socket.current = io(EVENTURL, {
    path: endpoint["pathname"],
    transports: transports,
    autoUnref: false,
  });

  // Once the socket is open, hydrate the page.
  socket.current.on("connect", () => {
    setConnectError(null)
  });

  socket.current.on('connect_error', (error) => {
    setConnectError(error)
  });

  // On each received message, queue the updates and events.
  socket.current.on("event", message => {
    const update = JSON5.parse(message)
    dispatch(update.delta)
    applyClientStorageDelta(client_storage, update.delta)
    event_processing = !update.final
    if (update.events) {
      queueEvents(update.events, socket)
    }
  });
};

/**
 * Upload files to the server.
 *
 * @param state The state to apply the delta to.
 * @param handler The handler to use.
 *
 * @returns Whether the files were uploaded.
 */
export const uploadFiles = async (handler, files) => {
  // return if there's no file to upload
  if (files.length == 0) {
    return false;
  }

  const headers = {
    "Content-Type": files[0].type,
  };
  const formdata = new FormData();

  // Add the token and handler to the file name.
  for (let i = 0; i < files.length; i++) {
    formdata.append(
      "files",
      files[i],
      getToken() + ":" + handler + ":" + files[i].name
    );
  }

  // Send the file to the server.
  await axios.post(UPLOADURL, formdata, headers)
    .then(() => { return true; })
    .catch(
      error => {
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
      }
    )
};

/**
 * Create an event object.
 * @param name The name of the event.
 * @param payload The payload of the event.
 * @param handler The client handler to process event.
 * @returns The event object.
 */
export const Event = (name, payload = {}, handler = null) => {
  return { name, payload, handler };
};

/**
 * Package client-side storage values as payload to send to the
 * backend with the hydrate event
 * @param client_storage The client storage object from context.js
 * @returns payload dict of client storage values
 */
export const hydrateClientStorage = (client_storage) => {
  const client_storage_values = {
    "cookies": {},
    "local_storage": {}
  }
  if (client_storage.cookies) {
    for (const state_key in client_storage.cookies) {
      const cookie_options = client_storage.cookies[state_key]
      const cookie_name = cookie_options.name || state_key
      client_storage_values.cookies[state_key] = cookies.get(cookie_name)
    }
  }
  if (client_storage.local_storage && (typeof window !== 'undefined')) {
    for (const state_key in client_storage.local_storage) {
      const options = client_storage.local_storage[state_key]
      const local_storage_value = localStorage.getItem(options.name || state_key)
      if (local_storage_value !== null) {
        client_storage_values.local_storage[state_key] = local_storage_value
      }
    }
  }
  if (client_storage.cookies || client_storage.local_storage) {
    return client_storage_values
  }
  return {}
};

/**
 * Update client storage values based on backend state delta.
 * @param client_storage The client storage object from context.js
 * @param delta The state update from the backend
 */
const applyClientStorageDelta = (client_storage, delta) => {
  // find the main state and check for is_hydrated
  const unqualified_states = Object.keys(delta).filter((key) => key.split(".").length === 1);
  if (unqualified_states.length === 1) {
    const main_state = delta[unqualified_states[0]]
    if (main_state.is_hydrated !== undefined && !main_state.is_hydrated) {
      // skip if the state is not hydrated yet, since all client storage
      // values are sent in the hydrate event
      return;
    }
  }
  // Save known client storage values to cookies and localStorage.
  for (const substate in delta) {
    for (const key in delta[substate]) {
      const state_key = `${substate}.${key}`
      if (client_storage.cookies && state_key in client_storage.cookies) {
        const cookie_options = { ...client_storage.cookies[state_key] }
        const cookie_name = cookie_options.name || state_key
        delete cookie_options.name  // name is not a valid cookie option
        cookies.set(cookie_name, delta[substate][key], cookie_options);
      } else if (client_storage.local_storage && state_key in client_storage.local_storage && (typeof window !== 'undefined')) {
        const options = client_storage.local_storage[state_key]
        localStorage.setItem(options.name || state_key, delta[substate][key]);
      }
    }
  }
}

/**
 * Establish websocket event loop for a NextJS page.
 * @param initial_state The initial app state.
 * @param initial_events The initial app events.
 * @param client_storage The client storage object from context.js
 *
 * @returns [state, addEvents, connectError] -
 *   state is a reactive dict,
 *   addEvents is used to queue an event, and
 *   connectError is a reactive js error from the websocket connection (or null if connected).
 */
export const useEventLoop = (
  initial_state = {},
  initial_events = [],
  client_storage = {},
) => {
  const socket = useRef(null)
  const router = useRouter()
  const [state, dispatch] = useReducer(applyDelta, initial_state)
  const [connectError, setConnectError] = useState(null)

  // Function to add new events to the event queue.
  const addEvents = (events, _e) => {
    preventDefault(_e);
    queueEvents(events, socket)
  }

  const sentHydrate = useRef(false);  // Avoid double-hydrate due to React strict-mode
  // initial state hydrate
  useEffect(() => {
    if (router.isReady && !sentHydrate.current) {
      addEvents(initial_events.map((e) => ({ ...e })))
      sentHydrate.current = true
    }
  }, [router.isReady])

  // Main event loop.
  useEffect(() => {
    // Skip if the router is not ready.
    if (!router.isReady) {
      return;
    }

    // Initialize the websocket connection.
    if (!socket.current) {
      connect(socket, dispatch, ['websocket', 'polling'], setConnectError, client_storage)
    }
    (async () => {
      // Process all outstanding events.
      while (event_queue.length > 0 && !event_processing) {
        await processEvent(socket.current)
      }
    })()
  })
  return [state, addEvents, connectError]
}

/***
 * Check if a value is truthy in python.
 * @param val The value to check.
 * @returns True if the value is truthy, false otherwise.
 */
export const isTrue = (val) => {
  return Array.isArray(val) ? val.length > 0 : !!val;
};

/**
 * Prevent the default event for form submission.
 * @param event
 */
export const preventDefault = (event) => {
  if (event && event.type == "submit") {
    event.preventDefault();
  }
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
    return ref.current.checked;
  } else {
    //querySelector(":checked") is needed to get value from radio_group
    return ref.current.value || (ref.current.querySelector(':checked') && ref.current.querySelector(':checked').value);
  }
}

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
  return refs.map((ref) => ref.current.value || ref.current.getAttribute("aria-valuenow"));
}

/**
* Spread two arrays or two objects.
* @param first The first array or object.
* @param second The second array or object.
* @returns The final merged array or object.
*/
export const spreadArraysOrObjects = (first, second) => {
  if (Array.isArray(first) && Array.isArray(second)) {
    return [...first, ...second];
  } else if (typeof first === 'object' && typeof second === 'object') {
    return { ...first, ...second };
  } else {
    throw new Error('Both parameters must be either arrays or objects.');
  }
}
