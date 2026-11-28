// What tabs do that the browser leaves to a script: a press on a trigger,
// or the focus moving to one, selects it and shows its panel.
//
// The state is the DOM: the selected trigger says so in `aria-selected`,
// and every other panel is `hidden`. The server renders both, so without
// this the tabs show the panel they start with. The arrow keys are the
// ones of `roving-focus.js`.

/**
 * Follow a press on a trigger and the focus moving between triggers: the
 * `onClick`, the `onFocus` and the `onBlur` of the element around tabs.
 *
 * Tab stops on one trigger: the one that has the focus, and the selected
 * one once the focus has left. A trigger is selected by a press, and by the
 * focus unless the tabs are activated by hand. Tabs bound to state say so
 * to their state, and show what it holds.
 *
 * @param {{ type: string, target: EventTarget | null, currentTarget: HTMLElement, relatedTarget?: EventTarget | null }} event
 *   The press, or the focus coming or going.
 * @param {(value: string) => void} [onChange] What the tabs do when another
 *   trigger is selected.
 * @returns {void}
 */
export function tabsEvent(event, onChange) {
  const root = event.currentTarget;
  // The parts of these tabs, and not the ones of tabs inside them.
  const own = (/** @type {string} */ role) =>
    /** @type {HTMLElement[]} */ (
      [...root.querySelectorAll(`[role=${role}]`)].filter(
        (part) => part.closest("[data-rx-tabs]") === root,
      )
    );
  const tabs = own("tab");
  const inside = (/** @type {EventTarget | null | undefined} */ node) =>
    tabs.find((tab) => tab.contains(/** @type {Node | null} */ (node)));
  const target = inside(event.target);
  const left = event.type === "blur";
  if (!target || (left && inside(event.relatedTarget))) return;
  const stop = left
    ? (tabs.find((tab) => tab.ariaSelected === "true") ?? target)
    : target;
  for (const tab of tabs) tab.tabIndex = tab === stop ? 0 : -1;
  if (
    left ||
    target.ariaSelected === "true" ||
    target.matches(":disabled") ||
    (event.type === "focus" && root.dataset.activation === "manual")
  )
    return;
  const value = target.dataset.value ?? "";
  onChange?.(value);
  if (root.dataset.rxTabs) return;
  for (const part of [...tabs, ...own("tabpanel")]) {
    const on = part.dataset.value === value;
    part.dataset.state = on ? "active" : "inactive";
    if (part.role === "tab") part.ariaSelected = String(on);
    else part.hidden = !on;
  }
}
