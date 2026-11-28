// A popup: a native popover placed beside the element that opens it.
//
// The browser opens it from its `popovertarget`, puts it over everything
// else, closes it on Escape and on a pointer outside it, and gives the
// focus back. CSS places it against its anchor and turns it over where it
// would leave the viewport. What is left for a script is to say on the
// element that opens it that it is open, and to place it where the browser
// has no anchor positioning: that part is loaded only there.

/** Whether the browser places a popover beside its anchor by itself. */
const ANCHORED = globalThis.CSS?.supports?.("position-area: bottom") ?? false;

let ids = 0;

/**
 * Find what opens a popup.
 *
 * @param {Element} popup The popover.
 * @returns {Element | null} The first element whose `popovertarget` it is.
 */
export function opener(popup) {
  return popup.id ? document.querySelector(`[popovertarget="${popup.id}"]`) : null;
}

/**
 * Give a popup and what opens it an id no other popup of the page has.
 *
 * A page renders one id for each popup written, so the popups a loop
 * renders share one: the first sync of each makes them distinct.
 *
 * @param {Element} popup The popover.
 * @param {Element | null} trigger What opens it.
 * @returns {void}
 */
export function pair(popup, trigger) {
  if (!trigger || popup.hasAttribute("data-rx-popup-paired")) return;
  popup.id = `${popup.id || "rx-popup"}-${++ids}`;
  popup.setAttribute("data-rx-popup-paired", "");
  trigger.setAttribute("popovertarget", popup.id);
  trigger.setAttribute("aria-controls", popup.id);
}

/**
 * Follow a popup that opens or closes: the `onToggle` of the popover.
 *
 * What opens it says so in `aria-expanded` and `data-state`, for styles and
 * for assistive technology.
 *
 * @param {{ currentTarget: HTMLElement, newState?: string }} event The toggle.
 * @returns {boolean} Whether the popup is open now.
 */
export function popupToggle(event) {
  const popup = event.currentTarget;
  const open = event.newState === "open";
  const trigger = opener(popup);
  if (trigger) {
    trigger.setAttribute("aria-expanded", String(open));
    trigger.setAttribute("data-state", open ? "open" : "closed");
  }
  if (!ANCHORED && trigger) {
    import("./popup-position.js").then(({ place }) => place(popup, trigger, open));
  }
  return open;
}
