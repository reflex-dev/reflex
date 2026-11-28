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
 * @template T
 * @param {(event: { currentTarget: HTMLElement, newState?: string }) => T} popupToggle The script.
 * @param {HTMLElement} popup The popup.
 * @param {string} newState What it is now, or is about to be.
 * @returns {T} What the script answers.
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
  return [
    trigger.getAttribute("aria-expanded"),
    trigger.getAttribute("data-state"),
  ];
}

beforeEach(() => {
  vi.resetModules();
  // The frame a popup is first drawn in comes at once.
  vi.stubGlobal("requestAnimationFrame", (/** @type {() => void} */ frame) =>
    frame(),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("the trigger says whether its popup is open, and the browser places it", async () => {
  vi.stubGlobal("CSS", {
    supports: (/** @type {string} */ rule) => rule === "position-area: bottom",
  });
  const { popupToggle } = await import("$/reflex-ui/behaviors/popup.js");
  const { trigger, popup } = build();

  expect(toggle(popupToggle, popup, "open")).toBe(true);
  expect(said(trigger)).toEqual(["true", "open"]);
  expect(toggle(popupToggle, popup, "closed")).toBe(false);
  expect(said(trigger)).toEqual(["false", "closed"]);
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(popup.getAttribute("style")).toBe(null);
});

/**
 * Lay a popup out as a browser does: where it is told, moved by what its
 * script found it off whole pixels.
 *
 * @param {HTMLElement} popup The popover.
 * @param {{ x: number, y: number }} laid Where it is laid out, unmoved.
 * @param {{ drawn?: { x: number, y: number }, turned?: boolean }} [how]
 *   How far its transform draws it from there, and whether the browser
 *   turned it over, its margins with it.
 * @returns {void}
 */
function layOut(popup, laid, { drawn = { x: 0, y: 0 }, turned = false } = {}) {
  const moved = (/** @type {string} */ axis) =>
    (Number.parseFloat(
      popup.style.getPropertyValue(`--rx-popup-snap-${axis}`),
    ) || 0) * (turned ? -1 : 1);
  popup.getBoundingClientRect = () =>
    /** @type {DOMRect} */ ({
      x: laid.x + moved("x") + drawn.x,
      y: laid.y + moved("y") + drawn.y,
    });
}

test("a popup that opens is laid out on whole pixels before it is drawn", async () => {
  vi.stubGlobal("CSS", { supports: () => true });
  const { popupBeforeToggle } = await import("$/reflex-ui/behaviors/popup.js");
  const { popup } = build();

  layOut(popup, { x: 34.640625, y: 52 });
  toggle(popupBeforeToggle, popup, "open");
  expect(popup.getAttribute("style")).toBe("--rx-popup-snap-x: 0.359375px;");

  // What it was moved by before is forgotten when it opens again.
  layOut(popup, { x: 60.3125, y: 51.75 });
  toggle(popupBeforeToggle, popup, "open");
  expect(popup.getAttribute("style")).toBe(
    "--rx-popup-snap-x: -0.3125px; --rx-popup-snap-y: 0.25px;",
  );

  // A popup on whole pixels is left where it is, and one that closes too.
  layOut(popup, { x: 40, y: 50 });
  toggle(popupBeforeToggle, popup, "open");
  expect(popup.getAttribute("style")).toBe("");
  layOut(popup, { x: 40.5, y: 50 });
  toggle(popupBeforeToggle, popup, "closed");
  expect(popup.getAttribute("style")).toBe("");
});

test("a popup is laid out on whole pixels whatever it comes in with", async () => {
  vi.stubGlobal("CSS", { supports: () => true });
  const { popupBeforeToggle } = await import("$/reflex-ui/behaviors/popup.js");
  const { popup } = build();
  // Halfway in: half its size about a point inside it, and four pixels up.
  popup.style.transform = "matrix(0.5, 0, 0, 0.5, 0, -4)";
  popup.style.transformOrigin = "10px 20px";
  layOut(popup, { x: 35.25, y: 44.5 }, { drawn: { x: 5, y: 6 } });

  toggle(popupBeforeToggle, popup, "open");
  expect([
    popup.style.getPropertyValue("--rx-popup-snap-x"),
    popup.style.getPropertyValue("--rx-popup-snap-y"),
  ]).toEqual(["-0.25px", "0.5px"]);
});

test("a popup the browser turned over is moved the other way", async () => {
  vi.stubGlobal("CSS", { supports: () => true });
  const { popupBeforeToggle } = await import("$/reflex-ui/behaviors/popup.js");
  const { popup } = build();
  layOut(popup, { x: 34.640625, y: 52.25 }, { turned: true });

  toggle(popupBeforeToggle, popup, "open");
  expect(popup.getAttribute("style")).toBe(
    "--rx-popup-snap-x: -0.359375px; --rx-popup-snap-y: 0.25px;",
  );
});

test("a screen with more pixels has the popup on its pixels", async () => {
  vi.stubGlobal("CSS", { supports: () => true });
  vi.stubGlobal("devicePixelRatio", 2);
  const { popupBeforeToggle } = await import("$/reflex-ui/behaviors/popup.js");
  const { popup } = build();
  layOut(popup, { x: 10.3, y: 20.5 });

  toggle(popupBeforeToggle, popup, "open");
  expect(popup.getAttribute("style")).toBe("--rx-popup-snap-x: 0.203125px;");
});

test("a browser that does not place popups moves none before it is drawn", async () => {
  const { popupBeforeToggle } = await import("$/reflex-ui/behaviors/popup.js");
  const { popup } = build();
  layOut(popup, { x: 34.640625, y: 52 });

  toggle(popupBeforeToggle, popup, "open");
  expect(popup.getAttribute("style")).toBe(null);
});

test("a popup nothing opens is followed without a trigger", async () => {
  const { popupToggle, opener } = await import(
    "$/reflex-ui/behaviors/popup.js"
  );
  document.body.innerHTML = `<div popover id="alone"></div><div popover></div>`;
  const [alone, unnamed] = /** @type {HTMLElement[]} */ ([
    ...document.querySelectorAll("[popover]"),
  ]);

  expect(opener(alone)).toBe(null);
  expect(opener(unnamed)).toBe(null);
  expect(toggle(popupToggle, alone, "open")).toBe(true);
});

test("the popups a loop renders with one id are told apart", async () => {
  const { opener, pair } = await import("$/reflex-ui/behaviors/popup.js");
  document.body.innerHTML = [1, 2]
    .map(
      () =>
        `<span><button popovertarget="list"></button><div popover id="list"></div></span>`,
    )
    .join("");
  const spans = [...document.querySelectorAll("span")];
  for (const span of spans) {
    pair(
      /** @type {Element} */ (span.querySelector("[popover]")),
      span.querySelector("button"),
    );
  }
  // A second sync of the first changes nothing.
  pair(
    /** @type {Element} */ (spans[0].querySelector("[popover]")),
    spans[0].querySelector("button"),
  );
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
  expect(
    opener(/** @type {Element} */ (spans[1].querySelector("[popover]"))),
  ).toBe(spans[1].querySelector("button"));
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
