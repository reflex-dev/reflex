// What the event loop in utils/state.js and the backend connection in
// utils/socket.js share. Only an app with state bundles utils/socket.js, so
// utils/state.js cannot import it: the two meet here instead.
import { useEffect, useRef } from "react";
import { useLocation, useNavigate, useParams } from "react-router";
import env from "$/env.json";

// What utils/socket.js provides, registered when it loads. Empty in an app
// without state, which has no backend to connect to.
export const backend = {};

// A frontend event naming one synced localStorage var, turned into an
// update_vars_internal event when it is sent: see syncLocalStorageEvent.
export const SYNC_LOCAL_STORAGE = "_sync_local_storage";

// Array holding pending events to be processed.
export const event_queue = [];

// Mirrors the data router's location so applyEvent can populate router_data
// with the in-widget URL. In embed mode the host page's window.location is
// unrelated to the Reflex route, so the backend's on_load and dynamic-route
// matching rely on this ref instead. Updated by useEventRoute once mounted;
// pre-seeded in embed mode with the memory router's initial path (see
// initialEntries in entry.client.embed.js) so events dispatched before the
// first effect commit don't briefly fall back to the host page's URL.
export const locationRef = {
  current: env.MOUNT_TARGET ? { pathname: "/", search: "", hash: "" } : null,
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
 * Track the route an event is dispatched from.
 *
 * Keeps `locationRef` on the router's location, and the route params in a ref
 * the event queue reads when it sends an event.
 * @returns The navigate function, the ref to the route params, and the location.
 */
export const useEventRoute = () => {
  const location = useLocation();
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

  useEffect(() => {
    locationRef.current = location;
  }, [location]);

  return /** @type {const} */ ([navigate, params, location]);
};
