// The script environment: the one object registered scripts reach Reflex
// through. Everything is read at call time, so a script module can import
// this before the event loop mounts.
import { eventLoop } from "$/utils/context-registry";
import { ReflexEvent, refs } from "$/utils/state";

export const env = Object.freeze({
  /**
   * Get the ref of a component by its id.
   * @param {string} id The component id.
   * @returns {any} The ref, or undefined if no such component is mounted.
   */
  ref: (id) => refs[`ref_${id}`],
  /**
   * Queue events to the backend.
   * @param {...any} args Passed to the mounted event loop's addEvents.
   * @returns {any} Whatever addEvents returns.
   */
  addEvents: (...args) => eventLoop.addEvents(...args),
  /**
   * Build an event to pass to addEvents.
   * @param {string} name The full event handler name.
   * @param {object} payload The handler arguments.
   * @returns {any} The event.
   */
  event: (name, payload = {}) => ReflexEvent(name, payload),
});
