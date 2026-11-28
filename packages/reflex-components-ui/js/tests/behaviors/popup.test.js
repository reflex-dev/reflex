// What a popup says on the element that opens it, and where it goes in a
// browser that does not place it.
import { afterEach, beforeEach, expect, test, vi } from "vitest";

/**
 * Build a button and the popup it opens.
 *
 * @param {string} [id] The id of the popup.
 * @returns {{ trigger: HTMLElement, popup: HTMLElement }} The two.
 */
function build(id = "list") {
  document.body.innerHTML = `<button popovertarget="${id}"></button><div popover id="${id}"></div>`;
  return {
    trigger: /** @type {HTMLElement} */ (document.querySelector("button")),
    popup: /** @type {HTMLElement} */ (document.querySelector("[popover]")),
  };
}

/**
 * Send a popup the toggle the browser sends.
 *
 * @param {(event: { currentTarget: HTMLElement, newState?: string }) => boolean} popupToggle The script.
 * @param {HTMLElement} popup The popup.
 * @param {string} newState What it is now.
 * @returns {boolean} What the script answers.
 */
function toggle(popupToggle, popup, newState) {
  return popupToggle({ currentTarget: popup, newState });
}

/**
 * Read what a trigger says of its popup.
 *
 * @param {HTMLElement} trigger The trigger.
 * @returns {(string | null)[]} Its `aria-expanded` and its `data-state`.
 */
function said(trigger) {
  return [trigger.getAttribute("aria-expanded"), trigger.getAttribute("data-state")];
}

beforeEach(() => {
  vi.resetModules();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("the trigger says whether its popup is open, and the browser places it", async () => {
  vi.stubGlobal("CSS", { supports: (/** @type {string} */ rule) => rule === "position-area: bottom" });
  const { popupToggle } = await import("$/reflex-ui/behaviors/popup.js");
  const { trigger, popup } = build();

  expect(toggle(popupToggle, popup, "open")).toBe(true);
  expect(said(trigger)).toEqual(["true", "open"]);
  expect(toggle(popupToggle, popup, "closed")).toBe(false);
  expect(said(trigger)).toEqual(["false", "closed"]);
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(popup.getAttribute("style")).toBe(null);
});

test("a popup nothing opens is followed without a trigger", async () => {
  const { popupToggle, opener } = await import("$/reflex-ui/behaviors/popup.js");
  document.body.innerHTML = `<div popover id="alone"></div><div popover></div>`;
  const [alone, unnamed] = /** @type {HTMLElement[]} */ ([...document.querySelectorAll("[popover]")]);

  expect(opener(alone)).toBe(null);
  expect(opener(unnamed)).toBe(null);
  expect(toggle(popupToggle, alone, "open")).toBe(true);
});

test("the popups a loop renders with one id are told apart", async () => {
  const { opener, pair } = await import("$/reflex-ui/behaviors/popup.js");
  document.body.innerHTML = [1, 2]
    .map(() => `<span><button popovertarget="list"></button><div popover id="list"></div></span>`)
    .join("");
  const spans = [...document.querySelectorAll("span")];
  for (const span of spans) {
    pair(/** @type {Element} */ (span.querySelector("[popover]")), span.querySelector("button"));
  }
  // A second sync of the first changes nothing.
  pair(/** @type {Element} */ (spans[0].querySelector("[popover]")), spans[0].querySelector("button"));
  pair(/** @type {Element} */ (spans[1].querySelector("[popover]")), null);

  expect(
    spans.map((span) => [
      span.querySelector("[popover]")?.id,
      span.querySelector("button")?.getAttribute("popovertarget"),
      span.querySelector("button")?.getAttribute("aria-controls"),
    ]),
  ).toEqual([
    ["list-1", "list-1", "list-1"],
    ["list-2", "list-2", "list-2"],
  ]);
  expect(opener(/** @type {Element} */ (spans[1].querySelector("[popover]")))).toBe(
    spans[1].querySelector("button"),
  );
});

test("a browser without anchor positioning has the popup placed by a script", async () => {
  const { popupToggle } = await import("$/reflex-ui/behaviors/popup.js");
  const { trigger, popup } = build();
  vi.stubGlobal("innerWidth", 800);
  vi.stubGlobal("innerHeight", 600);
  trigger.getBoundingClientRect = () =>
    /** @type {DOMRect} */ ({ left: 40, top: 100, bottom: 132, width: 120 });
  Object.defineProperty(popup, "offsetHeight", { value: 200 });
  Object.defineProperty(popup, "offsetWidth", { value: 160 });
  popup.style.marginTop = "4px";

  toggle(popupToggle, popup, "open");
  await vi.waitFor(() => expect(popup.style.top).toBe("132px"));
  expect(popup.getAttribute("style")).toBe(
    "margin-top: 4px; position: fixed; inset: auto; min-width: 120px; max-height: 454px; left: 40px; top: 132px;",
  );
});
