// What a dialog does that the browser leaves to a script.
//
// The dialog is a native `dialog` opened with `showModal`: the browser puts
// it over everything else, makes the page behind it inert, moves the focus
// in and gives it back, and closes the topmost one on Escape. Left for a
// script: opening it from its trigger and closing it from a button or
// beside its panel where the browser has no commands, saying on the trigger
// that it is open, the events of the dialog, and a dialog bound to state,
// which shows what its state holds.

const ROOT = "[data-rx-dialog-root]";

/**
 * @typedef {{ open?: (open: boolean) => void, openAutoFocus?: () => void, closeAutoFocus?: () => void, escape?: () => void, outside?: () => void, interact?: () => void }} Handlers
 */

/** @type {WeakMap<HTMLDialogElement, { on?: Handlers, bound: boolean }>} */
const dialogs = new WeakMap();

/**
 * Show on what opens a dialog whether it is open.
 *
 * @param {HTMLDialogElement} dialog The dialog.
 * @param {boolean} open Whether it is open.
 * @returns {void}
 */
function mark(dialog, open) {
  const root = dialog.closest(ROOT);
  for (const trigger of root?.querySelectorAll("[data-rx-dialog-trigger]") ??
    []) {
    if (trigger.closest(ROOT) !== root) continue;
    trigger.setAttribute("aria-expanded", String(open));
    trigger.setAttribute("data-state", open ? "open" : "closed");
  }
}

/**
 * Open a dialog over the page.
 *
 * @param {HTMLDialogElement} dialog The dialog.
 * @returns {void}
 */
function show(dialog) {
  dialog.showModal();
  // The browser scrolls to what it gives the focus: a tall dialog starts
  // at its top, as in Radix.
  dialog.scrollTop = 0;
  // An alert dialog starts on what cancels it, wherever that is in it.
  /** @type {HTMLElement | null} */ (
    dialog.querySelector("[data-rx-dialog-close=cancel]")
  )?.focus({ preventScroll: true });
  mark(dialog, true);
  dialogs.get(dialog)?.on?.openAutoFocus?.();
}

/**
 * Open or close a dialog as its user asks: a dialog bound to state says so
 * to its state instead, and shows what the state then holds.
 *
 * @param {HTMLDialogElement} dialog The dialog.
 * @param {boolean} open Whether to open it.
 * @param {...("escape" | "outside" | "interact")} why What dismissed it.
 * @returns {void}
 */
function ask(dialog, open, ...why) {
  const { on, bound } = dialogs.get(dialog) ?? {};
  for (const name of why) on?.[name]?.();
  if (bound || open) on?.open?.(open);
  if (bound) return;
  if (open) show(dialog);
  else dialog.close();
}

/**
 * Keep a dialog as its state says: the `ref` of the dialog, called again
 * whenever the page renders.
 *
 * @param {HTMLDialogElement | null} dialog The dialog.
 * @param {boolean | null} [open] Whether a dialog bound to state is open.
 * @param {Handlers | null} [on] What the dialog does when it opens, closes
 *   or is dismissed.
 * @returns {void}
 */
export function dialogSync(dialog, open, on) {
  if (!dialog) return;
  const first = !dialogs.has(dialog);
  dialogs.set(dialog, { on: on ?? undefined, bound: open != null });
  const wanted =
    open ?? (first && dialog.dataset.defaultOpen === "true" ? true : null);
  if (wanted === null || wanted === dialog.open) return;
  if (wanted) show(dialog);
  else dialog.close();
}

/**
 * Follow a press on what opens a dialog, on what closes it and beside its
 * panel: the `onClick` of the element around the dialog.
 *
 * @param {{ target: EventTarget | null, currentTarget: Element, preventDefault: () => void }} event
 *   The press.
 * @returns {void}
 */
export function dialogClick(event) {
  const root = event.currentTarget;
  const dialog = root.querySelector("dialog");
  const { target } = event;
  if (!dialog || !(target instanceof Element)) return;
  const part = target.closest(
    "[data-rx-dialog-trigger], [data-rx-dialog-close]",
  );
  if (part?.closest(ROOT) === root) {
    // The script does what the command of a button asks the browser for.
    event.preventDefault();
    ask(dialog, part.hasAttribute("data-rx-dialog-trigger"));
  } else if (
    (target === dialog || target.parentElement === dialog) &&
    dialog.role !== "alertdialog"
  )
    ask(dialog, false, "outside", "interact");
}

/**
 * Follow a dialog that is asked to close and one that has closed: the
 * `onCancel` and the `onClose` of the dialog.
 *
 * Escape asks, as a press beside the panel does. Once closed, by whatever
 * closed it, the dialog says so.
 *
 * @param {{ type: string, target: EventTarget | null, currentTarget: HTMLDialogElement, preventDefault: () => void }} event
 *   The request or the closing.
 * @returns {void}
 */
export function dialogEvent(event) {
  const dialog = event.currentTarget;
  // React hands a dialog the events of the dialogs inside it too.
  if (event.target !== dialog) return;
  if (event.type === "cancel") {
    event.preventDefault();
    ask(dialog, false, "escape");
    return;
  }
  const { on, bound } = dialogs.get(dialog) ?? {};
  mark(dialog, false);
  if (!bound) on?.open?.(false);
  on?.closeAutoFocus?.();
}
