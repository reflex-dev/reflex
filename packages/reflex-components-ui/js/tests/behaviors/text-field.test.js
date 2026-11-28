// What a pointer on the box of a text field does: the input takes the focus,
// with its caret at the end the pointer is nearest to.
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { focusField } from "$/reflex-ui/behaviors/text-field.js";

/** @type {HTMLElement} */
let box;
/** @type {HTMLInputElement} */
let input;

beforeEach(() => {
  document.body.innerHTML = `
    <div id="box">
      <input value="abcdef" />
      <div data-side="left" id="left"><svg id="icon"></svg></div>
      <div data-side="right" id="right">kg</div>
      <div data-side="right"><button id="clear">Clear</button><a id="link" href="#x">x</a></div>
    </div>
    <div id="empty"><div data-side="left" id="alone"></div></div>`;
  box = /** @type {HTMLElement} */ (document.getElementById("box"));
  input = /** @type {HTMLInputElement} */ (box.querySelector("input"));
  // The focus waits for a frame, as the pointer is still going down.
  vi.stubGlobal(
    "requestAnimationFrame",
    (/** @type {FrameRequestCallback} */ callback) => {
      callback(0);
      return 0;
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/**
 * Put the pointer down on an element of a box.
 *
 * @param {string} id The id of the element.
 * @param {Element} [currentTarget] The box, when it is not the first one.
 * @returns {void}
 */
function pointerDown(id, currentTarget = box) {
  focusField({ target: document.getElementById(id), currentTarget });
}

test("a pointer on a left slot focuses the input at the start of its text", () => {
  pointerDown("icon");
  expect(document.activeElement).toBe(input);
  expect([input.selectionStart, input.selectionEnd]).toEqual([0, 0]);
});

test("a pointer on a right slot focuses the input at the end of its text", () => {
  pointerDown("right");
  expect(document.activeElement).toBe(input);
  expect([input.selectionStart, input.selectionEnd]).toEqual([6, 6]);
});

test("a pointer on the box itself focuses the input at the start", () => {
  pointerDown("box");
  expect(document.activeElement).toBe(input);
  expect([input.selectionStart, input.selectionEnd]).toEqual([0, 0]);
});

test("a button, a link and the input keep the pointer for themselves", () => {
  input.setSelectionRange(3, 3);
  for (const id of ["clear", "link"]) {
    pointerDown(id);
    expect(document.activeElement).toBe(document.body);
  }
  focusField({ target: input, currentTarget: box });
  expect(document.activeElement).toBe(document.body);
  expect(input.selectionStart).toBe(3);
});

test("an input without a caret, such as a date, still takes the focus", () => {
  input.type = "date";
  pointerDown("right");
  expect(document.activeElement).toBe(input);
});

test("a box without an input and a target that is no element do nothing", () => {
  const empty = /** @type {HTMLElement} */ (document.getElementById("empty"));
  pointerDown("alone", empty);
  focusField({ target: null, currentTarget: box });
  focusField({ target: document, currentTarget: box });
  expect(document.activeElement).toBe(document.body);
});
