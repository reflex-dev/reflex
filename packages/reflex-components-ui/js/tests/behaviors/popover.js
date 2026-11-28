// What jsdom has of a popover: nothing. This gives an element the methods
// the scripts call and the pseudo-class they ask for, and the toggle event
// the browser sends, sent at once.

/** @type {WeakSet<Element>} */
const open = new WeakSet();

const matches = Element.prototype.matches;

/**
 * Give every element the popover methods, as a browser has them.
 *
 * @returns {void}
 */
export function installPopover() {
  Element.prototype.matches = function (/** @type {string} */ selector) {
    return selector === ":popover-open"
      ? open.has(this)
      : matches.call(this, selector);
  };
  HTMLElement.prototype.togglePopover = function (
    /** @type {unknown} */ force,
  ) {
    const next = typeof force === "boolean" ? force : !open.has(this);
    if (next === open.has(this)) return next;
    if (next) open.add(this);
    else open.delete(this);
    const event = new Event("toggle");
    Object.assign(event, { newState: next ? "open" : "closed" });
    this.dispatchEvent(event);
    return next;
  };
  HTMLElement.prototype.showPopover = function () {
    this.togglePopover(true);
  };
  HTMLElement.prototype.hidePopover = function () {
    this.togglePopover(false);
  };
}
