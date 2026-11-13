```python exec
import reflex as rx
```

# Forms

Forms are a common way to gather information from users. Below are some examples.

For more details, see the [form docs page](/docs/library/forms/form/).

## Event creation

```python demo exec
def form_field(label: str, placeholder: str, type: str, name: str) -> rx.Component:
    return rx.form.field(
        rx.flex(
            rx.form.label(label),
            rx.form.control(
                rx.input(placeholder=placeholder, type=type),
                as_child=True,
            ),
            direction="column",
            spacing="1",
        ),
        name=name,
        width="100%",
    )


def event_form() -> rx.Component:
    return rx.card(
        rx.flex(
            rx.hstack(
                rx.badge(
                    rx.icon(tag="calendar-plus", size=32),
                    color_scheme="mint",
                    radius="full",
                    padding="0.65rem",
                ),
                rx.vstack(
                    rx.heading("Create an event", as_="h2", size="4", weight="bold"),
                    rx.text("Fill the form to create a custom event", size="2"),
                    spacing="1",
                    height="100%",
                    align_items="start",
                ),
                height="100%",
                spacing="4",
                align_items="center",
                width="100%",
            ),
            rx.form.root(
                rx.flex(
                    form_field("Event Name", "Event Name", "text", "event_name"),
                    rx.flex(
                        form_field("Date", "", "date", "event_date"),
                        form_field("Time", "", "time", "event_time"),
                        spacing="3",
                        flex_direction="row",
                    ),
                    form_field("Description", "Optional", "text", "description"),
                    direction="column",
                    spacing="2",
                ),
                rx.form.submit(
                    rx.button("Create"),
                    as_child=True,
                    width="100%",
                ),
                on_submit=lambda form_data: rx.window_alert(form_data.to_string()),
                reset_on_submit=False,
            ),
            width="100%",
            direction="column",
            spacing="4",
        ),
        size="3",
    )
```

```python test
def test_event_form_alerts_submitted_data(page, demo):
    expect(demo.get_by_role("heading")).to_have_text("Create an event")
    demo.get_by_role("textbox", name="Event Name").fill("Launch")
    demo.get_by_role("textbox", name="Date").fill("2024-05-01")
    demo.get_by_role("textbox", name="Time").fill("09:30")
    page.once("dialog", lambda dialog: dialog.dismiss())
    with page.expect_event("dialog") as dialog_info:
        demo.get_by_role("button", name="Create").click()
    assert dialog_info.value.message == (
        '{"event_name":"Launch","event_date":"2024-05-01",'
        '"event_time":"09:30","description":""}'
    )
```

## Contact

```python demo exec
def form_field(label: str, placeholder: str, type: str, name: str) -> rx.Component:
    return rx.form.field(
        rx.flex(
            rx.form.label(label),
            rx.form.control(
                rx.input(placeholder=placeholder, type=type),
                as_child=True,
            ),
            direction="column",
            spacing="1",
        ),
        name=name,
        width="100%",
    )


def contact_form() -> rx.Component:
    return rx.card(
        rx.flex(
            rx.hstack(
                rx.badge(
                    rx.icon(tag="mail-plus", size=32),
                    color_scheme="blue",
                    radius="full",
                    padding="0.65rem",
                ),
                rx.vstack(
                    rx.heading("Send us a message", as_="h2", size="4", weight="bold"),
                    rx.text("Fill the form to contact us", size="2"),
                    spacing="1",
                    height="100%",
                ),
                height="100%",
                spacing="4",
                align_items="center",
                width="100%",
            ),
            rx.form.root(
                rx.flex(
                    rx.flex(
                        form_field("First Name", "First Name", "text", "first_name"),
                        form_field("Last Name", "Last Name", "text", "last_name"),
                        spacing="3",
                        flex_direction=["column", "row", "row"],
                    ),
                    rx.flex(
                        form_field("Email", "user@reflex.dev", "email", "email"),
                        form_field("Phone", "Phone", "tel", "phone"),
                        spacing="3",
                        flex_direction=["column", "row", "row"],
                    ),
                    rx.flex(
                        rx.text(
                            "Message",
                            style={
                                "font-size": "15px",
                                "font-weight": "500",
                                "line-height": "35px",
                            },
                        ),
                        rx.text_area(
                            placeholder="Message",
                            name="message",
                            resize="vertical",
                        ),
                        direction="column",
                        spacing="1",
                    ),
                    rx.form.submit(
                        rx.button("Submit"),
                        as_child=True,
                    ),
                    direction="column",
                    spacing="2",
                    width="100%",
                ),
                on_submit=lambda form_data: rx.window_alert(form_data.to_string()),
                reset_on_submit=False,
            ),
            width="100%",
            direction="column",
            spacing="4",
        ),
        size="3",
    )
```

```python test
def test_contact_form_alerts_submitted_data(page, demo):
    expect(demo.get_by_role("heading")).to_have_text("Send us a message")
    demo.get_by_role("textbox", name="First Name").fill("Ada")
    demo.get_by_role("textbox", name="Email").fill("ada@reflex.dev")
    demo.get_by_role("textbox", name="Message").fill("Hello")
    page.once("dialog", lambda dialog: dialog.dismiss())
    with page.expect_event("dialog") as dialog_info:
        demo.get_by_role("button", name="Submit").click()
    assert dialog_info.value.message == (
        '{"first_name":"Ada","last_name":"","email":"ada@reflex.dev",'
        '"phone":"","message":"Hello"}'
    )
```
