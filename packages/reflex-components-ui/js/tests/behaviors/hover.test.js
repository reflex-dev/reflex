// A popup that opens under the pointer and with the focus of the keyboard:
// when it opens and closes, what it says, and the state it follows.
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { installPopover } from "./popover.js";

/** @type {typeof import("$/reflex-ui/behaviors/hover.js")} */
let api;
/** @type {HTMLElement} */
let trigger;
/** @type {HTMLElement} */
let popup;
/** @type {string[]} */
let seen;

/**
 * Render a button and the popup that opens under it, and a second pair
 * rendered with the same id, as a loop renders them.
 *
 * @param {string} [attributes] The attributes of the first popup.
 * @returns {void}
 */
function render(attributes = 'role="tooltip"') {
  document.body.innerHTML = `
    <button id="save" data-rx-hover="rx-tip" aria-describedby="rx-tip"><span id="save-text">Save</span></button>
    <div popover="manual" id="rx-tip" data-open-delay="200" data-close-delay="100" ${attributes}><a id="link" href="#">More</a></div>
    <button id="copy" data-rx-hover="rx-tip"></button>
    <div popover="manual" id="rx-tip" data-open-delay="0" data-close-delay="0"></div>
    <button id="elsewhere"></button>`;
  trigger = /** @type {HTMLElement} */ (document.getElementById("save"));
  popup = /** @type {HTMLElement} */ (trigger.nextElementSibling);
}

const on = {
  open: (/** @type {boolean} */ open) => seen.push(`open:${open}`),
  escape: () => seen.push("escape"),
  outside: () => seen.push("outside"),
};

beforeEach(async () => {
  vi.resetModules();
  vi.useFakeTimers();
  vi.stubGlobal("CSS", { supports: () => true });
  installPopover();
  api = await import("$/reflex-ui/behaviors/hover.js");
  seen = [];
  render();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/**
 * Send what happens on a button or on its popup.
 *
 * @param {string} type The type of the event.
 * @param {HTMLElement} [element] The element that hears it.
 * @param {{ pointerType?: string, to?: HTMLElement | null }} [details] The
 *   kind of pointer, and where the focus goes.
 * @returns {void}
 */
function send(type, element = trigger, { pointerType, to } = {}) {
  api.hoverEvent({
    type,
    currentTarget: element,
    pointerType,
    relatedTarget: to,
  });
}

/**
 * Say whether the popup is shown.
 *
 * @returns {boolean} Whether it is open.
 */
function shown() {
  return popup.matches(":popover-open");
}

test("the first sync names each pair of a loop apart, for the browser to place the popup by", () => {
  const second = /** @type {HTMLElement} */ (
    document.getElementById("copy")?.nextElementSibling
  );
  api.hoverSync(popup, null, on);
  api.hoverSync(second);
  api.hoverSync(popup, null, on);
  api.hoverSync(null);
  expect([
    popup.id,
    trigger.dataset.rxHover,
    trigger.getAttribute("aria-describedby"),
    trigger.style.getPropertyValue("anchor-name"),
    popup.style.getPropertyValue("position-anchor"),
  ]).toEqual([
    "rx-tip-1",
    "rx-tip-1",
    "rx-tip-1",
    "--rx-tip-1",
    "--rx-tip-1",
  ]);
  expect([
    second.id,
    document.getElementById("copy")?.dataset.rxHover,
    document.getElementById("copy")?.hasAttribute("aria-describedby"),
  ]).toEqual(["rx-tip-2", "rx-tip-2", false]);
});

test("a popup an app named keeps its name, and one nothing opens is left alone", () => {
  document.body.innerHTML = `<button data-rx-hover="mine"></button><div popover="manual" id="mine"></div><div popover="manual" id="rx-alone"></div>`;
  const [mine, alone] = /** @type {HTMLElement[]} */ ([
    ...document.querySelectorAll("[popover]"),
  ]);
  api.hoverSync(mine);
  api.hoverSync(alone);
  expect([mine.id, alone.id]).toEqual(["mine", "rx-alone"]);
});

test("the pointer opens the popup after its delay, and closes it after the other", () => {
  api.hoverSync(popup, null, on);
  send("pointerenter");
  vi.advanceTimersByTime(199);
  expect(shown()).toBe(false);
  vi.advanceTimersByTime(1);
  expect([shown(), trigger.dataset.state]).toEqual([true, "delayed-open"]);
  send("pointerleave");
  vi.advanceTimersByTime(99);
  expect(shown()).toBe(true);
  // The pointer reached the popup in time.
  send("pointerenter", popup);
  vi.advanceTimersByTime(500);
  expect(shown()).toBe(true);
  send("pointerleave", popup);
  vi.advanceTimersByTime(100);
  expect([shown(), trigger.dataset.state]).toEqual([false, "closed"]);
  expect(seen).toEqual(["open:true", "open:false"]);
});

test("a pointer that leaves before the delay opens nothing, and a finger opens nothing", () => {
  api.hoverSync(popup, null, on);
  send("pointerenter");
  vi.advanceTimersByTime(100);
  send("pointerleave");
  vi.advanceTimersByTime(1000);
  send("pointerenter", trigger, { pointerType: "touch" });
  vi.advanceTimersByTime(1000);
  expect(shown()).toBe(false);
  expect(seen).toEqual([]);
});

test("the focus of the keyboard opens the popup at once, and closes it when it leaves both", () => {
  api.hoverSync(popup, null, on);
  send("focus");
  vi.advanceTimersByTime(0);
  expect(shown()).toBe(false);
  const matches = trigger.matches.bind(trigger);
  trigger.matches = (selector) =>
    selector === ":focus-visible" || matches(selector);
  send("focus");
  vi.advanceTimersByTime(0);
  expect(shown()).toBe(true);
  send("blur", trigger, { to: document.getElementById("link") });
  send("blur", popup, { to: document.getElementById("save-text") });
  vi.advanceTimersByTime(0);
  expect(shown()).toBe(true);
  send("blur", popup, { to: document.getElementById("elsewhere") });
  vi.advanceTimersByTime(0);
  expect(shown()).toBe(false);
});

test("Escape, a press outside and a press on the button of a tooltip close it", () => {
  api.hoverSync(popup, null, on);
  const open = () => {
    send("pointerenter");
    vi.advanceTimersByTime(200);
  };
  open();
  dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
  expect(shown()).toBe(true);
  dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  expect(shown()).toBe(false);
  // Once closed, the popup hears nothing of the page.
  dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  open();
  document
    .getElementById("link")
    ?.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  expect(shown()).toBe(true);
  document
    .getElementById("elsewhere")
    ?.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  expect(shown()).toBe(false);
  open();
  send("pointerdown");
  vi.advanceTimersByTime(0);
  expect(shown()).toBe(false);
  expect(seen).toEqual([
    "open:true",
    "escape",
    "open:false",
    "open:true",
    "outside",
    "open:false",
    "open:true",
    "open:false",
  ]);
});

test("a popup bound to state says what is asked of it, and shows its state", () => {
  render("");
  api.hoverSync(popup, false, on);
  send("pointerenter");
  vi.advanceTimersByTime(200);
  expect(shown()).toBe(false);
  api.hoverSync(popup, true, on);
  expect([shown(), trigger.dataset.state]).toEqual([true, "open"]);
  api.hoverSync(popup, true, on);
  dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  expect(shown()).toBe(true);
  api.hoverSync(popup, false, on);
  expect(shown()).toBe(false);
  expect(seen).toEqual(["open:true", "escape", "open:false"]);
});

test("a popup that starts open opens once, and one that is unknown is left alone", () => {
  render('data-default-open="true"');
  send("pointerenter");
  vi.advanceTimersByTime(1000);
  expect(shown()).toBe(false);
  api.hoverSync(popup);
  expect(shown()).toBe(true);
  send("pointerleave");
  vi.advanceTimersByTime(100);
  api.hoverSync(popup);
  expect(shown()).toBe(false);
  trigger.dataset.rxHover = "gone";
  send("pointerenter");
  delete trigger.dataset.rxHover;
  send("pointerenter");
});

test("a browser without anchor positioning has the popup placed by a script", async () => {
  vi.resetModules();
  vi.stubGlobal("CSS", { supports: () => false });
  const place = vi.fn();
  vi.doMock("$/reflex-ui/behaviors/popup-position.js", () => ({ place }));
  api = await import("$/reflex-ui/behaviors/hover.js");
  api.hoverSync(popup);
  send("pointerenter");
  vi.advanceTimersByTime(200);
  await vi.waitFor(() => expect(place.mock.calls).toEqual([[popup, trigger, true]]));
  vi.doUnmock("$/reflex-ui/behaviors/popup-position.js");
});
