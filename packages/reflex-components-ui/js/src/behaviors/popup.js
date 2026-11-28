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
  // An id an app gave a popup is its own to keep.
  if (
    !trigger ||
    !popup.id.startsWith("rx-") ||
    popup.hasAttribute("data-rx-popup-paired")
  )
    return;
  // What closes the popup from inside it names it too.
  const named = [
    trigger,
    ...popup.querySelectorAll(`[popovertarget="${popup.id}"]`),
  ];
  popup.id = `${popup.id || "rx-popup"}-${++ids}`;
  popup.setAttribute("data-rx-popup-paired", "");
  for (const element of named) element.setAttribute("popovertarget", popup.id);
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
    import("./popup-position.js").then(({ place }) =>
      place(popup, trigger, open),
    );
  }
  return open;
}

/**
 * Keep a popup as its state says: the `ref` of the popover, called again
 * whenever the page renders.
 *
 * @param {HTMLElement | null} popup The popover.
 * @param {boolean | null} [open] Whether a popup bound to state is open.
 * @returns {void}
 */
export function popupSync(popup, open) {
  if (!popup) return;
  pair(popup, opener(popup));
  const starts = popup.dataset.defaultOpen === "true";
  delete popup.dataset.defaultOpen;
  const wanted = open ?? (starts || null);
  if (wanted !== null && wanted !== popup.matches(":popover-open")) {
    popup.dataset.rxClosedBy = "state";
    popup.togglePopover(wanted);
  }
}

/**
 * Follow a popup that holds controls of its own, as a popover does: its
 * `onToggle`, `onKeyDown`, `onClick` and `onBlur`.
 *
 * The popup takes the focus when it opens, and closes when the focus
 * leaves it for anything but what opens it, as in Radix. It says when it
 * opens and closes, and what closed it: Escape, the focus, or a pointer
 * outside it.
 *
 * @param {{ type: string, target: EventTarget | null, currentTarget: HTMLElement, newState?: string, key?: string, relatedTarget?: EventTarget | null }} event
 *   The toggle, the key going down, the press or the focus leaving.
 * @param {{ open?: (open: boolean) => void, openAutoFocus?: () => void, closeAutoFocus?: () => void, escape?: () => void, outside?: () => void, focusOutside?: () => void, interact?: () => void } | null} [on]
 *   What the popup does when it opens, closes or is dismissed.
 * @returns {void}
 */
export function popupEvent(event, on) {
  const popup = event.currentTarget;
  const { type, target } = event;
  const data = popup.dataset;
  if (type === "keydown") {
    if (event.key === "Escape") data.rxClosedBy = "escape";
  } else if (type === "click") {
    if (
      target instanceof Element &&
      target.closest("[popovertargetaction=hide]")
    )
      data.rxClosedBy = "close";
  } else if (type === "blur") {
    const to = event.relatedTarget;
    // A press outside the popup is the browser's to close it by.
    if (
      to instanceof Element &&
      !popup.contains(to) &&
      to !== opener(popup) &&
      !to.matches(":active")
    ) {
      data.rxClosedBy = "focus";
      popup.hidePopover();
    }
  } else if (target === popup) {
    const open = popupToggle(event);
    const by = data.rxClosedBy;
    delete data.rxClosedBy;
    if (open) {
      if (by !== "state") on?.open?.(open);
      popup.focus();
      on?.openAutoFocus?.();
      return;
    }
    if (by === "escape") on?.escape?.();
    if (by === "focus") on?.focusOutside?.();
    if (!by) on?.outside?.();
    if (!by || by === "focus") on?.interact?.();
    if (by !== "state") on?.open?.(open);
    on?.closeAutoFocus?.();
  }
}
