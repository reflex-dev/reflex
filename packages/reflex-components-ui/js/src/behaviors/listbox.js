// What a select does that the browser leaves to a script: the keys that
// move through its options, typing to find one, and the value it keeps.
//
// The list is a popup the browser opens, closes and places. The value is
// the one of a text input no one sees, so a form submits it, a required
// select holds its form back, and React hears of a change as it does of
// any input. Without this the select opens and closes, and chooses nothing.

import { opener, pair, popupToggle } from "./popup.js";

const OPTION = "[role=option]";
const ENABLED = `${OPTION}:not([aria-disabled=true])`;

/** What was typed to find an option, and when it is forgotten. */
let typed = "";
let forgetting = 0;

/**
 * Find the parts of a select.
 *
 * @param {Element} select The element around the select.
 * @returns {{ trigger: HTMLElement | null, popup: HTMLElement | null, holder: HTMLInputElement | null }}
 *   What opens the list, the list, and the input that holds the value.
 */
function parts(select) {
  return {
    trigger: select.querySelector("[role=combobox]"),
    popup: select.querySelector("[popover]"),
    holder: select.querySelector("input[data-rx-select-value]"),
  };
}

/**
 * Read the text an option shows.
 *
 * @param {Element} option The option.
 * @returns {string} Its text, without what marks it as chosen.
 */
function textOf(option) {
  return (option.querySelector("[data-rx-select-text]") ?? option).textContent ?? "";
}

/**
 * Show the value of a select on its options and on what opens it: the
 * `ref` of the input that holds the value, called again whenever the page
 * renders.
 *
 * The chosen option says so, and its text is the text of the trigger, or
 * the placeholder when nothing is chosen. A select bound to state takes its
 * value, and whether it is open, from there.
 *
 * @param {Element | null} holder The input that holds the value.
 * @param {string | null} [value] The value of a select bound to state.
 * @param {boolean | null} [open] Whether a select bound to state is open.
 * @returns {void}
 */
export function syncSelect(holder, value, open) {
  const select = /** @type {HTMLElement | null | undefined} */ (holder?.closest("[data-rx-select]"));
  if (!select) return;
  const { trigger, popup } = parts(select);
  if (!trigger || !popup || !(holder instanceof HTMLInputElement)) return;
  pair(popup, trigger);
  if (value !== undefined && value !== null) {
    // What the select goes back to when a choice changes nothing in state.
    select.dataset.rxValue = value;
    if (holder.value !== value) holder.value = value;
  }
  show(select, trigger, holder.value);
  const starts = select.getAttribute("data-default-open") === "true";
  select.removeAttribute("data-default-open");
  const wanted = open ?? (starts ? true : null);
  if (wanted !== null && wanted !== popup.matches(":popover-open")) {
    popup.dataset.rxClosedBy = "state";
    popup.togglePopover(wanted);
  }
}

/**
 * Show a value on the options of a select and on what opens it.
 *
 * @param {Element} select The element around the select.
 * @param {Element} trigger What opens the list.
 * @param {string} current The value.
 * @returns {void}
 */
function show(select, trigger, current) {
  let chosen = null;
  for (const option of select.querySelectorAll(OPTION)) {
    const on = current !== "" && option.getAttribute("data-value") === current;
    option.setAttribute("aria-selected", String(on));
    option.setAttribute("data-state", on ? "checked" : "unchecked");
    if (on) chosen ??= option;
  }
  const shown = trigger.querySelector("[data-rx-select-shown]");
  if (shown instanceof HTMLElement) {
    const text = chosen ? textOf(chosen) : (shown.dataset.placeholder ?? "");
    // The node React rendered keeps its place: React may write to it again.
    if (shown.firstChild) shown.firstChild.nodeValue = text;
    else shown.textContent = text;
    trigger.toggleAttribute("data-placeholder", !chosen);
  }
}

/**
 * Choose an option: the list closes, and the value changes if it differs.
 *
 * @param {Element} select The element around the select.
 * @param {Element} option The option.
 * @returns {void}
 */
function choose(select, option) {
  const { trigger, popup, holder } = parts(select);
  const value = option.getAttribute("data-value") ?? "";
  if (popup?.matches(":popover-open")) {
    popup.dataset.rxClosedBy = "choice";
    popup.hidePopover();
  }
  if (!trigger || !holder || holder.value === value) return;
  const setter = /** @type {(this: HTMLInputElement, value: string) => void} */ (
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set
  );
  setter.call(holder, value);
  // As a user types it, so that React hears of it.
  holder.dispatchEvent(new Event("input", { bubbles: true }));
  // A select bound to state shows the value of the state, which follows or
  // does not.
  const bound = /** @type {HTMLElement} */ (select).dataset.rxValue;
  if (bound !== undefined) holder.value = bound;
  show(select, trigger, holder.value);
}

/**
 * Find the option that what was typed leads to.
 *
 * Typing one letter again goes through the options that start with it.
 *
 * @param {HTMLElement[]} options The options that can be chosen.
 * @param {string} key The letter typed.
 * @param {Element | null} from The option to start after.
 * @returns {HTMLElement | undefined} The option found.
 */
function find(options, key, from) {
  clearTimeout(forgetting);
  typed += key.toLowerCase();
  forgetting = Number(setTimeout(() => (typed = ""), 1000));
  const repeated = [...typed].every((letter) => letter === typed[0]);
  const search = repeated ? typed[0] : typed;
  const start = options.indexOf(/** @type {HTMLElement} */ (from));
  const order = [...options.slice(start + 1), ...options.slice(0, start + 1)];
  if (!repeated && from && textOf(from).trim().toLowerCase().startsWith(search)) {
    return /** @type {HTMLElement} */ (from);
  }
  return order.find((option) => textOf(option).trim().toLowerCase().startsWith(search));
}

/**
 * The keys of a select: the `onKeyDown` of the element around it.
 *
 * On the trigger the arrow keys open the list, and a letter chooses the
 * next option that starts with what is typed. In the list the arrow keys,
 * Home and End move through the options, a letter goes to one, Enter and
 * Space choose, and Tab stays.
 *
 * @param {{ key: string, target: EventTarget | null, currentTarget: Element, preventDefault: () => void, altKey?: boolean, ctrlKey?: boolean, metaKey?: boolean }} event
 *   The key going down inside the select.
 * @returns {void}
 */
export function selectKeyDown(event) {
  const select = event.currentTarget;
  const { trigger, popup, holder } = parts(select);
  if (!trigger || !popup || !holder) return;
  const { key } = event;
  if (key === "Escape") popup.dataset.rxClosedBy = "escape";
  const options = /** @type {HTMLElement[]} */ ([...select.querySelectorAll(ENABLED)]);
  const letter = key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey;
  if (!popup.matches(":popover-open")) {
    if (event.target !== trigger || trigger.matches(":disabled")) return;
    if (key === "ArrowDown" || key === "ArrowUp") {
      event.preventDefault();
      trigger.click();
    } else if (letter && (key !== " " || typed)) {
      event.preventDefault();
      const current = options.find((option) => option.dataset.value === holder.value);
      const found = find(options, key, current ?? null);
      if (found) choose(select, found);
    }
    return;
  }
  const at = options.indexOf(/** @type {HTMLElement} */ (document.activeElement));
  /** @type {HTMLElement | undefined} */
  let next;
  if (key === "ArrowDown") next = options[Math.min(at + 1, options.length - 1)];
  else if (key === "ArrowUp") next = options[Math.max(at - 1, 0)];
  else if (key === "Home") next = options[0];
  else if (key === "End") next = options[options.length - 1];
  else if (key === "Enter" || (key === " " && !typed)) {
    event.preventDefault();
    if (at >= 0) choose(select, options[at]);
    return;
  } else if (key === "Tab") {
    event.preventDefault();
    return;
  } else if (letter) next = find(options, key, options[at] ?? null);
  else return;
  event.preventDefault();
  next?.focus();
}

/**
 * Choose the option under the pointer: the `onClick` of the element around
 * a select.
 *
 * @param {{ target: EventTarget | null, currentTarget: Element }} event The click.
 * @returns {void}
 */
export function selectClick(event) {
  const option = event.target instanceof Element ? event.target.closest(ENABLED) : null;
  if (option) choose(event.currentTarget, option);
}

/**
 * Give the option under the pointer the focus, which is what marks it: the
 * `onPointerMove` of the element around a select.
 *
 * @param {{ target: EventTarget | null, currentTarget: Element }} event The pointer moving.
 * @returns {void}
 */
export function selectPointerMove(event) {
  const target = event.target instanceof Element ? event.target : null;
  const option = target?.closest(ENABLED);
  if (option instanceof HTMLElement) {
    if (option !== document.activeElement) option.focus({ preventScroll: true });
  } else if (target?.closest("[popover]")) {
    parts(event.currentTarget).popup?.focus({ preventScroll: true });
  }
}

/**
 * Follow the list of a select that opens or closes: the `onToggle` of its
 * popover.
 *
 * The chosen option takes the focus when the list opens, or the first one,
 * and the trigger has it back when the list closes.
 *
 * @param {{ currentTarget: HTMLElement, newState?: string }} event The toggle.
 * @param {{ open?: (open: boolean) => void, close?: () => void, escape?: () => void, outside?: () => void }} [on]
 *   What the select does when its list opens or closes, when it has closed,
 *   and when Escape or a pointer outside the list closed it.
 * @returns {void}
 */
export function selectToggle(event, on) {
  const popup = event.currentTarget;
  const open = popupToggle(event);
  const by = popup.dataset.rxClosedBy;
  delete popup.dataset.rxClosedBy;
  typed = "";
  on?.open?.(open);
  if (open) {
    const options = /** @type {HTMLElement[]} */ ([...popup.querySelectorAll(ENABLED)]);
    (options.find((option) => option.getAttribute("aria-selected") === "true") ?? options[0] ?? popup).focus();
    return;
  }
  if (popup.contains(document.activeElement)) /** @type {HTMLElement | null} */ (opener(popup))?.focus();
  if (by === "escape") on?.escape?.();
  else if (!by) on?.outside?.();
  on?.close?.();
}

/**
 * Hand the focus the input of the value is given to the trigger: the
 * `onFocus` of the input, which a form gives the focus when it is required
 * and empty.
 *
 * @param {{ currentTarget: Element }} event The focus.
 * @returns {void}
 */
export function selectFocus(event) {
  const select = event.currentTarget.closest("[data-rx-select]");
  if (select) parts(select).trigger?.focus();
}
