// What the messages of a form show of the validity of its controls: read
// on a submit and when a control is left after a change, forgotten while
// its value changes and on a reset.
import { beforeEach, expect, test } from "vitest";

import {
  changed,
  cleared,
  focusInvalid,
  invalid,
  left,
} from "$/reflex-ui/behaviors/form-validity.js";

/** @type {HTMLFormElement} */
let form;

beforeEach(() => {
  document.body.innerHTML = `
    <form>
      <div data-rx-form-field id="email-field">
        <label id="email-label">Email</label>
        <input name="email" type="email" required />
        <span data-rx-form-message data-match="valueMissing" hidden>needed</span>
        <span data-rx-form-message data-match="typeMismatch" hidden id="mine">not an email</span>
        <span data-rx-form-message>always</span>
        <span data-rx-form-message data-match="tooShort" data-force>forced</span>
      </div>
      <div data-rx-form-field data-invalid data-server-invalid id="code-field">
        <input name="code" pattern="[0-9]+" />
        <span data-rx-form-message data-match="patternMismatch" hidden>digits</span>
      </div>
      <span data-rx-form-message data-match="valueMissing" data-name="email" hidden>outside</span>
      <input name="free" />
      <button>Send</button>
    </form>`;
  form = /** @type {HTMLFormElement} */ (document.querySelector("form"));
});

/**
 * Find a control of the form.
 *
 * @param {string} name The name of the control.
 * @returns {HTMLInputElement} The control.
 */
function control(name) {
  return /** @type {HTMLInputElement} */ (form.elements.namedItem(name));
}

/**
 * Read which messages of the form show.
 *
 * @returns {(string | null)[]} The text of each one, in the order of the form.
 */
function shown() {
  return [...form.querySelectorAll("span")]
    .filter((message) => !message.hidden)
    .map((message) => message.textContent);
}

/**
 * Read which of the marks of validity an element has.
 *
 * @param {string} id The id of the element.
 * @returns {string[]} The names of the attributes.
 */
function marks(id) {
  const element = /** @type {HTMLElement} */ (document.getElementById(id));
  return ["data-valid", "data-invalid"].filter((mark) => element.hasAttribute(mark));
}

/**
 * Make the event of a control, as React hands it to the form.
 *
 * @param {EventTarget | null} target The control.
 * @returns {{ target: EventTarget | null, currentTarget: HTMLFormElement, preventDefault: () => void, prevented: boolean }}
 *   The event.
 */
function eventOf(target) {
  const event = {
    target,
    currentTarget: form,
    prevented: false,
    preventDefault: () => {
      event.prevented = true;
    },
  };
  return event;
}

test("a control found invalid shows its reasons, is described by them and takes the focus", () => {
  const email = control("email");
  const event = eventOf(email);
  invalid(event);
  expect(shown()).toEqual(["needed", "always", "forced", "outside"]);
  expect(event.prevented).toBe(true);
  expect(document.activeElement).toBe(email);
  expect(marks("email-field")).toEqual(["data-invalid"]);
  expect(marks("email-label")).toEqual(["data-invalid"]);
  expect(email.hasAttribute("data-invalid")).toBe(true);
  const described = (email.getAttribute("aria-describedby") ?? "").split(" ");
  expect(described.map((id) => document.getElementById(id)?.textContent)).toEqual([
    "needed",
    "always",
    "forced",
    "outside",
  ]);
});

test("only the first invalid control of the form takes the focus", () => {
  const code = control("code");
  code.value = "abc";
  invalid(eventOf(code));
  expect(shown()).toEqual(["always", "forced", "digits"]);
  expect(document.activeElement).toBe(document.body);
});

test("a change forgets the reasons, and leaving the control reads them again", () => {
  const email = control("email");
  invalid(eventOf(email));
  email.value = "ada";
  changed(eventOf(email));
  expect(shown()).toEqual(["always", "forced"]);
  expect(marks("email-field")).toEqual([]);
  left(eventOf(email));
  expect(shown()).toEqual(["not an email", "always", "forced"]);
  expect(email.getAttribute("aria-describedby")?.split(" ")[0]).toBe("mine");
  email.value = "ada@example.com";
  changed(eventOf(email));
  left(eventOf(email));
  expect(shown()).toEqual(["always", "forced"]);
  expect(marks("email-field")).toEqual(["data-valid"]);
});

test("a control that is left without a change keeps what it shows", () => {
  left(eventOf(control("email")));
  expect(shown()).toEqual(["always", "forced"]);
  expect(marks("email-field")).toEqual([]);
});

test("a field the server finds invalid stays marked whatever the browser says", () => {
  const code = control("code");
  code.value = "12";
  changed(eventOf(code));
  left(eventOf(code));
  expect(marks("code-field")).toEqual(["data-valid", "data-invalid"]);
  expect(code.hasAttribute("aria-describedby")).toBe(false);
});

test("a reset forgets the reasons of every control", () => {
  invalid(eventOf(control("email")));
  control("code").value = "abc";
  invalid(eventOf(control("code")));
  cleared({ currentTarget: form });
  expect(shown()).toEqual(["always", "forced"]);
  expect(marks("email-field")).toEqual([]);
  left(eventOf(control("code")));
  expect(shown()).toEqual(["always", "forced"]);
});

test("a control outside a field has the messages that name it", () => {
  const free = control("free");
  free.required = true;
  form.insertAdjacentHTML(
    "beforeend",
    '<span data-rx-form-message data-match="valueMissing" data-name="free" hidden>free</span>',
  );
  invalid(eventOf(free));
  expect(shown()).toEqual(["always", "forced", "free"]);
});

test("what is no form control is left alone", () => {
  for (const handler of [invalid, changed, left]) {
    handler(eventOf(form.querySelector("button")));
    handler(eventOf(null));
  }
  expect(shown()).toEqual(["always", "forced"]);
});

test("a field the server finds invalid gives the first invalid control the focus", () => {
  focusInvalid(document.getElementById("code-field"));
  expect(document.activeElement).toBe(control("email"));
  control("email").value = "ada@example.com";
  control("code").setAttribute("aria-invalid", "true");
  focusInvalid(document.getElementById("code-field"));
  expect(document.activeElement).toBe(control("code"));
});

test("a field that stops being invalid, or is in no form, moves no focus", () => {
  focusInvalid(null);
  focusInvalid(document.body);
  control("email").value = "ada@example.com";
  focusInvalid(document.getElementById("email-field"));
  expect(document.activeElement).toBe(document.body);
});
