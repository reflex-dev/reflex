// State management for Pynecone web apps.
import io from 'socket.io-client';

// Global variable to hold the token.
let token;

// Key for the token in the session storage.
const TOKEN_KEY = "token";

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
  for (const substate in delta) {
    let s = state;
    const path = substate.split(".").slice(1);
    while (path.length > 0) {
      s = s[path.shift()];
    }
    for (const key in delta[substate]) {
      s[key] = delta[substate][key];
    }
  }
};

/**
 * Send an event to the server.
 * @param event The event to send.
 * @param router The router object.
 * @param socket The socket object to send the event on.
 *
 * @returns True if the event was sent, false if it was handled locally.
 */
export const applyEvent = async (event, router, socket) => {
  // Handle special events
  if (event.name == "_redirect") {
    router.push(event.payload.path);
    return false;
  }

  if (event.name == "_console") {
    console.log(event.payload.message);
    return false;
  }

  if (event.name == "_alert") {
    alert(event.payload.message);
    return false;
  }

  // Send the event to the server.
  event.token = getToken();
  event.router_data = (({ pathname, query }) => ({ pathname, query }))(router);
  if (socket) {
    socket.emit("event", JSON.stringify(event));
    return true;
  }

  return false;
};

/**
 * Process an event off the event queue.
 * @param state The state with the event queue.
 * @param setState The function to set the state.
 * @param result The current result
 * @param setResult The function to set the result.
 * @param router The router object.
 * @param socket The socket object to send the event on.
 */
export const updateState = async (state, setState, result, setResult, router, socket) => {
  // If we are already processing an event, or there are no events to process, return.
  if (result.processing || state.events.length == 0) {
    return;
  }

  // Set processing to true to block other events from being processed.
  setResult({ ...result, processing: true });

  // Pop the next event off the queue and apply it.
  const event = state.events.shift()

  // Set new events to avoid reprocessing the same event.
  setState({ ...state, events: state.events });

  // Apply the event.
  const eventSent = await applyEvent(event, router, socket);
  if (!eventSent) {
    // If no event was sent, set processing to false and return.
    setResult({...state, processing: false})
  }
};

/**
 * Connect to a websocket and set the handlers.
 * @param socket The socket object to connect.
 * @param state The state object to apply the deltas to.
 * @param setState The function to set the state.
 * @param setResult The function to set the result.
 * @param endpoint The endpoint to connect to.
 */
export const connect = async (socket, state, setState, result, setResult, router, endpoint, transports) => {
  // Get backend URL object from the endpoint
  const endpoint_url = new URL(endpoint)
  // Create the socket.
  socket.current = io(endpoint, {
    path: endpoint_url['pathname'],
    transports: transports,
    autoUnref: false,
  });

  // Once the socket is open, hydrate the page.
  socket.current.on('connect', () => {
    updateState(state, setState, result, setResult, router, socket.current);
  });

  // On each received message, apply the delta and set the result.
  socket.current.on('event', function (update) {
    update = JSON.parse(update);
    applyDelta(state, update.delta);
    setResult({
      processing: false,
      state: state,
      events: update.events,
    });
  });
};

/**
 * Create an event object.
 * @param name The name of the event.
 * @param payload The payload of the event.
 * @returns The event object.
 */
export const E = (name, payload) => {
  return { name, payload };
};
