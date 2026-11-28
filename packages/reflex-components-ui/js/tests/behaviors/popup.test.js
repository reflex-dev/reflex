// What a popup says on the element that opens it, and where it goes in a
// browser that does not place it.
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { installPopover } from "./popover.js";

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
  return [
    trigger.getAttribute("aria-expanded"),
    trigger.getAttribute("data-state"),
  ];
}

beforeEach(() => {
  vi.resetModules();
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
        `<span><button popovertarget="rx-list"></button><div popover id="rx-list"><button popovertarget="rx-list" popovertargetaction="hide"></button></div></span>`,
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
    ["rx-list-1", "rx-list-1", "rx-list-1"],
    ["rx-list-2", "rx-list-2", "rx-list-2"],
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

/**
 * Build a popover with a control and a button that closes it, after the
 * button that opens it.
 *
 * @param {string} [attributes] The attributes of the popover.
 * @returns {Promise<{ api: typeof import("$/reflex-ui/behaviors/popup.js"), trigger: HTMLElement, popup: HTMLElement, seen: string[], on: Record<string, (open?: boolean) => void> }>}
 *   The script, the two elements, and handlers that keep what they are
 *   called with.
 */
async function popover(attributes = "") {
  installPopover();
  const api = await import("$/reflex-ui/behaviors/popup.js");
  document.body.innerHTML = `
    <button id="open" popovertarget="rx-panel"></button>
    <div popover id="rx-panel" tabindex="-1" ${attributes}>
      <input id="field" />
      <button id="close" popovertarget="rx-panel" popovertargetaction="hide"><span id="close-text">Close</span></button>
    </div>
    <button id="beside"></button>`;
  const popup = /** @type {HTMLElement} */ (
    document.querySelector("[popover]")
  );
  /** @type {string[]} */
  const seen = [];
  const on = Object.fromEntries(
    [
      "open",
      "openAutoFocus",
      "closeAutoFocus",
      "escape",
      "outside",
      "focusOutside",
      "interact",
    ].map((name) => [
      name,
      (/** @type {boolean | undefined} */ open) =>
        seen.push(open === undefined ? name : `${name}:${open}`),
    ]),
  );
  popup.addEventListener("toggle", (event) =>
    api.popupEvent(
      /** @type {{ type: string, target: EventTarget | null, currentTarget: HTMLElement }} */ (
        /** @type {unknown} */ (event)
      ),
      on,
    ),
  );
  return {
    api,
    trigger: /** @type {HTMLElement} */ (document.getElementById("open")),
    popup,
    seen,
    on,
  };
}

/**
 * Send a popover something that happens inside it.
 *
 * @param {typeof import("$/reflex-ui/behaviors/popup.js")} api The script.
 * @param {HTMLElement} popup The popover.
 * @param {string} type The type of the event.
 * @param {{ target?: string, key?: string, to?: string }} [details] The id
 *   of the element it happens on, the key, and where the focus goes.
 * @returns {void}
 */
function inside(api, popup, type, { target, key, to } = {}) {
  api.popupEvent({
    type,
    target: target ? document.getElementById(target) : popup,
    currentTarget: popup,
    key,
    relatedTarget: to ? document.getElementById(to) : null,
  });
}

test("a popover takes the focus when it opens, and says what closed it", async () => {
  const { api, popup, trigger, seen } = await popover();
  api.popupSync(popup);
  api.popupSync(null);
  expect([popup.id, trigger.getAttribute("popovertarget")]).toEqual([
    "rx-panel-1",
    "rx-panel-1",
  ]);
  expect(document.getElementById("close")?.getAttribute("popovertarget")).toBe(
    "rx-panel-1",
  );

  popup.showPopover();
  expect(document.activeElement).toBe(popup);
  expect(said(trigger)).toEqual(["true", "open"]);
  inside(api, popup, "keydown", { target: "field", key: "a" });
  inside(api, popup, "keydown", { target: "field", key: "Escape" });
  popup.hidePopover();

  popup.showPopover();
  inside(api, popup, "click", { target: "field" });
  inside(api, popup, "click", { target: "close-text" });
  popup.hidePopover();

  popup.showPopover();
  popup.hidePopover();

  expect(seen).toEqual([
    "open:true",
    "openAutoFocus",
    "escape",
    "open:false",
    "closeAutoFocus",
    "open:true",
    "openAutoFocus",
    "open:false",
    "closeAutoFocus",
    "open:true",
    "openAutoFocus",
    "outside",
    "interact",
    "open:false",
    "closeAutoFocus",
  ]);
});

test("a popover closes when the focus leaves it for the page", async () => {
  const { api, popup, seen } = await popover();
  popup.showPopover();
  inside(api, popup, "blur", { target: "field", to: "close" });
  inside(api, popup, "blur", { target: "field", to: "open" });
  inside(api, popup, "blur", { target: "field" });
  expect(popup.matches(":popover-open")).toBe(true);
  // A press outside is left to the browser.
  const beside = /** @type {HTMLElement} */ (document.getElementById("beside"));
  const matches = beside.matches.bind(beside);
  beside.matches = (selector) => selector === ":active" || matches(selector);
  inside(api, popup, "blur", { target: "field", to: "beside" });
  expect(popup.matches(":popover-open")).toBe(true);
  beside.matches = matches;
  inside(api, popup, "blur", { target: "field", to: "beside" });
  expect(popup.matches(":popover-open")).toBe(false);
  expect(seen).toEqual([
    "open:true",
    "openAutoFocus",
    "focusOutside",
    "interact",
    "open:false",
    "closeAutoFocus",
  ]);
});

test("a popover bound to state shows its state, and one that starts open opens once", async () => {
  const { api, popup, seen } = await popover('data-default-open="true"');
  api.popupSync(popup);
  expect(popup.matches(":popover-open")).toBe(true);
  expect(popup.hasAttribute("data-default-open")).toBe(false);
  api.popupSync(popup, false);
  api.popupSync(popup, false);
  expect(popup.matches(":popover-open")).toBe(false);
  api.popupSync(popup);
  expect(popup.matches(":popover-open")).toBe(false);
  api.popupSync(popup, true);
  expect(popup.matches(":popover-open")).toBe(true);
  expect(seen).toEqual(["openAutoFocus", "closeAutoFocus", "openAutoFocus"]);
});

test("a popover without handlers, and the toggle of a popup inside it, change nothing", async () => {
  installPopover();
  const api = await import("$/reflex-ui/behaviors/popup.js");
  document.body.innerHTML = `<button id="open" popovertarget="mine"></button><div popover id="mine" tabindex="-1"><div popover id="inner"></div></div>`;
  const popup = /** @type {HTMLElement} */ (document.getElementById("mine"));
  api.popupSync(popup);
  expect(popup.id).toBe("mine");
  api.popupEvent({
    type: "toggle",
    target: popup,
    currentTarget: popup,
    newState: "open",
  });
  expect(document.activeElement).toBe(popup);
  api.popupEvent({
    type: "toggle",
    target: document.getElementById("inner"),
    currentTarget: popup,
    newState: "closed",
  });
  expect(
    said(/** @type {HTMLElement} */ (document.getElementById("open"))),
  ).toEqual(["true", "open"]);
  api.popupEvent({
    type: "toggle",
    target: popup,
    currentTarget: popup,
    newState: "closed",
  });
  api.popupEvent({ type: "click", target: null, currentTarget: popup });
});
