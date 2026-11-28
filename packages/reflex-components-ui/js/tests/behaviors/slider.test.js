// What a slider draws of its range inputs: the filled part of its track,
// the order of several thumbs, and the thumb a pointer on the track moves.
import { beforeEach, expect, test } from "vitest";

import { press, slide } from "$/reflex-ui/behaviors/slider.js";

/**
 * Build a slider.
 *
 * @param {number[]} values The value of each thumb.
 * @param {string} [attributes] Further attributes of each input.
 * @returns {HTMLElement} The slider.
 */
function slider(values, attributes = "") {
  document.body.innerHTML = `<span id="slider">${values
    .map((value) => `<input type="range" value="${value}" ${attributes} />`)
    .join("")}</span>`;
  const element = /** @type {HTMLElement} */ (
    document.getElementById("slider")
  );
  // jsdom lays nothing out: the track is 200 pixels long, from 100.
  element.getBoundingClientRect = () =>
    /** @type {DOMRect} */ ({
      left: 100,
      width: 200,
      bottom: 300,
      height: 200,
    });
  return element;
}

/**
 * Read where the filled part of the track of a slider starts and ends.
 *
 * @param {HTMLElement} element The slider.
 * @returns {string[]} The two custom properties.
 */
function filled(element) {
  return ["--rx-slider-start", "--rx-slider-end"].map((name) =>
    element.style.getPropertyValue(name),
  );
}

/**
 * Read the values of the thumbs of a slider.
 *
 * @param {HTMLElement} element The slider.
 * @returns {number[]} The value of each thumb.
 */
function values(element) {
  return [...element.querySelectorAll("input")].map(
    (input) => input.valueAsNumber,
  );
}

/**
 * Move a thumb as a user does.
 *
 * @param {HTMLElement} element The slider.
 * @param {number} index Which thumb.
 * @param {number} value Where to.
 * @returns {void}
 */
function move(element, index, value) {
  const input = element.querySelectorAll("input")[index];
  input.value = String(value);
  slide({ target: input, currentTarget: element });
}

/**
 * Put the pointer down on the track of a slider.
 *
 * @param {HTMLElement} element The slider.
 * @param {{ clientX?: number, clientY?: number, target?: EventTarget }} at Where.
 * @returns {boolean} Whether the slider kept the pointer from the browser.
 */
function pointer(element, at) {
  let prevented = false;
  press({
    target: element,
    currentTarget: element,
    clientX: 0,
    clientY: 0,
    preventDefault: () => {
      prevented = true;
    },
    ...at,
  });
  return prevented;
}

beforeEach(() => {
  document.body.innerHTML = "";
});

test("the track is filled from its start to the only thumb", () => {
  const element = slider([30]);
  move(element, 0, 45);
  expect(filled(element)).toEqual(["0%", "45%"]);
});

test("the share of the track follows the range of the slider", () => {
  const element = slider([20], 'min="10" max="50"');
  move(element, 0, 30);
  expect(filled(element)).toEqual(["0%", "50%"]);
  const flat = slider([5], 'min="5" max="5"');
  move(flat, 0, 5);
  expect(filled(flat)).toEqual(["0%", "0%"]);
});

test("with several thumbs the track is filled from the first to the last", () => {
  const element = slider([20, 60, 90]);
  move(element, 1, 70);
  expect(filled(element)).toEqual(["20%", "90%"]);
  move(element, 0, 10);
  expect(filled(element)).toEqual(["10%", "90%"]);
});

test("a thumb stops at the thumbs beside it", () => {
  const element = slider([20, 60, 90]);
  move(element, 0, 75);
  expect(values(element)).toEqual([60, 60, 90]);
  move(element, 2, 10);
  expect(values(element)).toEqual([60, 60, 60]);
  move(element, 1, 100);
  expect(values(element)).toEqual([60, 60, 60]);
  expect(filled(element)).toEqual(["60%", "60%"]);
});

test("what is no thumb of the slider moves nothing", () => {
  const element = slider([20, 60]);
  slide({ target: document.body, currentTarget: element });
  expect(filled(element)).toEqual(["", ""]);
});

test("a pointer on the track moves the nearest thumb there and gives it the focus", () => {
  const element = slider([20, 60]);
  /** @type {number[][]} */
  const heard = [];
  element.addEventListener("input", () => heard.push(values(element)));
  expect(pointer(element, { clientX: 250 })).toBe(true);
  expect(values(element)).toEqual([20, 75]);
  expect(document.activeElement).toBe(element.querySelectorAll("input")[1]);
  expect(pointer(element, { clientX: 110 })).toBe(true);
  expect(values(element)).toEqual([5, 75]);
  expect(heard).toEqual([
    [20, 75],
    [5, 75],
  ]);
});

test("a pointer past the ends of the track goes to its ends, by the step", () => {
  const element = slider([2, 6], 'min="0" max="10" step="4"');
  pointer(element, { clientX: 1000 });
  expect(values(element)).toEqual([2, 10]);
  const stepped = slider([0, 8], 'min="0" max="10" step="4"');
  pointer(stepped, { clientX: 100 + 200 * 0.45 });
  expect(values(stepped)).toEqual([4, 8]);
  pointer(stepped, { clientX: -50 });
  expect(values(stepped)).toEqual([0, 8]);
});

test("a vertical slider is read from the bottom up", () => {
  const element = slider([20, 60]);
  element.dataset.orientation = "vertical";
  pointer(element, { clientY: 300 - 200 * 0.9 });
  expect(values(element)).toEqual([20, 90]);
});

test("one thumb, a thumb under the pointer and a disabled slider are left to the browser", () => {
  const one = slider([20]);
  expect(pointer(one, { clientX: 250 })).toBe(false);
  expect(values(one)).toEqual([20]);
  const two = slider([20, 60]);
  expect(
    pointer(two, { clientX: 250, target: two.querySelector("input") ?? two }),
  ).toBe(false);
  const off = slider([20, 60], "disabled");
  expect(pointer(off, { clientX: 250 })).toBe(false);
  expect(values(off)).toEqual([20, 60]);
});
