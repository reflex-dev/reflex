// The arrow keys of a group that is one stop for Tab: they move the focus
// between its items, as in Radix, without choosing one.
//
// The items are native controls, which the browser moves between with the
// arrow keys by itself: choosing each one it passes, for radio buttons.
// Without this the group works that way.

const STEPS = /** @type {Record<string, number>} */ ({
  ArrowLeft: -1,
  ArrowUp: -1,
  ArrowRight: 1,
  ArrowDown: 1,
});

/**
 * Move the focus through the items of a group: the `onKeyDown` of the group.
 *
 * The arrow keys go to the item before and after, around the ends, Home and
 * End to the first and the last, and Enter chooses the item the focus is on,
 * as Space does by itself. The direction of the text turns left and right.
 *
 * @param {{ key: string, target: EventTarget | null, currentTarget: Element, preventDefault: () => void, altKey?: boolean, ctrlKey?: boolean, metaKey?: boolean, shiftKey?: boolean }} event
 *   The key going down on an item.
 * @returns {void}
 */
export function rovingKeyDown(event) {
  const { key, target, currentTarget } = event;
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  if (!(target instanceof HTMLInputElement) || target.type !== "radio") return;
  if (key === "Enter") {
    event.preventDefault();
    target.click();
    return;
  }
  const items = /** @type {HTMLInputElement[]} */ ([
    ...currentTarget.querySelectorAll("input[type=radio]:not(:disabled)"),
  ]);
  const last = items.length - 1;
  let index = items.indexOf(target);
  if (key === "Home") index = 0;
  else if (key === "End") index = last;
  else if (key in STEPS) {
    const flipped =
      key !== "ArrowUp" &&
      key !== "ArrowDown" &&
      getComputedStyle(currentTarget).direction === "rtl";
    index += flipped ? -STEPS[key] : STEPS[key];
    index = index < 0 ? last : index > last ? 0 : index;
  } else return;
  event.preventDefault();
  items[index]?.focus();
}
