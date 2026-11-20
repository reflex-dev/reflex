// The script environment: the API JavaScript run by an app reaches Reflex
// through, in place of the internals of utils/state.js. It is passed to
// `rx.call_script` code as `env`, a module imports it as `env`, and
// `rx.js.env` builds expressions on it from Python. Its members read the
// runtime at call time, so it is safe to import before the event loop mounts
// and from a module utils/state.js imports.
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
const refName = (id) =>
  `ref_${String(id).replace(/[^\p{L}\p{N}_]+/gu, "_")}`;

export const env = Object.freeze({
  /**
   * Every registered component ref, by registry key (`ref_<id>`).
   * @returns {Record<string, any>} The ref registry.
   */
  get refs() {
    return refs;
  },

  /**
   * Get the ref of a component by its id.
   * @param {string} id The component id.
   * @returns {{current: any} | undefined} The ref, or undefined if no
   *   component with that id has mounted.
   */
  ref: (id) => refs[refName(id)],

  /**
   * Dispatch events through the mounted event loop, as event triggers do.
   * @param {any[]} events The events, built with `env.event`.
   * @param {any[]} [args] The arguments of the triggering call.
   * @param {object} [eventActions] Event actions such as preventDefault.
   * @returns {any} Whatever the event loop's addEvents returns.
   */
  addEvents: (events, args = [], eventActions = {}) =>
    eventLoop.addEvents(events, args, eventActions),

  /**
   * Build an event for `addEvents`.
   * @param {string} name The full name of the event handler.
   * @param {object} [payload] The handler's arguments, by name.
   * @returns {any} The event.
   */
  event: (name, payload = {}) => ReflexEvent(name, payload),

  /**
   * Get a library bundled for dynamic components, loading it first when the
   * app loads optional libraries lazily.
   * @param {string} name The library's import name, e.g. "react".
   * @returns {Promise<any>} The library's module namespace.
   */
  library: async (name) => {
    await window.__reflex_load?.([name]);
    const module = window.__reflex?.[name];
    if (module === undefined) {
      throw new Error(`${name} is not a bundled library of this app.`);
    }
    return module;
  },
});
