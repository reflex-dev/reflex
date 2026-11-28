// What a slider draws of the values of its native range inputs: the part
// of its track between them, and for a slider with several thumbs the order
// they keep and the thumb a pointer on the track moves.
//
// The thumbs are the ones of the inputs, which the browser moves, reads to
// the accessibility tree and submits with a form by itself. Without this
// the filled part of the track stays where the server drew it.

/**
 * Find the inputs of a slider.
 *
 * @param {Element} slider The slider.
 * @returns {HTMLInputElement[]} Its range inputs, in the order of its thumbs.
 */
function thumbs(slider) {
  return /** @type {HTMLInputElement[]} */ ([
    ...slider.querySelectorAll("input"),
  ]);
}

/**
 * Say how far along its track the value of an input is.
 *
 * @param {HTMLInputElement} input A range input.
 * @returns {string} The share of the track, as a percentage.
 */
function share(input) {
  const min = Number(input.min || 0);
  const max = Number(input.max || 100);
  return `${max > min ? ((input.valueAsNumber - min) / (max - min)) * 100 : 0}%`;
}

/**
 * Give an input a value as a user does, so that React hears of it.
 *
 * @param {HTMLInputElement} input The input.
 * @param {number} value The value.
 * @returns {void}
 */
function assign(input, value) {
  const setter =
    /** @type {(this: HTMLInputElement, value: string) => void} */ (
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set
    );
  setter.call(input, String(value));
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

/**
 * Follow a thumb that moves: the `onInput` of a slider.
 *
 * A thumb stops at the ones beside it, and the filled part of the track is
 * drawn from the first thumb to the last, or from the start of the track to
 * the only one.
 *
 * @param {{ target: EventTarget | null, currentTarget: HTMLElement }} event
 *   The input of one of the thumbs.
 * @returns {void}
 */
export function slide(event) {
  const slider = event.currentTarget;
  const inputs = thumbs(slider);
  const index = inputs.indexOf(/** @type {HTMLInputElement} */ (event.target));
  if (index < 0) return;
  const moved = inputs[index];
  const low = inputs[index - 1]?.valueAsNumber ?? -Infinity;
  const high = inputs[index + 1]?.valueAsNumber ?? Infinity;
  const kept = Math.min(Math.max(moved.valueAsNumber, low), high);
  if (kept !== moved.valueAsNumber) moved.value = String(kept);
  slider.style.setProperty(
    "--rx-slider-start",
    inputs.length > 1 ? share(inputs[0]) : "0%",
  );
  slider.style.setProperty("--rx-slider-end", share(inputs[inputs.length - 1]));
}

/**
 * Move the nearest thumb of a slider with several to a pointer on its
 * track: the `onMouseDown` of such a slider.
 *
 * The browser does it for a slider with one thumb. With several, each
 * input lets the pointer through to the ones below it, but for its thumb.
 * The thumb that moves takes the focus, which the pointer leaves it.
 *
 * @param {{ target: EventTarget | null, currentTarget: HTMLElement, clientX: number, clientY: number, preventDefault: () => void }} event
 *   The pointer going down on the slider.
 * @returns {void}
 */
export function press(event) {
  const slider = event.currentTarget;
  const inputs = thumbs(slider);
  const first = inputs[0];
  if (
    inputs.length < 2 ||
    event.target instanceof HTMLInputElement ||
    first.disabled
  )
    return;
  const box = slider.getBoundingClientRect();
  const vertical = slider.dataset.orientation === "vertical";
  const along = vertical
    ? (box.bottom - event.clientY) / box.height
    : (event.clientX - box.left) / box.width;
  const min = Number(first.min || 0);
  const max = Number(first.max || 100);
  const step = Number(first.step || 1);
  const reached = min + Math.min(Math.max(along, 0), 1) * (max - min);
  const value = Math.min(max, min + Math.round((reached - min) / step) * step);
  let nearest = first;
  for (const input of inputs) {
    if (
      Math.abs(input.valueAsNumber - value) <
      Math.abs(nearest.valueAsNumber - value)
    ) {
      nearest = input;
    }
  }
  event.preventDefault();
  nearest.focus();
  assign(nearest, value);
}
