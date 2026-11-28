// Where a popup goes in a browser without CSS anchor positioning.
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { place } from "$/reflex-ui/behaviors/popup-position.js";

/** @type {HTMLElement} */
let popup;
/** @type {HTMLElement} */
let anchor;
/** @type {{ left: number, top: number, bottom: number, width: number }} */
let box;

/**
 * Read where the popup was put.
 *
 * @returns {string[]} Its left, top, least width and greatest height.
 */
function placed() {
  const { left, top, minWidth, maxHeight } = popup.style;
  return [left, top, minWidth, maxHeight];
}

beforeEach(() => {
  document.body.innerHTML = `<button></button><div popover style="margin-top: 4px"></div>`;
  anchor = /** @type {HTMLElement} */ (document.querySelector("button"));
  popup = /** @type {HTMLElement} */ (document.querySelector("[popover]"));
  box = { left: 40, top: 100, bottom: 132, width: 120 };
  anchor.getBoundingClientRect = () => /** @type {DOMRect} */ (box);
  Object.defineProperty(popup, "offsetHeight", {
    value: 200,
    configurable: true,
  });
  Object.defineProperty(popup, "offsetWidth", {
    value: 160,
    configurable: true,
  });
  vi.stubGlobal("innerWidth", 800);
  vi.stubGlobal("innerHeight", 600);
});

afterEach(() => {
  place(popup, anchor, false);
  vi.unstubAllGlobals();
});

test("the popup goes below its anchor, at its start and at least as wide", () => {
  place(popup, anchor, true);

  expect(placed()).toEqual(["40px", "132px", "120px", "454px"]);
  expect([popup.style.position, popup.style.inset]).toEqual(["fixed", "auto"]);
});

test("it goes above where there is more room and it would leave the viewport", () => {
  box = { left: 40, top: 460, bottom: 492, width: 120 };
  place(popup, anchor, true);

  expect(placed()).toEqual(["40px", "252px", "120px", "446px"]);
});

test("a popup taller than the room above is as tall as the room", () => {
  box = { left: 40, top: 300, bottom: 532, width: 120 };
  Object.defineProperty(popup, "offsetHeight", { value: 400 });
  place(popup, anchor, true);

  expect(placed()).toEqual(["40px", "6px", "120px", "286px"]);
});

test("it stays inside the viewport at both ends", () => {
  box = { left: 700, top: 100, bottom: 132, width: 120 };
  place(popup, anchor, true);
  expect(placed()).toEqual(["630px", "132px", "120px", "454px"]);

  box = { left: -30, top: 100, bottom: 132, width: 120 };
  place(popup, anchor, true);
  expect(placed()).toEqual(["10px", "132px", "120px", "454px"]);
});

test("it follows its anchor while it is open, and no longer", () => {
  place(popup, anchor, true);
  box = { left: 60, top: 80, bottom: 112, width: 120 };
  window.dispatchEvent(new Event("scroll"));
  expect(placed()).toEqual(["60px", "112px", "120px", "474px"]);

  box = { left: 80, top: 80, bottom: 112, width: 140 };
  window.dispatchEvent(new Event("resize"));
  expect(placed()).toEqual(["80px", "112px", "140px", "474px"]);

  place(popup, anchor, false);
  box = { left: 0, top: 0, bottom: 32, width: 10 };
  window.dispatchEvent(new Event("scroll"));
  window.dispatchEvent(new Event("resize"));
  expect(placed()).toEqual(["80px", "112px", "140px", "474px"]);
});

test("it is put on whole pixels", () => {
  box = { left: 40.4, top: 100.2, bottom: 132.6, width: 120.5 };
  place(popup, anchor, true);

  expect(placed()).toEqual(["40px", "133px", "120.5px", "453.4px"]);
});

test("a popup without a margin has no gap", () => {
  popup.style.marginTop = "";
  place(popup, anchor, true);

  expect(placed()).toEqual(["40px", "132px", "120px", "458px"]);
});
