import { queueEvents, getToken, cookies } from "/utils/state.js"
import { initialEvents } from "utils/context.js"
import Router from "next/router";



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
    queueEvents(initialEvents(), socket)
    return false;
  }

  if (event.name == "_set_local_storage") {
    localStorage.setItem(event.payload.key, event.payload.value);
    return false;
  }

  if (event.name == "_clear_local_storage") {
    localStorage.clear();
    queueEvents(initialEvents(), socket)
    return false;
  }

  if (event.name == "_remove_local_storage") {
    localStorage.removeItem(event.payload.key);
    queueEvents(initialEvents(), socket)
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