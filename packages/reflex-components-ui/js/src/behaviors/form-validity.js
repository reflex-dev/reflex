// What the messages of a form show of the validity of its controls.
//
// The browser knows why a control is not valid: nothing typed, a pattern
// that does not match, a number out of its range. A message names one of
// those reasons and is hidden until it holds, as Radix has it: reasons are
// read when a form is submitted or a control is left after a change, and
// forgotten while its value changes.
//
// Without it the browser reports an invalid control itself, as it does for
// any form.

/**
 * @typedef {HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement} Control
 */

let ids = 0;

/**
 * Tell the element of an event apart from anything that is no form control.
 *
 * @param {EventTarget | null} target The target of an event.
 * @returns {Control | null} The control, or null.
 */
function controlOf(target) {
  return target instanceof HTMLInputElement ||
    target instanceof HTMLSelectElement ||
    target instanceof HTMLTextAreaElement
    ? target
    : null;
}

/**
 * Show the messages of a control whose reason holds, and hide the others.
 *
 * The field of the control, its labels and the control say whether it is
 * valid in `data-valid` and `data-invalid`, and the control is described by
 * the messages that show.
 *
 * @param {Element} form The form.
 * @param {Control} control The control.
 * @param {boolean} known Whether the validity of the control is read, or
 *   forgotten.
 * @returns {void}
 */
function report(form, control, known) {
  const field = control.closest("[data-rx-form-field]");
  const validity = control.validity;
  const invalid = known && !validity.valid;
  const marked = [control, ...(field ? [field, ...field.querySelectorAll("label")] : [])];
  for (const element of marked) {
    if (element !== field || !field.hasAttribute("data-server-invalid")) {
      element.toggleAttribute("data-invalid", invalid);
    }
    element.toggleAttribute("data-valid", known && validity.valid);
  }
  const shown = [];
  for (const message of form.querySelectorAll("[data-rx-form-message]")) {
    if (!(message instanceof HTMLElement)) continue;
    const name = message.dataset.name;
    const own = name ? name === control.name : field !== null && field.contains(message);
    if (!own) continue;
    const match = message.dataset.match;
    if (match && !("force" in message.dataset)) {
      message.hidden = !(known && /** @type {Record<string, any>} */ (validity)[match]);
    }
    if (!message.hidden) {
      message.id ||= `rx-form-message-${++ids}`;
      shown.push(message.id);
    }
  }
  if (shown.length) control.setAttribute("aria-describedby", shown.join(" "));
  else control.removeAttribute("aria-describedby");
}

/**
 * Read the validity of a control the browser found invalid: the `onInvalid`
 * of a form.
 *
 * The messages stand in for the report of the browser, and the first
 * invalid control of the form takes the focus.
 *
 * @param {{ target: EventTarget | null, currentTarget: HTMLFormElement, preventDefault: () => void }} event
 *   The control found invalid.
 * @returns {void}
 */
export function invalid(event) {
  const control = controlOf(event.target);
  if (!control) return;
  const form = event.currentTarget;
  if (form.querySelector(":invalid") === control) control.focus();
  event.preventDefault();
  report(form, control, true);
}

/**
 * Forget the validity of a control whose value changes: the
 * `onChangeCapture` of a form.
 *
 * @param {{ target: EventTarget | null, currentTarget: HTMLFormElement }} event
 *   The change.
 * @returns {void}
 */
export function changed(event) {
  const control = controlOf(event.target);
  if (!control) return;
  control.dataset.rxChanged = "";
  report(event.currentTarget, control, false);
}

/**
 * Read the validity of a control that is left after a change: the
 * `onBlurCapture` of a form.
 *
 * @param {{ target: EventTarget | null, currentTarget: HTMLFormElement }} event
 *   The control losing the focus.
 * @returns {void}
 */
export function left(event) {
  const control = controlOf(event.target);
  if (!control || !("rxChanged" in control.dataset)) return;
  delete control.dataset.rxChanged;
  report(event.currentTarget, control, true);
}

/**
 * Forget the validity of every control of a form that is reset: its
 * `onReset`.
 *
 * @param {{ currentTarget: HTMLFormElement }} event The reset.
 * @returns {void}
 */
export function cleared(event) {
  const form = event.currentTarget;
  for (const element of form.elements) {
    const control = controlOf(element);
    if (control) {
      delete control.dataset.rxChanged;
      report(form, control, false);
    }
  }
}

/**
 * Give the focus to the first control of a form that is not valid, when
 * the server finds a field invalid: the `ref` of the field while it is.
 *
 * It is the first one of the whole form, as in Radix: a form with several
 * such fields, or with one the browser finds invalid too, starts at the top.
 *
 * @param {Element | null} field The field, or null when it stops being invalid.
 * @returns {void}
 */
export function focusInvalid(field) {
  const form = field?.closest("form");
  if (!form) return;
  for (const element of form.elements) {
    const control = controlOf(element);
    if (control && (control.ariaInvalid === "true" || !control.validity.valid)) {
      control.focus();
      return;
    }
  }
}
