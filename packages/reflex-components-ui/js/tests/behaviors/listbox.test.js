// What a select does with its options: the value it keeps and shows, the
// keys that move through the list, and what it says when the list closes.
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import {
  selectClick,
  selectFocus,
  selectKeyDown,
  selectPointerMove,
  selectToggle,
  syncSelect,
} from "$/reflex-ui/behaviors/listbox.js";

import { installPopover } from "./popover.js";

const OPTIONS = [
  ["apple", "Apple"],
  ["apricot", "Apricot"],
  ["banana", "Banana"],
  ["cherry", "Cherry"],
];

/** @type {HTMLElement} */
let select;
/** @type {HTMLElement} */
let trigger;
/** @type {HTMLElement} */
let popup;
/** @type {HTMLInputElement} */
let holder;
/** @type {string[]} */
let heard;

/**
 * Build a select, wired as a page wires it.
 *
 * @param {{ value?: string, disabled?: string, attributes?: string, id?: string }} [options]
 *   The value it starts with, the value of a disabled option, further
 *   attributes of the element around it, and the id of its popup.
 * @returns {void}
 */
function build({
  value = "",
  disabled = "",
  attributes = "",
  id = "list",
} = {}) {
  const container = document.createElement("div");
  container.innerHTML = `<span data-rx-select ${attributes}>
    <button type="button" role="combobox" popovertarget="${id}"><span data-rx-select-shown data-placeholder="Pick">${value}</span></button>
    <div popover id="${id}" role="listbox" tabindex="-1">
      <div data-rx-select-label>Fruits</div>
      ${OPTIONS.map(
        ([option, text]) =>
          `<div role="option" tabindex="-1" data-value="${option}"${option === disabled ? ' aria-disabled="true"' : ""}><span>✓</span><span data-rx-select-text>${text}</span></div>`,
      ).join("")}
    </div>
    <input data-rx-select-value value="${value}" />
  </span>`;
  document.body.append(container);
  select = /** @type {HTMLElement} */ (
    container.querySelector("[data-rx-select]")
  );
  trigger = /** @type {HTMLElement} */ (select.querySelector("button"));
  popup = /** @type {HTMLElement} */ (select.querySelector("[popover]"));
  holder = /** @type {HTMLInputElement} */ (select.querySelector("input"));
  heard = [];
  // What the browser does of a button with a `popovertarget`.
  trigger.addEventListener("click", () => {
    if (!trigger.matches(":disabled")) popup.togglePopover();
  });
  popup.addEventListener("toggle", (event) =>
    selectToggle(/** @type {any} */ (event), {
      open: (open) => heard.push(`open ${open}`),
      close: () => heard.push("close"),
      escape: () => heard.push("escape"),
      outside: () => heard.push("outside"),
    }),
  );
  holder.addEventListener("input", () => heard.push(`change ${holder.value}`));
  syncSelect(holder);
}

/**
 * Press a key inside the select.
 *
 * @param {string} key The key.
 * @param {Partial<{ target: Element, altKey: boolean, ctrlKey: boolean, metaKey: boolean }>} [more]
 *   Where, when not on what has the focus, and the modifiers held.
 * @returns {boolean} Whether the select kept the key from the browser.
 */
function press(key, more = {}) {
  let prevented = false;
  selectKeyDown({
    key,
    target: document.activeElement,
    currentTarget: select,
    preventDefault: () => (prevented = true),
    ...more,
  });
  return prevented;
}

/**
 * Find an option.
 *
 * @param {string} value Its value.
 * @returns {HTMLElement} The option.
 */
function option(value) {
  return /** @type {HTMLElement} */ (
    select.querySelector(`[data-value="${value}"]`)
  );
}

/**
 * Read what the select shows.
 *
 * @returns {{ value: string, shown: string | null, empty: boolean, chosen: string[], open: boolean }}
 *   Its value, the text and the placeholder mark of its trigger, the
 *   options that say they are chosen, and whether the list is open.
 */
function state() {
  return {
    value: holder.value,
    shown: trigger.textContent,
    empty: trigger.hasAttribute("data-placeholder"),
    chosen: [
      ...select.querySelectorAll(
        '[aria-selected="true"][data-state="checked"]',
      ),
    ].map((element) => element.getAttribute("data-value") ?? ""),
    open: popup.matches(":popover-open"),
  };
}

/**
 * Read the value of the option that has the focus.
 *
 * @returns {string | null | undefined} Its value, or null for anything else.
 */
function focused() {
  return document.activeElement?.getAttribute("data-value");
}

beforeAll(installPopover);

beforeEach(() => {
  document.body.innerHTML = "";
  vi.useRealTimers();
});

test("a select without a value shows its placeholder, and every option unchosen", () => {
  build();

  expect(state()).toEqual({
    value: "",
    shown: "Pick",
    empty: true,
    chosen: [],
    open: false,
  });
  expect(
    [...select.querySelectorAll("[role=option]")].map((element) => [
      element.getAttribute("aria-selected"),
      element.getAttribute("data-state"),
    ]),
  ).toEqual(OPTIONS.map(() => ["false", "unchecked"]));
});

test("a select with a value shows the text of its option", () => {
  build({ value: "banana" });

  expect(state()).toEqual({
    value: "banana",
    shown: "Banana",
    empty: false,
    chosen: ["banana"],
    open: false,
  });
});

test("a value no option has shows the placeholder", () => {
  build({ value: "kiwi" });

  expect(state()).toEqual({
    value: "kiwi",
    shown: "Pick",
    empty: true,
    chosen: [],
    open: false,
  });
});

test("a trigger without the element that shows the value is left as it is", () => {
  build({ value: "banana" });
  trigger.innerHTML = "Custom";
  syncSelect(holder);

  expect(trigger.outerHTML).toBe(
    `<button type="button" role="combobox" popovertarget="${popup.id}" aria-controls="${popup.id}">Custom</button>`,
  );
});

test("an empty element that shows the value is given the text", () => {
  build();
  /** @type {HTMLElement} */ (trigger.firstElementChild).textContent = "";
  holder.value = "cherry";
  syncSelect(holder);

  expect(trigger.textContent).toBe("Cherry");
});

test("nothing is done for what is not a select", () => {
  build();
  const before = document.body.innerHTML;
  syncSelect(null);
  syncSelect(document.body);
  trigger.remove();
  syncSelect(holder);
  press("ArrowDown");

  expect(document.body.innerHTML).toBe(
    before.replace(/<button.*<\/button>/, ""),
  );
});

test("opening gives the focus to the chosen option, or to the first", () => {
  build({ value: "banana" });
  trigger.click();
  expect([state().open, focused(), heard]).toEqual([
    true,
    "banana",
    ["open true"],
  ]);
  expect([
    trigger.getAttribute("aria-expanded"),
    trigger.getAttribute("data-state"),
  ]).toEqual(["true", "open"]);

  build({ disabled: "apple" });
  trigger.click();
  expect(focused()).toBe("apricot");
});

test("a list without options takes the focus itself", () => {
  build();
  for (const element of select.querySelectorAll("[role=option]"))
    element.remove();
  trigger.click();

  expect(document.activeElement).toBe(popup);
});

test("the arrow keys open the list from the trigger", () => {
  build();
  trigger.focus();
  expect([press("ArrowDown"), state().open, focused()]).toEqual([
    true,
    true,
    "apple",
  ]);
  popup.hidePopover();
  expect([press("ArrowUp"), state().open]).toEqual([true, true]);
});

test("a key on anything but the trigger of a closed select is left alone", () => {
  build();
  expect([press("ArrowDown", { target: holder }), state().open]).toEqual([
    false,
    false,
  ]);
  trigger.setAttribute("disabled", "");
  expect([press("ArrowDown", { target: trigger }), state().open]).toEqual([
    false,
    false,
  ]);
  expect([press("Enter", { target: trigger }), state().open]).toEqual([
    false,
    false,
  ]);
});

test("the arrow keys, Home and End move through the options that can be chosen", () => {
  build({ disabled: "apricot" });
  trigger.click();
  const moves = [
    "ArrowDown",
    "ArrowDown",
    "ArrowDown",
    "ArrowUp",
    "Home",
    "ArrowUp",
    "End",
  ].map((key) => [key, press(key), focused()]);

  expect(moves).toEqual([
    ["ArrowDown", true, "banana"],
    ["ArrowDown", true, "cherry"],
    ["ArrowDown", true, "cherry"],
    ["ArrowUp", true, "banana"],
    ["Home", true, "apple"],
    ["ArrowUp", true, "apple"],
    ["End", true, "cherry"],
  ]);
});

test("Tab stays in an open list, and other keys are left to the browser", () => {
  build();
  trigger.click();

  expect([press("Tab"), focused(), state().open]).toEqual([
    true,
    "apple",
    true,
  ]);
  expect([press("Shift"), press("a", { ctrlKey: true }), focused()]).toEqual([
    false,
    false,
    "apple",
  ]);
});

test("Enter and Space choose the option that has the focus", () => {
  build();
  trigger.click();
  press("ArrowDown");
  expect(press("Enter")).toBe(true);
  expect(state()).toEqual({
    value: "apricot",
    shown: "Apricot",
    empty: false,
    chosen: ["apricot"],
    open: false,
  });
  expect(heard).toEqual(["open true", "open false", "close", "change apricot"]);
  expect(document.activeElement).toBe(trigger);

  trigger.click();
  press("End");
  expect(press(" ")).toBe(true);
  expect([state().value, heard.slice(4)]).toEqual([
    "cherry",
    ["open true", "open false", "close", "change cherry"],
  ]);
});

test("Enter with the focus on the list itself chooses nothing", () => {
  build();
  trigger.click();
  popup.focus();

  expect([press("Enter"), state().value, state().open]).toEqual([
    true,
    "",
    true,
  ]);
});

test("choosing the chosen option closes the list and changes nothing", () => {
  build({ value: "banana" });
  trigger.click();
  selectClick({
    target: option("banana").lastElementChild,
    currentTarget: select,
  });

  expect([state().value, state().open, heard]).toEqual([
    "banana",
    false,
    ["open true", "open false", "close"],
  ]);
});

test("a click chooses an option, and nothing anywhere else or on a disabled one", () => {
  build({ disabled: "banana" });
  trigger.click();
  selectClick({ target: option("banana"), currentTarget: select });
  selectClick({ target: popup, currentTarget: select });
  selectClick({ target: null, currentTarget: select });
  expect([state().value, state().open]).toEqual(["", true]);

  selectClick({
    target: option("cherry").lastElementChild,
    currentTarget: select,
  });
  expect([state().value, state().shown, state().open]).toEqual([
    "cherry",
    "Cherry",
    false,
  ]);
});

test("typing in the list goes to the option that starts with it", () => {
  vi.useFakeTimers();
  build();
  trigger.click();

  expect([press("b"), focused()]).toEqual([true, "banana"]);
  vi.advanceTimersByTime(1000);
  // One letter again goes through the options that start with it.
  expect([press("a"), focused()]).toEqual([true, "apple"]);
  expect([press("a"), focused()]).toEqual([true, "apricot"]);
  expect([press("a"), focused()]).toEqual([true, "apple"]);
  vi.advanceTimersByTime(1000);
  // Several letters are a search, which stays where it matches.
  expect([press("a"), press("p"), press("r"), focused()]).toEqual([
    true,
    true,
    true,
    "apricot",
  ]);
  // A space is part of what is typed, and chooses nothing.
  expect([press(" "), state().open, state().value]).toEqual([true, true, ""]);
  vi.advanceTimersByTime(1000);
  expect([press("z"), focused()]).toEqual([true, "apricot"]);
  vi.advanceTimersByTime(1000);
});

test("typing on the trigger chooses the next option that starts with it", () => {
  vi.useFakeTimers();
  build({ value: "apple" });
  trigger.focus();

  expect([press("a"), state().value, state().open]).toEqual([
    true,
    "apricot",
    false,
  ]);
  vi.advanceTimersByTime(1000);
  expect([press("c"), state().value]).toEqual([true, "cherry"]);
  vi.advanceTimersByTime(1000);
  expect([press("z"), state().value]).toEqual([true, "cherry"]);
  vi.advanceTimersByTime(1000);
  // Space is left to the button, which it opens.
  expect(press(" ")).toBe(false);
  expect(heard).toEqual(["change apricot", "change cherry"]);
});

test("the pointer gives the option under it the focus, and the list between options", () => {
  build({ disabled: "banana" });
  trigger.click();
  selectPointerMove({
    target: option("cherry").lastElementChild,
    currentTarget: select,
  });
  expect(focused()).toBe("cherry");
  selectPointerMove({ target: option("cherry"), currentTarget: select });
  expect(focused()).toBe("cherry");

  selectPointerMove({ target: option("banana"), currentTarget: select });
  expect(document.activeElement).toBe(popup);
  selectPointerMove({ target: trigger, currentTarget: select });
  selectPointerMove({ target: null, currentTarget: select });
  expect(document.activeElement).toBe(popup);
});

test("a list says what closed it", () => {
  build();
  trigger.click();
  press("Escape");
  popup.hidePopover();
  expect(heard).toEqual(["open true", "open false", "escape", "close"]);
  expect(document.activeElement).toBe(trigger);

  heard.length = 0;
  trigger.click();
  /** @type {HTMLElement} */ (document.activeElement).blur();
  popup.hidePopover();
  expect(heard).toEqual(["open true", "open false", "outside", "close"]);
  expect(document.activeElement).toBe(document.body);
});

test("a list without anything to call is followed all the same", () => {
  build();
  selectToggle({ currentTarget: popup, newState: "open" });
  expect(focused()).toBe("apple");
  selectToggle({ currentTarget: popup, newState: "closed" });
  expect(document.activeElement).toBe(trigger);
});

test("a select bound to state takes its value and whether it is open from there", () => {
  build();
  syncSelect(holder, "banana", true);
  expect(state()).toEqual({
    value: "banana",
    shown: "Banana",
    empty: false,
    chosen: ["banana"],
    open: true,
  });

  syncSelect(holder, "banana", true);
  syncSelect(holder, "cherry", false);
  expect([state().value, state().open, heard]).toEqual([
    "cherry",
    false,
    ["open true", "open false", "close"],
  ]);
});

test("a choice the state does not follow leaves the select as it was", () => {
  build();
  syncSelect(holder, "banana", null);
  trigger.click();
  selectClick({ target: option("cherry"), currentTarget: select });
  expect([state().value, state().shown, state().chosen, heard]).toEqual([
    "banana",
    "Banana",
    ["banana"],
    ["open true", "open false", "close", "change cherry"],
  ]);

  syncSelect(holder, "cherry", null);
  expect([state().value, state().shown]).toEqual(["cherry", "Cherry"]);
});

test("a select that starts open opens once", () => {
  build({ attributes: 'data-default-open="true"' });
  expect([state().open, select.hasAttribute("data-default-open")]).toEqual([
    true,
    false,
  ]);

  popup.hidePopover();
  syncSelect(holder);
  expect(state().open).toBe(false);

  build({ attributes: 'data-default-open="false"' });
  expect(state().open).toBe(false);
});

test("the input of the value hands the focus it is given to the trigger", () => {
  build();
  holder.focus();
  selectFocus({ currentTarget: holder });
  expect(document.activeElement).toBe(trigger);

  document.body.append(holder);
  holder.focus();
  selectFocus({ currentTarget: holder });
  expect(document.activeElement).toBe(holder);
});
