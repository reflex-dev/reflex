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

export const applyEvent = async (state, event, router, socket) => {
  // Handle special events
  if (event.name == "_redirect") {
    router.push(event.payload.path);
  }

  if (event.name == "_console") {
    console.log(event.payload.message);
  }

  if (event.name == "_alert") {
    alert(event.payload.message);
  }

  event.token = getToken();
  if (socket) {
    socket.send(JSON.stringify(event));
  }
};

export const updateState = async (
  state,
  result,
  setResult,
  router,
  socket,
) => {
  if (result.processing || state.events.length == 0) {
    return;
  }
  if (!socket.readyState) {
    return
  }
  setResult({ ...result, processing: true });
  await applyEvent(
    state,
    state.events.shift(),
    router,
    socket
  );
};

export const E = (name, payload) => {
  return { name, payload };
};

export const connect = async (socket, state, setResult, endpoint) => {
    socket.current = new WebSocket(endpoint);
    socket.current.onmessage = function(update) {
      update = JSON.parse(update.data)
      applyDelta(state, update.delta);
      setResult({
        processing: false,
        state: state,
        events: update.events,
      });
    };
  }
