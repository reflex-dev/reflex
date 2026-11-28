// What an accordion does that the browser leaves to a script.
//
// An item is a native `details`: the browser opens and closes it with a
// press, Enter and Space, and closes the others of its name. Left for a
// script: an open item that stays open when it is pressed, as in Radix
// unless the accordion is collapsible, saying which items are open, and an
// accordion bound to state, which shows what its state holds. Without this
// every item opens and closes.

/**
 * Follow a press on the header of an item: the `onClick` of the element
 * around an accordion.
 *
 * @param {{ target: EventTarget | null, currentTarget: HTMLElement, preventDefault: () => void }} event
 *   The press, before the browser opens or closes the item.
 * @param {(value: string | string[]) => void} [onValueChange] What the
 *   accordion does when its open items change.
 * @returns {void}
 */
export function accordionClick(event, onValueChange) {
  const root = event.currentTarget;
  const item =
    event.target instanceof Element
      ? event.target.closest("summary")?.parentElement
      : null;
  if (!(item instanceof HTMLDetailsElement) || item.parentElement !== root)
    return;
  const { rxAccordion, collapsible, bound } = root.dataset;
  const single = rxAccordion === "single";
  if (single && item.open && collapsible !== "true") {
    event.preventDefault();
    return;
  }
  if (bound !== undefined) event.preventDefault();
  if (!onValueChange) return;
  const value = item.dataset.value ?? "";
  onValueChange(
    single
      ? item.open
        ? ""
        : value
      : /** @type {HTMLDetailsElement[]} */ ([...root.children])
          .filter((other) => other.open !== (other === item))
          .map((other) => other.dataset.value ?? ""),
  );
}
