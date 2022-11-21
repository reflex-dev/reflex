import axios from "axios";

let token;
const TOKEN_KEY = "token";

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

export const applyEvent = async (state, event, endpoint, router) => {
  // Handle special events
  if (event.name == "_redirect") {
    router.push(event.payload.path);
    return [];
  }

  if (event.name == "_console") {
    console.log(event.payload.message);
    return [];
  }

  if (event.name == "_alert") {
    alert(event.payload.message);
    return [];
  }

  event.token = getToken();
  const update = (await axios.post(endpoint, event)).data;
  applyDelta(state, update.delta);
  return update.events;
};

export const updateState = async (
  state,
  result,
  setResult,
  endpoint,
  router
) => {
  if (result.processing || state.events.length == 0) {
    return;
  }
  setResult({ ...result, processing: true });
  const events = await applyEvent(
    state,
    state.events.shift(),
    endpoint,
    router
  );
  setResult({
    processing: true,
    state: state,
    events: events,
  });
};

export const E = (name, payload) => {
  return { name, payload };
};
