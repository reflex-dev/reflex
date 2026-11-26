// `reflex`: the API JavaScript run by an app reaches Reflex through, in place
// of the internals of utils/state.js. `rx.call_script` code sees it as
// `reflex`, a module imports it from here, and `rx.js` builds calls on it from
// Python. Its members read the runtime at call time, so it is safe to import
// before the event loop mounts and from a module utils/state.js imports.
import { eventLoop } from "$/utils/context-registry";
import { ReflexEvent, refs } from "$/utils/state";

/**
 * Get the name a component id is registered under in `refs`.
 *
 * Mirrors `format_ref` in reflex_base.utils.format: every run of characters
 * that are not letters, digits or underscores becomes one underscore.
 * @param {string} id The component id.
 * @returns {string} The registry key.
 */
const refName = (id) => `ref_${String(id).replace(/[^\p{L}\p{N}_]+/gu, "_")}`;

export const reflex = Object.freeze({
  /**
   * Get the ref of a component by its id.
   * @param {string} id The component id.
   * @returns {{current: any} | undefined} The ref, or undefined if no
   *   component with that id has rendered or the component's id is a Var,
   *   which registers no ref. Its `current` is null until React attaches the
   *   element.
   */
  ref: (id) => refs[refName(id)],

  /**
   * Dispatch events through the mounted event loop, as event triggers do.
   * @param {any[]} events The events, built with `reflex.event`.
   */
  addEvents: (events) => {
    eventLoop.addEvents(events);
  },

  /**
   * Build an event for `addEvents`.
   * @param {string} name The full name of the event handler, built in Python
   *   as `f"{State.get_full_name()}.handler_name"` and passed in.
   * @param {object} [payload] The handler's arguments, by name.
   * @returns {any} The event.
   */
  event: (name, payload = {}) => ReflexEvent(name, payload),
});
