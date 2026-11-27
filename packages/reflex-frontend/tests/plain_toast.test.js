/**
 * The plain notice a build without the toaster shows toasts with: what a call
 * puts on the page, and what takes it off again.
 */
import { afterEach, beforeEach, expect, test, vi } from "vitest";

let plainToast;
let warn;

beforeEach(async () => {
  vi.resetModules();
  vi.useFakeTimers();
  warn = vi.spyOn(console, "warn").mockImplementation(() => {});
  ({ default: plainToast } = await import("$/utils/helpers/plain_toast"));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  document.body.replaceChildren();
});

/** The notices on the page: where each is, its role and its text. */
const notices = () =>
  [...document.querySelectorAll("[id^=reflex-plain-toasts-] > div")].map(
    (notice) => [
      notice.parentElement.id,
      notice.getAttribute("role"),
      [...notice.children].map((child) => child.textContent),
    ],
  );

test("a toast shows its message and description, then closes itself", () => {
  const closed = [];
  const id = plainToast("Saved", {
    description: "All changes are stored.",
    onAutoClose: (toast) => closed.push(toast),
  });

  expect(id).toBe(1);
  expect(notices()).toEqual([
    [
      "reflex-plain-toasts-bottom-right",
      "status",
      ["Saved", "All changes are stored."],
    ],
  ]);
  vi.advanceTimersByTime(3999);
  expect(notices().length).toBe(1);
  vi.advanceTimersByTime(1);
  expect(notices()).toEqual([]);
  expect(closed).toEqual([{ id: 1, title: "Saved" }]);
});

test("the level sets the role and the accent, and the position the stack", () => {
  plainToast.error("Failed", { position: "top-center" });
  plainToast.success("", { title: "Done", duration: 100 });

  expect(notices()).toEqual([
    ["reflex-plain-toasts-top-center", "alert", ["Failed"]],
    ["reflex-plain-toasts-bottom-right", "status", ["Done"]],
  ]);
  const [failed, done] = document.querySelectorAll(
    "[id^=reflex-plain-toasts-] > div",
  );
  expect(failed.style.borderLeft).toBe("4px solid rgb(229, 72, 77)");
  expect(done.style.borderLeft).toBe("4px solid rgb(48, 164, 108)");
  expect(failed.parentElement.style.top).toBe("0px");
  expect(failed.parentElement.style.left).toBe("50%");
  expect(done.parentElement.style.bottom).toBe("0px");
  expect(done.parentElement.style.right).toBe("0px");
});

test("a toast with the id of one on the page replaces it, and dismiss removes it", () => {
  plainToast.error("Cannot connect to server: timeout.", {
    id: "websocket-error",
    duration: 120000,
  });
  plainToast.error("Cannot connect to server: refused.", {
    id: "websocket-error",
    duration: 120000,
  });
  plainToast.loading("Working");
  expect(notices()).toEqual([
    [
      "reflex-plain-toasts-bottom-right",
      "alert",
      ["Cannot connect to server: refused."],
    ],
    ["reflex-plain-toasts-bottom-right", "status", ["Working"]],
  ]);

  plainToast.dismiss("websocket-error");
  plainToast.dismiss("no-such-toast");
  // A loading toast stays until it is replaced or dismissed.
  vi.advanceTimersByTime(600000);
  expect(notices()).toEqual([
    ["reflex-plain-toasts-bottom-right", "status", ["Working"]],
  ]);
  plainToast.dismiss();
  expect(notices()).toEqual([]);
});

test("the close button and an action close the toast and report it", () => {
  const dismissed = [];
  const clicked = vi.fn();
  plainToast.info("Update ready", {
    id: "update",
    duration: Infinity,
    closeButton: true,
    action: { label: "Reload", onClick: clicked },
    onDismiss: (toast) => dismissed.push(toast),
  });
  expect(notices()).toEqual([
    [
      "reflex-plain-toasts-bottom-right",
      "status",
      ["Update ready", "Reload", "×"],
    ],
  ]);
  vi.advanceTimersByTime(600000);

  const [reload, close] = document.querySelectorAll("button");
  close.click();
  expect(notices()).toEqual([]);
  expect(clicked).not.toHaveBeenCalled();

  plainToast.info("Update ready", {
    id: "update",
    action: { label: "Reload", onClick: clicked },
    onDismiss: (toast) => dismissed.push(toast),
  });
  document.querySelector("button").click();
  expect(reload.isConnected).toBe(false);
  expect(clicked).toHaveBeenCalledTimes(1);
  expect(notices()).toEqual([]);
  expect(dismissed).toEqual([
    { id: "update", title: "Update ready" },
    { id: "update", title: "Update ready" },
  ]);
});

test("the first toast says once why it is plain", () => {
  plainToast("one");
  plainToast("two");
  expect(warn.mock.calls).toEqual([
    [
      "The toaster is not part of this build, because no use of rx.toast was " +
        "found when the app was compiled, so a plain notice is shown instead. " +
        "Pass toaster=rx.toast.provider() to rx.App to include it.",
    ],
  ]);
});
