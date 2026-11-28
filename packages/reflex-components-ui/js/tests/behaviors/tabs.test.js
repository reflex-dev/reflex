// What tabs do with a press on a trigger and with the focus: one trigger is
// selected and its panel shown, and Tab stops on one trigger.
import { beforeEach, expect, test, vi } from "vitest";

import { tabsEvent } from "$/reflex-ui/behaviors/tabs.js";

/** @type {HTMLElement} */
let root;

/**
 * Render tabs, with tabs of their own in the first panel.
 *
 * @param {string} [attributes] The attributes of the element around them.
 * @returns {void}
 */
function render(attributes = 'data-rx-tabs=""') {
  document.body.innerHTML = `
    <div id="root" ${attributes}>
      <div role="tablist">
        <button role="tab" id="a" data-value="a" aria-selected="true" data-state="active" tabindex="0"><span>A</span></button>
        <button role="tab" id="b" data-value="b" aria-selected="false" data-state="inactive" tabindex="-1">B</button>
        <button role="tab" id="c" data-value="c" aria-selected="false" data-state="inactive" tabindex="-1" disabled>C</button>
        <button id="other">Other</button>
      </div>
      <div role="tabpanel" data-value="a" data-state="active">
        <div data-rx-tabs="">
          <button role="tab" id="inner" data-value="b" aria-selected="false" tabindex="0">Inner</button>
          <div role="tabpanel" id="inner-panel" data-value="b" hidden></div>
        </div>
      </div>
      <div role="tabpanel" data-value="b" data-state="inactive" hidden></div>
      <div role="tabpanel" data-value="c" data-state="inactive" hidden></div>
    </div>`;
  root = /** @type {HTMLElement} */ (document.getElementById("root"));
}

beforeEach(() => render());

/**
 * Send the tabs an event of one of their elements.
 *
 * @param {string} type The type of the event.
 * @param {string} id The id of the element it happens on.
 * @param {{ to?: string, onChange?: (value: string) => void }} [options]
 *   Where the focus goes, and what the tabs do when they change.
 * @returns {void}
 */
function send(type, id, { to, onChange } = {}) {
  tabsEvent(
    {
      type,
      target: document.getElementById(id),
      currentTarget: root,
      relatedTarget: to ? document.getElementById(to) : null,
    },
    onChange,
  );
}

/**
 * Read the state of the tabs.
 *
 * @returns {string[]} For each of their own triggers whether it is
 *   selected, its state and its place in the Tab order, then each panel
 *   that is shown.
 */
function state() {
  return [
    ...["a", "b", "c"].map((id) => {
      const tab = /** @type {HTMLElement} */ (document.getElementById(id));
      return `${id}:${tab.getAttribute("aria-selected")}:${tab.dataset.state}:${tab.tabIndex}`;
    }),
    ...[...root.querySelectorAll(":scope > [role=tabpanel]:not([hidden])")].map(
      (panel) =>
        `${/** @type {HTMLElement} */ (panel).dataset.value}:${/** @type {HTMLElement} */ (panel).dataset.state}`,
    ),
  ];
}

const START = [
  "a:true:active:0",
  "b:false:inactive:-1",
  "c:false:inactive:-1",
  "a:active",
];
const SECOND = [
  "a:false:inactive:-1",
  "b:true:active:0",
  "c:false:inactive:-1",
  "b:active",
];

test("a press on a trigger selects it, shows its panel and says so once", () => {
  const onChange = vi.fn();
  send("click", "b", { onChange });
  expect(state()).toEqual(SECOND);
  send("click", "b", { onChange });
  expect(onChange.mock.calls).toEqual([["b"]]);
  send("click", "a");
  expect(state()).toEqual(START);
});

test("a press inside a trigger is a press on it", () => {
  /** @type {HTMLElement} */ (document.getElementById("b")).innerHTML =
    '<span id="text">B</span>';
  send("click", "text");
  expect(state()).toEqual(SECOND);
});

test("the focus selects a trigger, unless the tabs are activated by hand", () => {
  send("focus", "b");
  expect(state()).toEqual(SECOND);
  render('data-rx-tabs="" data-activation="manual"');
  const onChange = vi.fn();
  send("focus", "b", { onChange });
  expect(state()).toEqual([
    "a:true:active:-1",
    "b:false:inactive:0",
    "c:false:inactive:-1",
    "a:active",
  ]);
  expect(onChange.mock.calls).toEqual([]);
  send("click", "b", { onChange });
  expect(state()).toEqual(SECOND);
  expect(onChange.mock.calls).toEqual([["b"]]);
});

test("Tab stops on the selected trigger again once the focus has left", () => {
  render('data-rx-tabs="" data-activation="manual"');
  send("focus", "b");
  send("blur", "b", { to: "a" });
  expect(state()[1]).toBe("b:false:inactive:0");
  send("blur", "b", { to: "other" });
  expect(state()).toEqual(START);
  /** @type {HTMLElement} */ (document.getElementById("a")).setAttribute(
    "aria-selected",
    "false",
  );
  send("focus", "b");
  send("blur", "b");
  expect(state()[1]).toBe("b:false:inactive:0");
});

test("a disabled trigger is not selected", () => {
  const onChange = vi.fn();
  send("click", "c", { onChange });
  expect(state()).toEqual([
    "a:true:active:-1",
    "b:false:inactive:-1",
    "c:false:inactive:0",
    "a:active",
  ]);
  expect(onChange.mock.calls).toEqual([]);
});

test("tabs bound to state say what was selected and change nothing", () => {
  render('data-rx-tabs="bound"');
  const onChange = vi.fn();
  send("click", "b", { onChange });
  expect(onChange.mock.calls).toEqual([["b"]]);
  expect(state()).toEqual([
    "a:true:active:-1",
    "b:false:inactive:0",
    "c:false:inactive:-1",
    "a:active",
  ]);
});

test("what is no trigger of the tabs is left alone", () => {
  const onChange = vi.fn();
  send("click", "other", { onChange });
  send("click", "inner", { onChange });
  send("focus", "inner", { onChange });
  tabsEvent({ type: "click", target: null, currentTarget: root }, onChange);
  expect(state()).toEqual(START);
  expect(onChange.mock.calls).toEqual([]);
  expect(
    /** @type {HTMLElement} */ (document.getElementById("inner-panel")).hidden,
  ).toBe(true);
});

test("a trigger without a value selects the tab of no value", () => {
  /** @type {HTMLElement} */ (document.getElementById("b")).removeAttribute(
    "data-value",
  );
  const onChange = vi.fn();
  send("click", "b", { onChange });
  expect(onChange.mock.calls).toEqual([[""]]);
});
