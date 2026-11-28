// Where a popup goes in a browser without CSS anchor positioning: loaded on
// demand, only there.
//
// The popup is placed below what opens it, at its start, at least as wide,
// and above it where there is more room and it would leave the viewport.

/** @type {WeakMap<Element, () => void>} */
const following = new WeakMap();

/** The room kept between a popup and the edge of the viewport, in pixels. */
const EDGE = 10;

/**
 * Place a popup beside its anchor, and keep it there while it is open.
 *
 * @param {HTMLElement} popup The popover.
 * @param {Element} anchor What opens it.
 * @param {boolean} open Whether the popup is open.
 * @returns {void}
 */
export function place(popup, anchor, open) {
  following.get(popup)?.();
  following.delete(popup);
  if (!open) return;
  const gap = Number.parseFloat(getComputedStyle(popup).marginTop) || 0;
  const update = () => {
    const box = anchor.getBoundingClientRect();
    const below = innerHeight - box.bottom - gap - EDGE;
    const above = box.top - gap - EDGE;
    const height = popup.offsetHeight;
    const over = height > below && above > below;
    const style = popup.style;
    style.position = "fixed";
    style.inset = "auto";
    style.minWidth = `${box.width}px`;
    style.maxHeight = `${Math.max(over ? above : below, 0)}px`;
    style.left = `${Math.max(Math.min(box.left, innerWidth - popup.offsetWidth - EDGE), EDGE)}px`;
    style.top = over
      ? `${box.top - Math.min(height, above) - gap * 2}px`
      : `${box.bottom}px`;
  };
  update();
  addEventListener("scroll", update, true);
  addEventListener("resize", update);
  following.set(popup, () => {
    removeEventListener("scroll", update, true);
    removeEventListener("resize", update);
  });
}
