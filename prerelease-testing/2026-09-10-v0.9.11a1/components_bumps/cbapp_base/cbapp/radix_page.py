"""Radix primitives: accordion 1.2.20, dialog 1.1.23, form 0.1.16."""

import reflex as rx


class RadixState(rx.State):
    """State for the radix page."""

    acc_value: str = "item-1"
    acc_multi: list[str] = ["m1"]
    dialog_open: bool = False
    nested_open: bool = False
    form_dialog_open: bool = False
    submitted: dict = {}
    submit_count: int = 0
    email_invalid: bool = False
    form_in_dialog_submitted: str = ""

    @rx.event
    def set_acc(self, value: str | list[str]):
        """Set the controlled accordion value.

        Args:
            value: The new value.
        """
        self.acc_value = value if isinstance(value, str) else (value[0] if value else "")

    @rx.event
    def open_dialog(self):
        """Open the controlled dialog."""
        self.dialog_open = True

    @rx.event
    def set_dialog_open(self, value: bool):
        """Set the controlled dialog open state.

        Args:
            value: The new open state.
        """
        self.dialog_open = value

    @rx.event
    def set_form_dialog_open(self, value: bool):
        """Set the in-dialog form dialog open state.

        Args:
            value: The new open state.
        """
        self.form_dialog_open = value

    @rx.event
    def close_dialog(self):
        """Close the controlled dialog."""
        self.dialog_open = False

    @rx.event
    def handle_submit(self, form_data: dict):
        """Handle the main form submit.

        Args:
            form_data: The submitted data.
        """
        self.submit_count += 1
        self.submitted = form_data
        self.email_invalid = "@" not in str(form_data.get("email", ""))

    @rx.event
    def handle_dialog_submit(self, form_data: dict):
        """Handle the in-dialog form submit.

        Args:
            form_data: The submitted data.
        """
        self.form_in_dialog_submitted = str(form_data.get("note", ""))
        self.form_dialog_open = False


client_open = rx._x.client_state("radix_client_dialog", default=False)


def radix_page() -> rx.Component:
    """The radix page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("radix primitives (accordion/dialog/form)", size="4"),
        rx.link("home", href="/"),
        client_open,
        rx.text("accordion single collapsible (uncontrolled)"),
        rx.accordion.root(
            rx.accordion.item(header="uncontrolled one", content="content one", value="u1"),
            rx.accordion.item(header="uncontrolled two", content="content two", value="u2"),
            type="single",
            collapsible=True,
            width="400px",
            id="acc-single",
        ),
        rx.text("accordion single controlled by state"),
        rx.accordion.root(
            rx.accordion.item(header="controlled A", content="body A", value="item-1"),
            rx.accordion.item(header="controlled B", content="body B", value="item-2"),
            type="single",
            collapsible=True,
            value=RadixState.acc_value,
            on_value_change=RadixState.set_acc,
            width="400px",
            id="acc-controlled",
        ),
        rx.text("acc value: ", rx.text.strong(RadixState.acc_value, id="acc-value")),
        rx.hstack(
            rx.button("open A", on_click=RadixState.set_acc("item-1"), id="acc-open-a"),
            rx.button("open B", on_click=RadixState.set_acc("item-2"), id="acc-open-b"),
        ),
        rx.text("accordion multiple"),
        rx.accordion.root(
            rx.accordion.item(header="multi 1", content="m body 1", value="m1"),
            rx.accordion.item(header="multi 2", content="m body 2", value="m2"),
            rx.accordion.item(header="multi 3", content="m body 3", value="m3"),
            type="multiple",
            width="400px",
            id="acc-multi",
        ),
        rx.divider(),
        rx.text("dialog controlled by state (with nested dialog)"),
        rx.hstack(
            rx.button("open state dialog", on_click=RadixState.open_dialog, id="dlg-open"),
            rx.button(
                "open client dialog",
                on_click=client_open.set_value(True),
                id="dlg-client-open",
            ),
        ),
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("state dialog"),
                rx.dialog.description("controlled by a backend state var"),
                rx.text("outer dialog body", id="dlg-body"),
                rx.dialog.root(
                    rx.dialog.trigger(rx.button("open nested", id="dlg-nested-open")),
                    rx.dialog.content(
                        rx.dialog.title("nested dialog"),
                        rx.text("nested body", id="dlg-nested-body"),
                        rx.dialog.close(rx.button("close nested", id="dlg-nested-close")),
                    ),
                ),
                rx.button("close", on_click=RadixState.close_dialog, id="dlg-close"),
            ),
            open=RadixState.dialog_open,
            on_open_change=RadixState.set_dialog_open,
        ),
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("client dialog"),
                rx.text("client-state controlled body", id="dlg-client-body"),
                rx.button("close", on_click=client_open.set_value(False), id="dlg-client-close"),
            ),
            open=client_open.value,
        ),
        rx.text("dialog with a form inside"),
        rx.dialog.root(
            rx.dialog.trigger(rx.button("open form dialog", id="dlg-form-open")),
            rx.dialog.content(
                rx.dialog.title("form dialog"),
                rx.form.root(
                    rx.form.field(
                        rx.form.label("note"),
                        rx.form.control(rx.input(name="note", id="dlg-form-note"), as_child=True),
                        name="note",
                    ),
                    rx.form.submit(rx.button("submit note", id="dlg-form-submit"), as_child=True),
                    on_submit=RadixState.handle_dialog_submit,
                    reset_on_submit=True,
                ),
            ),
            open=RadixState.form_dialog_open,
            on_open_change=RadixState.set_form_dialog_open,
        ),
        rx.text("dialog form note: ", rx.text.strong(RadixState.form_in_dialog_submitted, id="dlg-form-result")),
        rx.divider(),
        rx.text("form.root with validation"),
        rx.form.root(
            rx.form.field(
                rx.form.label("email"),
                rx.form.control(
                    rx.input(
                        name="email",
                        placeholder="you@example.com",
                        id="form-email",
                        type="email",
                        required=True,
                    ),
                    as_child=True,
                ),
                rx.form.message("email is required", match="valueMissing", id="form-msg-required"),
                rx.form.message("must be an email", match="typeMismatch", id="form-msg-type"),
                # documented server-side pattern: force_match paired with a match
                rx.form.message(
                    "rejected by the server",
                    match="typeMismatch",
                    force_match=RadixState.email_invalid,
                    id="form-msg-server",
                ),
                name="email",
                server_invalid=RadixState.email_invalid,
            ),
            rx.form.field(
                rx.form.label("nickname"),
                rx.form.control(rx.input(name="nickname", id="form-nick"), as_child=True),
                # undocumented: force_match without match (docs call this out as not working)
                rx.form.message(
                    "nickname rejected (force_match only)",
                    force_match=RadixState.email_invalid,
                    id="form-msg-nomatch",
                ),
                name="nickname",
            ),
            rx.form.field(
                rx.form.label("age"),
                rx.form.control(
                    rx.input(name="age", type="number", id="form-age"),
                    as_child=True,
                ),
                rx.form.message("too small", match="rangeUnderflow", id="form-msg-range"),
                name="age",
            ),
            rx.form.submit(rx.button("submit", id="form-submit"), as_child=True),
            on_submit=RadixState.handle_submit,
            reset_on_submit=False,
        ),
        rx.text("submit count: ", rx.text.strong(RadixState.submit_count, id="form-count")),
        rx.text("submitted: ", rx.text.strong(RadixState.submitted.to_string(), id="form-data")),
        spacing="2",
        padding="1em",
        align="start",
    )
