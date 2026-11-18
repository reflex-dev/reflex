---
components:
  - rx.input

TextFieldRoot: |
  lambda **props: rx.input(placeholder="Search the docs", **props)

TextFieldSlot: |
  lambda **props: rx.input(
      rx.input.slot(
          rx.icon(tag="search", height="16", width="16"),
          **props,
      ),
      placeholder="Search the docs",
  )
---

```python exec
import reflex as rx
```

# Input

The `input` component is an input field that users can type into.

```md video https://youtube.com/embed/ITOZkzjtjUA?start=1517&end=1869
# Video: Input
```

## Basic Example

The `on_blur` event handler is called when focus has left the `input` for example, it’s called when the user clicks outside of a focused text input.

```python demo exec
class TextfieldBlur(rx.State):
    text: str = "Hello World!"

    @rx.event
    def set_text(self, value: str):
        self.text = value


def blur_example():
    return rx.vstack(
        rx.heading(TextfieldBlur.text, as_="h2"),
        rx.input(
            placeholder="Search here...",
            on_blur=TextfieldBlur.set_text,
        ),
    )
```

```python test
def test_input_sets_text_on_blur(demo):
    heading = demo.get_by_role("heading")
    expect(heading).to_have_text("Hello World!")
    textbox = demo.get_by_placeholder("Search here...")
    textbox.fill("Blurred")
    expect(heading).to_have_text("Hello World!")
    textbox.blur()
    expect(heading).to_have_text("Blurred")
```

The `on_change` event handler is called when the `value` of `input` has changed.

```python demo exec
class TextfieldControlled(rx.State):
    text: str = "Hello World!"

    @rx.event
    def set_text(self, value: str):
        self.text = value


def controlled_example():
    return rx.vstack(
        rx.heading(TextfieldControlled.text, as_="h2"),
        rx.input(
            placeholder="Search here...",
            value=TextfieldControlled.text,
            on_change=TextfieldControlled.set_text,
        ),
    )
```

```python test
def test_debounced_controlled_input(demo):
    textbox = demo.get_by_placeholder("Search here...")
    expect(textbox).to_have_value("Hello World!")
    textbox.fill("Debounced")
    expect(demo.get_by_role("heading")).to_have_text("Debounced")
```

Behind the scenes, the input component is implemented as a debounced input to avoid sending individual state updates per character to the backend while the user is still typing. This allows a state variable to directly control the `value` prop from the backend without the user experiencing input lag.

## Input Types

The `type` prop controls how the input is rendered (e.g. plain text, password, file picker).

It accepts the same values as the native HTML `<input type>` attribute, such as:

- `"text"` (default)
- `"password"`
- `"email"`
- `"number"`
- `"file"`
- `"checkbox"`
- `"radio"`
- `"date"`
- `"time"`
- `"url"`
- `"color"`

and several others. See the [MDN reference](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input#input_types) for the full list.

```python demo
rx.vstack(
    rx.input(placeholder="Username", type="text"),
    rx.input(placeholder="Password", type="password"),
    rx.input(type="date"),
)
```

```python test
def test_input_types(demo):
    expect(demo.get_by_placeholder("Username")).to_have_attribute("type", "text")
    expect(demo.get_by_placeholder("Password")).to_have_attribute("type", "password")
    expect(demo.locator("input[type=date]")).to_have_count(1)
```

## Submitting a form using input

The `name` prop is needed to submit with its owning form as part of a name/value pair.

When the `required` prop is `True`, it indicates that the user must input text before the owning form can be submitted.

The `type` is set here to `password`. The element is presented as a one-line plain text editor control in which the text is obscured so that it cannot be read. The `type` prop can take any value of `email`, `file`, `password`, `text` and several others. Learn more in the [HTML input reference](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input).

```python demo exec
class FormInputState(rx.State):
    form_data: dict = {}

    @rx.event
    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def form_input1():
    return rx.card(
        rx.vstack(
            rx.heading("Example Form", as_="h2"),
            rx.form.root(
                rx.hstack(
                    rx.input(
                        name="input",
                        placeholder="Enter text...",
                        type="text",
                        required=True,
                    ),
                    rx.button("Submit", type="submit"),
                    width="100%",
                ),
                on_submit=FormInputState.handle_submit,
                reset_on_submit=True,
            ),
            rx.divider(),
            rx.hstack(
                rx.heading("Results:", as_="h2"),
                rx.badge(FormInputState.form_data.to_string()),
            ),
            align_items="left",
            width="100%",
        ),
        width="50%",
    )
```

```python test
def test_required_input_form(demo):
    results = demo.locator(".rt-Badge")
    textbox = demo.get_by_placeholder("Enter text...")
    submit = demo.get_by_role("button", name="Submit")
    submit.click()
    expect(textbox).to_have_js_property("validity.valueMissing", True)
    expect(results).to_have_text("{}")
    textbox.fill("hello")
    submit.click()
    expect(results).to_have_text('{"input":"hello"}')
    expect(textbox).to_have_value("")
```

To learn more about how to use forms in the [Form](/docs/library/forms/form/) docs.

## Setting a value without using a State var

Set the value of the specified reference element, without needing to link it up to a State var. This is an alternate way to modify the value of the `input`.

```python demo
rx.hstack(
    rx.input(id="input1"),
    rx.button("Erase", on_click=rx.set_value("input1", "")),
)
```

```python test
def test_set_value_erases_input(demo):
    textbox = demo.get_by_role("textbox")
    textbox.fill("to be erased")
    demo.get_by_role("button", name="Erase").click()
    expect(textbox).to_have_value("")
```
