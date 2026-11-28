// What a pointer on the box of a text field does when it is not on the
// input: on a slot that holds an icon, or on the edge of the box.
//
// Without it the input still takes the focus from a pointer on the input
// itself, from the keyboard and from its label.

/**
 * Give the input of a text field the focus: the `onPointerDown` of its box.
 *
 * The caret goes to the end of the value from a slot on the right and to
 * its start from anywhere else. A button or a link in a slot keeps the
 * pointer for itself.
 *
 * @param {{ target: EventTarget | null, currentTarget: Element }} event The
 *   pointer going down inside the box.
 * @returns {void}
 */
export function focusField(event) {
  const target = event.target;
  if (!(target instanceof Element) || target.closest("input, button, a"))
    return;
  const input = event.currentTarget.querySelector("input");
  if (!input) return;
  const caret = target.closest("[data-side='right']") ? input.value.length : 0;
  requestAnimationFrame(() => {
    try {
      // An input without text, such as a date, has no caret to place.
      input.setSelectionRange(caret, caret);
    } catch {
      // The focus is all it takes then.
    }
    input.focus();
  });
}
