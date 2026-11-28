// The keys of a group that is one stop for Tab: the arrow keys, Home and End
// move the focus between its radio buttons without choosing one, and Enter
// chooses.
import { beforeEach, expect, test } from "vitest";

import { rovingKeyDown } from "$/reflex-ui/behaviors/roving-focus.js";

/** @type {HTMLElement} */
let group;

beforeEach(() => {
  document.body.innerHTML = `
    <div id="group">
      <label><input type="radio" name="g" value="a" /></label>
      <label><input type="radio" name="g" value="b" disabled /></label>
      <label><input type="radio" name="g" value="c" /></label>
      <label><input type="radio" name="g" value="d" /></label>
      <input type="text" id="text" />
    </div>`;
  group = /** @type {HTMLElement} */ (document.getElementById("group"));
});

/**
 * Find a radio button of the group.
 *
 * @param {string} value Its value.
 * @returns {HTMLInputElement} The radio button.
 */
function radio(value) {
  return /** @type {HTMLInputElement} */ (
    group.querySelector(`[value=${value}]`)
  );
}

/**
 * Press a key on whatever has the focus.
 *
 * @param {string} key The key.
 * @param {Record<string, boolean>} [modifiers] The modifiers held with it.
 * @returns {boolean} Whether the group kept the key from the browser.
 */
function press(key, modifiers = {}) {
  let prevented = false;
  rovingKeyDown({
    key,
    target: document.activeElement,
    currentTarget: group,
    preventDefault: () => {
      prevented = true;
    },
    ...modifiers,
  });
  return prevented;
}

/**
 * Read which radio button has the focus.
 *
 * @returns {string} Its value.
 */
function focused() {
  return /** @type {HTMLInputElement} */ (document.activeElement).value;
}

test("the arrow keys move the focus past a disabled item and around the ends", () => {
  radio("a").focus();
  const visited = [];
  for (const key of [
    "ArrowRight",
    "ArrowDown",
    "ArrowRight",
    "ArrowLeft",
    "ArrowUp",
  ]) {
    expect(press(key)).toBe(true);
    visited.push(focused());
  }
  expect(visited).toEqual(["c", "d", "a", "d", "c"]);
  expect(group.querySelectorAll(":checked").length).toBe(0);
});

test("Home and End go to the first and the last item", () => {
  radio("c").focus();
  expect(press("End")).toBe(true);
  expect(focused()).toBe("d");
  expect(press("Home")).toBe(true);
  expect(focused()).toBe("a");
});

test("Enter chooses the item the focus is on", () => {
  radio("c").focus();
  expect(press("Enter")).toBe(true);
  expect(radio("c").checked).toBe(true);
  expect(focused()).toBe("c");
});

test("left and right are turned where the text runs from the right", () => {
  group.style.direction = "rtl";
  radio("c").focus();
  press("ArrowRight");
  expect(focused()).toBe("a");
  press("ArrowLeft");
  expect(focused()).toBe("c");
  press("ArrowDown");
  expect(focused()).toBe("d");
});

test("other keys, keys with a modifier and other controls are left to the browser", () => {
  radio("a").focus();
  expect(press("a")).toBe(false);
  expect(press(" ")).toBe(false);
  expect(press("Tab")).toBe(false);
  for (const modifier of ["altKey", "ctrlKey", "metaKey", "shiftKey"]) {
    expect(press("ArrowRight", { [modifier]: true })).toBe(false);
  }
  expect(focused()).toBe("a");
  /** @type {HTMLElement} */ (document.getElementById("text")).focus();
  expect(press("ArrowRight")).toBe(false);
  expect(press("Enter")).toBe(false);
  expect(document.activeElement?.id).toBe("text");
});
