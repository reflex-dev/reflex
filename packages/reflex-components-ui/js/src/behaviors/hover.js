// A popup that opens under the pointer and with the focus of the keyboard:
// a tooltip, a hover card.
//
// The popup is a native popover the browser puts over everything else and
// CSS places against what opens it. Nothing in a browser opens one on
// hover in every engine, so a script does: after a delay under the pointer,
// at once with the focus of the keyboard, and it closes the popup when
// both have left, on Escape and on a press outside it. Without this the
// popup never shows; a tooltip still describes what it is on.

/** Whether the browser places a popover beside its anchor by itself. */
const ANCHORED = globalThis.CSS?.supports?.("position-area: bottom") ?? false;

let ids = 0;

/**
 * @typedef {{ open?: (open: boolean) => void, escape?: () => void, outside?: () => void }} Handlers
 * @typedef {{ on?: Handlers | null, bound?: boolean, timer?: number, off?: () => void }} State
 */

/** @type {WeakMap<HTMLElement, State>} */
const popups = new WeakMap();

/**
 * Find what a popup opens under.
 *
 * @param {HTMLElement} popup The popover.
 * @returns {HTMLElement | null} The element that names it.
 */
function triggerOf(popup) {
  return document.querySelector(`[data-rx-hover="${popup.id}"]`);
}

/**
 * Open or close a popup, and say so on what it opens under.
 *
 * While it is open, Escape and a press outside it close it, wherever the
 * focus is.
 *
 * @param {HTMLElement} popup The popover.
 * @param {boolean} open Whether to open it.
 * @returns {void}
 */
function set(popup, open) {
  const state = popups.get(popup);
  if (!state || open === popup.matches(":popover-open")) return;
  popup.togglePopover(open);
  const trigger = triggerOf(popup);
  if (trigger) {
    const shown = popup.role === "tooltip" ? "delayed-open" : "open";
    trigger.dataset.state = open ? shown : "closed";
    if (!ANCHORED)
      import("./popup-position.js").then(({ place }) =>
        place(popup, trigger, open),
      );
  }
  state.off?.();
  delete state.off;
  if (!open) return;
  const dismiss = (/** @type {Event} */ event) => {
    if (event.type !== "keydown") {
      if (!popup.contains(/** @type {Node} */ (event.target)))
        ask(popup, false, "outside");
    } else if (/** @type {KeyboardEvent} */ (event).key === "Escape")
      ask(popup, false, "escape");
  };
  addEventListener("keydown", dismiss, true);
  addEventListener("pointerdown", dismiss, true);
  state.off = () => {
    removeEventListener("keydown", dismiss, true);
    removeEventListener("pointerdown", dismiss, true);
  };
}

/**
 * Open or close a popup as its user asks: a popup bound to state says so
 * to its state instead, and shows what the state then holds.
 *
 * @param {HTMLElement} popup The popover.
 * @param {boolean} open Whether to open it.
 * @param {"escape" | "outside"} [why] What dismissed it.
 * @returns {void}
 */
function ask(popup, open, why) {
  const state = popups.get(popup);
  if (!state) return;
  clearTimeout(state.timer);
  if (open === popup.matches(":popover-open")) return;
  if (why) state.on?.[why]?.();
  state.on?.open?.(open);
  if (!state.bound) set(popup, open);
}

/**
 * Keep a popup as its state says: the `ref` of the popover, called again
 * whenever the page renders.
 *
 * The first time, the popup and what it opens under are given a name no
 * other pair of the page has, which CSS places the popup by: the popups a
 * loop renders share the id they are rendered with.
 *
 * @param {HTMLElement | null} popup The popover.
 * @param {boolean | null} [open] Whether a popup bound to state is open.
 * @param {Handlers | null} [on] What the popup does when it opens, closes
 *   or is dismissed.
 * @returns {void}
 */
export function hoverSync(popup, open, on) {
  if (!popup) return;
  let state = popups.get(popup);
  let wanted = open ?? null;
  if (!state) {
    popups.set(popup, (state = {}));
    const trigger = triggerOf(popup);
    if (trigger) {
      const id = popup.id.startsWith("rx-")
        ? `${popup.id}-${++ids}`
        : popup.id;
      if (trigger.getAttribute("aria-describedby") === popup.id)
        trigger.setAttribute("aria-describedby", id);
      trigger.dataset.rxHover = popup.id = id;
      trigger.style.setProperty("anchor-name", `--${id}`);
      popup.style.setProperty("position-anchor", `--${id}`);
    }
    if (popup.dataset.defaultOpen === "true") wanted ??= true;
  }
  state.on = on;
  state.bound = open != null;
  if (wanted !== null) set(popup, wanted);
}

/**
 * Follow the pointer and the focus on a popup and on what it opens under:
 * the `onPointerEnter`, `onPointerLeave`, `onFocus`, `onBlur` and
 * `onPointerDown` of either.
 *
 * The pointer opens the popup and closes it after the delays the popup
 * says, so it can go from one to the other. The focus of the keyboard
 * opens it at once, and closes it when it leaves both. A press on what a
 * tooltip is on closes the tooltip.
 *
 * @param {{ type: string, currentTarget: HTMLElement, pointerType?: string, relatedTarget?: EventTarget | null }} event
 *   The pointer or the focus coming or going.
 * @returns {void}
 */
export function hoverEvent(event) {
  const element = event.currentTarget;
  const popup = element.hasAttribute("popover")
    ? element
    : document.getElementById(element.dataset.rxHover ?? "");
  const state = popup && popups.get(popup);
  const { type } = event;
  const to = /** @type {Node | null} */ (event.relatedTarget ?? null);
  if (
    !state ||
    event.pointerType === "touch" ||
    (type === "focus" && !element.matches(":focus-visible")) ||
    (type === "blur" && (popup.contains(to) || triggerOf(popup)?.contains(to)))
  )
    return;
  const open = type === "pointerenter" || type === "focus";
  const data = popup.dataset;
  clearTimeout(state.timer);
  state.timer = Number(
    setTimeout(
      () => ask(popup, open),
      type === "pointerenter" || type === "pointerleave"
        ? Number(open ? data.openDelay : data.closeDelay)
        : 0,
    ),
  );
}
