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
   *   component with that id has mounted.
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
   * @param {string} name The full name of the event handler.
   * @param {object} [payload] The handler's arguments, by name.
   * @returns {any} The event.
   */
  event: (name, payload = {}) => ReflexEvent(name, payload),

  /**
   * Get an npm library bundled for dynamic components, loading it first when
   * the app loads optional libraries lazily.
   * @param {string} name The library's import name, e.g. "react".
   * @returns {Promise<any>} The library's module namespace.
   */
  library: async (name) => {
    if (name.startsWith("$/")) {
      throw new Error(
        `reflex.library("${name}") cannot load "${name}": a name starting with "$/" is a module of the app's frontend, not a bundled npm library. Use reflex.ref, reflex.addEvents and reflex.event instead of Reflex internals, and import your own modules from a JavaScript module.`,
      );
    }
    await window.__reflex_load?.([name]);
    // Without lazy loading, the app root registers the libraries in an effect.
    if (window.__reflex === undefined) {
      throw new Error(
        `reflex.library("${name}") cannot load "${name}" yet: the app registers its bundled libraries when it first mounts, and it has not mounted. Call reflex.library from an event, such as on_mount or on_click, rather than while a module loads.`,
      );
    }
    const module = window.__reflex[name];
    if (module === undefined) {
      throw new Error(
        `reflex.library("${name}") cannot load "${name}": the app does not bundle it for dynamic components. Bundle it by calling bundle_library("${name}") from reflex.components.dynamic in your app's Python code.`,
      );
    }
    return module;
  },
});
