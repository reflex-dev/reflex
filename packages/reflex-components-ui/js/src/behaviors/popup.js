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
  return popup.id
    ? document.querySelector(`[popovertarget="${popup.id}"]`)
    : null;
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

/** What says how far a popup is from whole pixels, across and down. */
const SNAP = ["--rx-popup-snap-x", "--rx-popup-snap-y"];

/**
 * Say how far a popup is laid out from whole pixels.
 *
 * Where it is laid out is read from where it is drawn, less the transform
 * it comes in with.
 *
 * @param {HTMLElement} popup The popover.
 * @returns {number[]} What brings it to whole pixels, across and down.
 */
function off(popup) {
  const { transform, transformOrigin } = getComputedStyle(popup);
  const [a = 1, , , d = 1, e = 0, f = 0] = (
    transform.match(/-?[\d.]+(e-?\d+)?/g) ?? []
  ).map(Number);
  const [x = 0, y = 0] = transformOrigin
    .split(" ")
    .map((length) => Number.parseFloat(length) || 0);
  const box = popup.getBoundingClientRect();
  const ratio = globalThis.devicePixelRatio || 1;
  return [box.x - x * (1 - a) - e, box.y - y * (1 - d) - f].map((at) => {
    // In the units a browser lays out in: a sixty-fourth of a pixel, or
    // close to it, and what is left of one is nothing.
    const by = Math.round((Math.round(at * ratio) / ratio - at) * 64) / 64;
    return Math.abs(by) < 0.02 ? 0 : by;
  });
}

/**
 * Put an open popup on whole pixels, as Radix puts the ones it places.
 *
 * A popup that ends at the end of its anchor, or is centered on it, starts
 * on a fraction of a pixel when its width has one. Its styles move it by
 * what is written here, in its margins: it is laid out there, not drawn
 * there by a transform, which would blur it.
 *
 * @param {HTMLElement} popup The popover.
 * @returns {void}
 */
function snap(popup) {
  const { style } = popup;
  for (const name of SNAP) style.removeProperty(name);
  const wanted = off(popup);
  wanted.forEach((by, axis) => by && style.setProperty(SNAP[axis], `${by}px`));
  // A popup the browser turned over has its margins turned over with it.
  off(popup).forEach(
    (left, axis) => left && style.setProperty(SNAP[axis], `${-wanted[axis]}px`),
  );
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
    import("./popup-position.js").then(({ place }) =>
      place(popup, trigger, open),
    );
  }
  return open;
}

/**
 * Put a popup that is about to open on whole pixels before it is first
 * drawn: the `onBeforeToggle` of the popover.
 *
 * The browser keeps the fraction of a pixel a popover is first drawn at, in
 * the edges of its letters, so moving it once it has been seen is too late:
 * it is moved in the frame that shows it.
 *
 * @param {{ currentTarget: HTMLElement, newState?: string }} event The toggle to come.
 * @returns {void}
 */
export function popupBeforeToggle(event) {
  const popup = event.currentTarget;
  if (ANCHORED && event.newState === "open") {
    requestAnimationFrame(() => snap(popup));
  }
}
