// What a dialog does with a press on its trigger, on a button that closes
// it and beside its panel, with Escape, and with the state it is bound to.
import { beforeEach, expect, test } from "vitest";

import {
  dialogClick,
  dialogEvent,
  dialogSync,
} from "$/reflex-ui/behaviors/dialog.js";

// What jsdom has of a modal dialog: the attribute. These open and close
// one as a browser does, and send the event a browser sends.
HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
HTMLDialogElement.prototype.close = function () {
  if (!this.open) return;
  this.open = false;
  dialogEvent({
    type: "close",
    target: this,
    currentTarget: this,
    preventDefault: () => {},
  });
};

/** @type {HTMLElement} */
let root;
/** @type {HTMLDialogElement} */
let dialog;

/**
 * Render a dialog with a dialog of its own inside its panel.
 *
 * @param {string} [attributes] The attributes of the dialog.
 * @returns {void}
 */
function render(attributes = "") {
  document.body.innerHTML = `
    <div id="root" data-rx-dialog-root>
      <button id="open" data-rx-dialog-trigger aria-expanded="false" data-state="closed"><span id="open-text">Open</span></button>
      <dialog id="dialog" ${attributes}>
        <div id="pad">
          <div id="panel">
            <button id="close" data-rx-dialog-close>Close</button>
            <div id="inner-root" data-rx-dialog-root>
              <button id="inner-open" data-rx-dialog-trigger aria-expanded="false">Inner</button>
              <dialog id="inner"><div id="inner-pad"><button id="inner-close" data-rx-dialog-close>Back</button></div></dialog>
            </div>
          </div>
        </div>
      </dialog>
    </div>
    <button id="elsewhere">Elsewhere</button>`;
  root = /** @type {HTMLElement} */ (document.getElementById("root"));
  dialog = /** @type {HTMLDialogElement} */ (document.getElementById("dialog"));
}

beforeEach(() => render());

/**
 * Make the handlers of a dialog, which keep what they are called with.
 *
 * @returns {{ on: Record<string, (open?: boolean) => void>, seen: string[] }}
 *   The handlers, and what was called, in order.
 */
function handlers() {
  /** @type {string[]} */
  const seen = [];
  const on = Object.fromEntries(
    [
      "open",
      "openAutoFocus",
      "closeAutoFocus",
      "escape",
      "outside",
      "interact",
    ].map((name) => [
      name,
      (/** @type {boolean | undefined} */ open) =>
        seen.push(open === undefined ? name : `${name}:${open}`),
    ]),
  );
  return { on, seen };
}

/**
 * Press an element, as the element around the dialog hears it.
 *
 * @param {string | null} id The id of the element, or null for no element.
 * @param {HTMLElement} [around] The element that hears the press.
 * @returns {boolean} Whether the dialog kept the press from the browser.
 */
function press(id, around = root) {
  let prevented = false;
  dialogClick({
    target: id ? document.getElementById(id) : null,
    currentTarget: around,
    preventDefault: () => {
      prevented = true;
    },
  });
  return prevented;
}

/**
 * Press Escape in a dialog, as the dialog hears it.
 *
 * @param {HTMLDialogElement} [target] The dialog the key is pressed in.
 * @returns {boolean} Whether the dialog kept the browser from closing it.
 */
function escape(target = dialog) {
  let prevented = false;
  dialogEvent({
    type: "cancel",
    target,
    currentTarget: dialog,
    preventDefault: () => {
      prevented = true;
    },
  });
  return prevented;
}

/**
 * Read what the trigger says of its dialog.
 *
 * @returns {string} Whether the dialog is open, to assistive technology
 *   and to styles.
 */
function said() {
  const trigger = /** @type {HTMLElement} */ (document.getElementById("open"));
  return `${trigger.getAttribute("aria-expanded")}:${trigger.dataset.state}`;
}

test("a press on the trigger opens the dialog, and one on its button closes it", () => {
  const { on, seen } = handlers();
  dialogSync(dialog, null, on);
  dialog.scrollTop = 40;
  expect(press("open-text")).toBe(true);
  expect([dialog.open, dialog.scrollTop, said()]).toEqual([
    true,
    0,
    "true:open",
  ]);
  expect(
    document.getElementById("inner-open")?.getAttribute("aria-expanded"),
  ).toBe("false");
  expect(press("close")).toBe(true);
  expect([dialog.open, said()]).toEqual([false, "false:closed"]);
  expect(seen).toEqual([
    "open:true",
    "openAutoFocus",
    "open:false",
    "closeAutoFocus",
  ]);
});

test("a dialog without handlers opens and closes all the same", () => {
  press("open");
  expect(dialog.open).toBe(true);
  expect(escape()).toBe(true);
  expect(dialog.open).toBe(false);
  dialogSync(dialog);
  press("open");
  expect(dialog.open).toBe(true);
});

test("a press beside the panel and Escape dismiss the dialog, and say what did", () => {
  const { on, seen } = handlers();
  dialogSync(dialog, null, on);
  press("open");
  expect(press("panel")).toBe(false);
  expect(dialog.open).toBe(true);
  expect(press("pad")).toBe(false);
  expect(dialog.open).toBe(false);
  press("open");
  press("dialog");
  expect(dialog.open).toBe(false);
  press("open");
  expect(escape()).toBe(true);
  expect(dialog.open).toBe(false);
  expect(seen).toEqual([
    "open:true",
    "openAutoFocus",
    "outside",
    "interact",
    "open:false",
    "closeAutoFocus",
    "open:true",
    "openAutoFocus",
    "outside",
    "interact",
    "open:false",
    "closeAutoFocus",
    "open:true",
    "openAutoFocus",
    "escape",
    "open:false",
    "closeAutoFocus",
  ]);
});

test("a press beside the panel of an alert dialog does not dismiss it", () => {
  render('role="alertdialog"');
  press("open");
  press("pad");
  press("dialog");
  expect(dialog.open).toBe(true);
  expect(escape()).toBe(true);
  expect(dialog.open).toBe(false);
});

test("a dialog bound to state says what is asked of it, and shows its state", () => {
  const { on, seen } = handlers();
  dialogSync(dialog, false, on);
  expect(press("open")).toBe(true);
  expect(dialog.open).toBe(false);
  dialogSync(dialog, true, on);
  expect([dialog.open, said()]).toEqual([true, "true:open"]);
  dialogSync(dialog, true, on);
  expect(escape()).toBe(true);
  press("close");
  press("pad");
  expect(dialog.open).toBe(true);
  dialogSync(dialog, false, on);
  expect([dialog.open, said()]).toEqual([false, "false:closed"]);
  expect(seen).toEqual([
    "open:true",
    "openAutoFocus",
    "escape",
    "open:false",
    "open:false",
    "outside",
    "interact",
    "open:false",
    "closeAutoFocus",
  ]);
});

test("a dialog that starts open opens once", () => {
  render('data-default-open="true"');
  const { on, seen } = handlers();
  dialogSync(dialog, null, on);
  expect(dialog.open).toBe(true);
  press("close");
  dialogSync(dialog, null, on);
  expect(dialog.open).toBe(false);
  expect(seen).toEqual(["openAutoFocus", "open:false", "closeAutoFocus"]);
  dialogSync(null);
});

test("the dialog inside a dialog is its own", () => {
  const inner = /** @type {HTMLDialogElement} */ (
    document.getElementById("inner")
  );
  const innerRoot = /** @type {HTMLElement} */ (
    document.getElementById("inner-root")
  );
  press("open");
  // The press on what opens the inner dialog reaches both elements.
  press("inner-open", innerRoot);
  press("inner-open");
  expect([dialog.open, inner.open]).toEqual([true, true]);
  expect(escape(inner)).toBe(false);
  press("inner-pad");
  press("inner-close");
  expect([dialog.open, inner.open]).toEqual([true, true]);
  press("inner-close", innerRoot);
  expect([dialog.open, inner.open, said()]).toEqual([true, false, "true:open"]);
});

test("a press on anything else is left alone", () => {
  expect(press(null)).toBe(false);
  expect(press("elsewhere")).toBe(false);
  dialog.remove();
  expect(press("open")).toBe(false);
});
