// What an accordion does with a press on a header that the browser does
// not: an open item stays open, a change is said, and an accordion bound to
// state waits for its state.
import { beforeEach, expect, test, vi } from "vitest";

import { accordionClick } from "$/reflex-ui/behaviors/accordion.js";

/** @type {HTMLElement} */
let root;

/**
 * Render an accordion of three items, the first of them open, with an
 * accordion of its own in its panel.
 *
 * @param {string} attributes The attributes of the element around it.
 * @returns {void}
 */
function render(attributes) {
  document.body.innerHTML = `
    <div id="root" ${attributes}>
      <details data-value="a" open>
        <summary id="a"><h3 id="a-text">A</h3></summary>
        <div>
          <div data-rx-accordion="single">
            <details data-value="inner"><summary id="inner">Inner</summary></details>
          </div>
          <button id="inside">Inside</button>
        </div>
      </details>
      <details data-value="b"><summary id="b">B</summary></details>
      <details><summary id="c">C</summary></details>
    </div>`;
  root = /** @type {HTMLElement} */ (document.getElementById("root"));
}

beforeEach(() => render('data-rx-accordion="single"'));

/**
 * Press an element of the accordion.
 *
 * @param {string | null} id The id of the element, or null for no element.
 * @param {(value: string | string[]) => void} [onValueChange] What the
 *   accordion does when its open items change.
 * @returns {boolean} Whether the accordion kept the press from the browser.
 */
function press(id, onValueChange) {
  let prevented = false;
  accordionClick(
    {
      target: id ? document.getElementById(id) : null,
      currentTarget: root,
      preventDefault: () => {
        prevented = true;
      },
    },
    onValueChange,
  );
  return prevented;
}

test("the open item of an accordion that does not collapse stays open", () => {
  const onValueChange = vi.fn();
  expect(press("a", onValueChange)).toBe(true);
  expect(press("a-text", onValueChange)).toBe(true);
  expect(onValueChange.mock.calls).toEqual([]);
  expect(press("b", onValueChange)).toBe(false);
  expect(onValueChange.mock.calls).toEqual([["b"]]);
});

test("a collapsible accordion closes its open item, and says that none is open", () => {
  render('data-rx-accordion="single" data-collapsible="true"');
  const onValueChange = vi.fn();
  expect(press("a", onValueChange)).toBe(false);
  expect(press("c", onValueChange)).toBe(false);
  expect(press("b")).toBe(false);
  expect(onValueChange.mock.calls).toEqual([[""], [""]]);
});

test("an accordion of several says which items are open after the press", () => {
  render('data-rx-accordion="multiple"');
  const onValueChange = vi.fn();
  expect(press("b", onValueChange)).toBe(false);
  expect(press("a", onValueChange)).toBe(false);
  expect(press("c", onValueChange)).toBe(false);
  expect(onValueChange.mock.calls).toEqual([[["a", "b"]], [[]], [["a", ""]]]);
});

test("an accordion bound to state leaves its items to its state", () => {
  render('data-rx-accordion="multiple" data-bound=""');
  const onValueChange = vi.fn();
  expect(press("b", onValueChange)).toBe(true);
  expect(press("b")).toBe(true);
  expect(onValueChange.mock.calls).toEqual([[["a", "b"]]]);
});

test("a press on anything but a header of the accordion is left alone", () => {
  const onValueChange = vi.fn();
  expect(press("inside", onValueChange)).toBe(false);
  expect(press("inner", onValueChange)).toBe(false);
  expect(press("root", onValueChange)).toBe(false);
  expect(press(null, onValueChange)).toBe(false);
  expect(onValueChange.mock.calls).toEqual([]);
});
