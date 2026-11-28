// The arrow keys of a group that is one stop for Tab: they move the focus
// between its items, as in Radix, without choosing one.
//
// The items are the native radio buttons of a group, which the browser
// moves between with the arrow keys by itself, choosing each one it passes:
// without this the group works that way. Or they are the triggers of tabs,
// which are buttons the browser does not move between.

const RADIO = "input[type=radio]";

/**
 * Move the focus through the items of a group: the `onKeyDown` of the group.
 *
 * The arrow keys go to the item before and after, around the ends unless
 * the group says `data-loop="false"`, Home and End to the first and the
 * last, and Enter chooses the radio button the focus is on, as Space does
 * by itself. The direction of the text turns left and right, and a group
 * with an `aria-orientation` only hears the arrow keys along it.
 *
 * @param {{ key: string, target: EventTarget | null, currentTarget: HTMLElement, preventDefault: () => void, altKey?: boolean, ctrlKey?: boolean, metaKey?: boolean, shiftKey?: boolean }} event
 *   The key going down on an item.
 * @returns {void}
 */
export function rovingKeyDown(event) {
  const { key, target, currentTarget } = event;
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  if (!(target instanceof HTMLElement)) return;
  const item = [RADIO, "[role=tab]"].find((kind) => target.matches(kind));
  if (!item) return;
  if (key === "Enter") {
    if (item === RADIO) {
      event.preventDefault();
      target.click();
    }
    return;
  }
  const items = /** @type {HTMLElement[]} */ ([
    ...currentTarget.querySelectorAll(`${item}:not(:disabled)`),
  ]);
  const count = items.length;
  let index = items.indexOf(target);
  if (key === "Home") index = 0;
  else if (key === "End") index = count - 1;
  else if (key.startsWith("Arrow")) {
    const across = /Up|Down/.test(key);
    const orientation = currentTarget.ariaOrientation;
    if (orientation && across === (orientation === "horizontal")) return;
    const back =
      /Up|Left/.test(key) !==
      (!across && getComputedStyle(currentTarget).direction === "rtl");
    index += back ? -1 : 1;
    index =
      currentTarget.dataset.loop === "false"
        ? Math.max(0, Math.min(index, count - 1))
        : (index + count) % count;
  } else return;
  event.preventDefault();
  items[index]?.focus();
}
