"""The form: its fields, labels and messages, and what it does with validity."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix
from ui_parity.samples import wait_for_text


def _form(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a form with one field.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``control`` names what the field holds.

    Returns:
        The form.
    """
    form = namespace.form
    control = props.get("control")
    if control == "input":
        held = form.control(namespace.input(placeholder="you@example.com"))
    elif control == "area":
        held = form.control(namespace.text_area(placeholder="Say something"))
    elif control == "native":
        held = form.control(rx.el.input(placeholder="you@example.com"))
    else:
        held = form.control()
    return form.root(
        form.field(
            form.label("Email"),
            held,
            form.message("Always shown", color="gray"),
            form.message(
                "Forced", match="valueMissing", force_match=True, color="gray"
            ),
            form.message("Hidden", match="typeMismatch", color="gray"),
            name="email",
        ),
        form.submit("Send"),
    )


MATRIX = Matrix(
    component="form",
    render=_form,
    sweep={
        "control": ["input", "area", "native"],
        "appearance": [DARK],
    },
    stage=(280, 220),
    crop="stage",
    parts={
        "field": "form > div",
        "label": "label",
        "message": "form > div > span",
        "submit": "form > button",
    },
    # A field the server finds invalid gives its control the focus, which
    # only one cell of a page could have: the contract has it.
    threshold=0,
    tolerance=0,
)


class FormState(rx.State):
    """What the form of the contract is bound to."""

    taken: rx.Field[bool] = rx.field(False)
    cleared: rx.Field[int] = rx.field(0)
    submitted: rx.Field[dict[str, Any]] = rx.field(default_factory=dict)
    submissions: rx.Field[int] = rx.field(0)

    @rx.event
    def take(self):
        """Have the server find the code invalid."""
        self.taken = True

    @rx.event
    def clear(self):
        """Forget what the server found."""
        self.taken = False
        self.cleared += 1

    @rx.event
    def submit(self, data: dict[str, Any]):
        """Keep what the form submitted.

        Args:
            data: The values of the form.
        """
        self.submitted = data
        self.submissions += 1


def _contract_form(namespace: Any) -> Any:
    """Create the form of the contract.

    Args:
        namespace: ``rx`` or ``rx.ui``.

    Returns:
        The form, and what shows the state it is bound to.
    """
    form = namespace.form
    return namespace.box(
        form.root(
            form.field(
                form.label("Email"),
                form.control(namespace.input(type="email", required=True)),
                form.message("Email is needed", match="valueMissing"),
                form.message("Not an email", match="typeMismatch"),
                name="email",
                id="email-field",
            ),
            form.field(form.label("Age"), form.control(), name="age"),
            form.field(
                form.label("Code"),
                form.control(rx.el.input(pattern="[0-9]+")),
                form.message("Digits only", match="patternMismatch"),
                form.message(
                    "Taken", match="valueMissing", force_match=FormState.taken
                ),
                name="code",
                server_invalid=FormState.taken,
                id="code-field",
            ),
            form.message("Outside", match="valueMissing", name="email"),
            form.submit("Send", id="send"),
            rx.el.button("Reset", type="reset", id="reset"),
            on_submit=FormState.submit,
            on_clear_server_errors=FormState.clear,
            id="form",
        ),
        rx.el.button("Take", id="take", on_click=FormState.take),
        rx.el.span(FormState.cleared.to_string(), id="cleared"),
        rx.el.span(FormState.taken.to_string(), id="taken"),
        rx.el.span(FormState.submitted.to_string(), id="submitted"),
        rx.el.span(FormState.submissions.to_string(), id="submissions"),
    )


CONTRACT = Contract(component="form", render=_contract_form)

# The messages that show, in the order of the page.
SHOWN = (
    "[...document.querySelectorAll('#form span')]"
    ".filter(message => message.checkVisibility()).map(message => message.textContent)"
)
# The name of the control that has the focus.
FOCUSED = "document.activeElement.name"


def _wait_for_messages(run: Run, messages: list[str]) -> None:
    """Wait until the messages that show are the ones expected.

    Args:
        run: The run, on a page.
        messages: The text of each message that is to show.
    """
    run.page.wait_for_function(
        f"expected => {SHOWN}.join('|') === expected", arg="|".join(messages)
    )


def _control(run: Run, name: str) -> Any:
    """Find a control of the form by the name its field gives it.

    Args:
        run: The run, on a page.
        name: The name of the field.

    Returns:
        The control.
    """
    return run.page.locator(f"#form [name='{name}']")


@CONTRACT.step("is a form with a submit button in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    assert run.server.element("form").tag == "form"
    send = run.server.element("send")
    assert (send.tag, send.attributes["type"], send.text) == (
        "button",
        "submit",
        "Send",
    )


@CONTRACT.step(
    "a label gives its control the focus with JavaScript disabled", on=NO_JAVASCRIPT
)
def _without_javascript(run: Run) -> None:
    page = run.page
    page.get_by_text("Code", exact=True).click()
    assert page.evaluate(FOCUSED) == "code"
    page.keyboard.type("12")
    assert _control(run, "code").input_value() == "12"
    assert page.evaluate(SHOWN) == []


@CONTRACT.step("each control has the name of its field and of the label of its field")
def _role(run: Run) -> None:
    page = run.page
    for label in ("Email", "Age", "Code"):
        textbox = page.get_by_role("textbox", name=label, exact=True)
        assert textbox.get_attribute("name") == label.lower()
    assert page.get_by_role("button", name="Send").get_attribute("type") == "submit"
    assert page.evaluate(SHOWN) == []


@CONTRACT.step("a submit shows why a control is not valid, and gives it the focus")
def _invalid(run: Run) -> None:
    page = run.page
    _control(run, "age").focus()
    page.locator("#send").click()
    _wait_for_messages(run, ["Email is needed", "Outside"])
    assert page.evaluate(FOCUSED) == "email"
    assert page.locator("#submissions").text_content() == "0"
    assert page.locator("#email-field").get_attribute("data-invalid") is not None
    described = _control(run, "email").get_attribute("aria-describedby") or ""
    assert [
        page.locator(f"[id='{message}']").text_content()
        for message in described.split()
    ] == ["Email is needed", "Outside"]


@CONTRACT.step("a change forgets the reason, and leaving the control reads it again")
def _change(run: Run) -> None:
    page = run.page
    page.locator("#send").click()
    _wait_for_messages(run, ["Email is needed", "Outside"])
    page.keyboard.type("ada")
    _wait_for_messages(run, [])
    assert page.locator("#email-field").get_attribute("data-invalid") is None
    page.keyboard.press("Tab")
    _wait_for_messages(run, ["Not an email"])
    _control(run, "email").fill("ada@example.com")
    page.keyboard.press("Tab")
    _wait_for_messages(run, [])
    assert page.locator("#email-field").get_attribute("data-valid") is not None


@CONTRACT.step("a pattern that does not match is a reason too")
def _pattern(run: Run) -> None:
    page = run.page
    _control(run, "email").fill("ada@example.com")
    _control(run, "code").fill("abc")
    page.keyboard.press("Enter")
    _wait_for_messages(run, ["Digits only"])
    assert page.evaluate(FOCUSED) == "code"
    assert page.locator("#submissions").text_content() == "0"


@CONTRACT.step("a reset forgets every reason")
def _reset(run: Run) -> None:
    page = run.page
    page.locator("#send").click()
    _wait_for_messages(run, ["Email is needed", "Outside"])
    page.locator("#reset").click()
    _wait_for_messages(run, [])
    assert page.locator("#email-field").get_attribute("data-invalid") is None


@CONTRACT.step("submits the values of its controls by the names of their fields")
def _submit(run: Run) -> None:
    page = run.page
    _control(run, "email").fill("ada@example.com")
    _control(run, "age").fill("36")
    _control(run, "code").fill("123")
    page.keyboard.press("Enter")
    wait_for_text(page, "submissions", "1")
    assert page.locator("#submitted").text_content() == (
        '{"email":"ada@example.com","age":"36","code":"123"}'
    )
    assert page.evaluate(SHOWN) == []


@CONTRACT.step(
    "a field the server finds invalid says so, with the focus, until a reset"
)
def _server_invalid(run: Run) -> None:
    page = run.page
    _control(run, "email").fill("ada@example.com")
    page.locator("#take").click()
    wait_for_text(page, "taken", "true")
    _wait_for_messages(run, ["Taken"])
    assert _control(run, "code").get_attribute("aria-invalid") == "true"
    assert page.locator("#code-field").get_attribute("data-invalid") is not None
    page.wait_for_function(f"{FOCUSED} === 'code'")
    page.keyboard.type("1")
    assert page.locator("#cleared").text_content() == "0"
    page.locator("#reset").click()
    wait_for_text(page, "cleared", "1")
    wait_for_text(page, "taken", "false")
    _wait_for_messages(run, [])
    assert _control(run, "code").get_attribute("aria-invalid") is None
