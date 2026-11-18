```python exec
import reflex as rx
```

# Special Events

Reflex includes a set of built-in special events that can be utilized as event triggers
or returned from event handlers in your applications. These events enhance interactivity and user experience.
Below are the special events available in Reflex, along with explanations of their functionality:

## rx.console_log

Perform a console.log in the browser's console.

```python demo
rx.button("Log", on_click=rx.console_log("Hello World!"))
```

```python test
def test_console_log(demo, page):
    with page.expect_console_message(lambda m: m.text == "Hello World!"):
        demo.get_by_role("button", name="Log").click()
```

When triggered, this event logs a specified message to the browser's developer console.
It's useful for debugging and monitoring the behavior of your application.

## rx.scroll_to

scroll to an element in the page

```python demo
rx.button("Scroll to download button", on_click=rx.scroll_to("download button"))
```

```python test
def test_scroll_to_download_button(demo, page):
    target = page.locator('[id="download button"]')
    expect(target).not_to_be_in_viewport()
    demo.get_by_role("button", name="Scroll to download button").click()
    expect(target).to_be_in_viewport()
```

When this is triggered, it scrolls to an element passed by id as parameter. Click on button to scroll to download button (rx.download section) at the bottom of the page

To keep a container automatically scrolled to the bottom as new content is added — for example a chat or log view — use the [`rx.auto_scroll`](/docs/library/dynamic-rendering/auto-scroll/) component instead.

## rx.redirect

Redirect the user to a new path within the application.

### Parameters

- `path`: The destination path or URL to which the user should be redirected.
- `external`: If set to True, the redirection will open in a new tab. Defaults to `False`.

```python demo
rx.vstack(
    rx.button("open in tab", on_click=rx.redirect("/api-reference/special-events")),
    rx.button(
        "open in new tab",
        on_click=rx.redirect("https://github.com/reflex-dev/reflex/", is_external=True),
    ),
)
```

```python test
def test_redirect_same_and_new_tab(demo, page):
    page.context.route("https://github.com/**", lambda route: route.fulfill(body="ok"))
    with page.expect_popup() as popup:
        demo.get_by_role("button", name="open in new tab").click()
    expect(popup.value).to_have_url("https://github.com/reflex-dev/reflex/")
    expect(page).to_have_url(re.compile(r"/docs/api-reference/special-events/$"))

    demo.get_by_role("button", name="open in tab").click()
    expect(page).to_have_url(re.compile(r"/docs/api-reference/special-events/?$"))
    expect(
        page.get_by_role("heading", name="Special Events", exact=True)
    ).to_be_visible()
```

When this event is triggered, it navigates the user to a different page or location within your Reflex application.
By default, the redirection occurs in the same tab. However, if you set the external parameter to True, the redirection
will open in a new tab or window, providing a seamless user experience.

This event can also be run from an event handler in State. It is necessary to `return` the `rx.redirect()`.

```python demo exec
class RedirectExampleState(rx.State):
    """The app state."""

    @rx.event
    def change_page(self):
        return rx.redirect("https://github.com/reflex-dev/reflex/", is_external=True)


def redirect_example():
    return rx.vstack(
        rx.button("Change page in State", on_click=RedirectExampleState.change_page),
    )
```

```python test
def test_redirect_from_state(demo, page):
    page.context.route("https://github.com/**", lambda route: route.fulfill(body="ok"))
    with page.expect_popup() as popup:
        demo.get_by_role("button", name="Change page in State").click()
    expect(popup.value).to_have_url("https://github.com/reflex-dev/reflex/")
```

## rx.set_clipboard

Set the specified text content to the clipboard.

```python demo
rx.button(
    'Copy "Hello World" to clipboard',
    on_click=rx.set_clipboard("Hello World"),
)
```

```python test
def test_set_clipboard(demo, page):
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    demo.get_by_role("button", name='Copy "Hello World" to clipboard').click()
    page.wait_for_function(
        "navigator.clipboard.readText().then(t => t === 'Hello World')"
    )
```

This event allows you to copy a given text or content to the user's clipboard.
It's handy when you want to provide a "Copy to Clipboard" feature in your application,
allowing users to easily copy information to paste elsewhere.

`rx.set_clipboard` also accepts state Vars, so you can copy dynamic content,
such as the current value of an input field:

```python demo exec
class CopyState(rx.State):
    text: str = ""

    @rx.event
    def set_text(self, value: str):
        self.text = value


def copy_input_example():
    return rx.hstack(
        rx.input(
            placeholder="Type something to copy",
            value=CopyState.text,
            on_change=CopyState.set_text,
        ),
        rx.button("Copy", on_click=rx.set_clipboard(CopyState.text)),
    )
```

```python test
def test_set_clipboard_from_state_var(demo, page):
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    field = demo.get_by_placeholder("Type something to copy")
    field.fill("copied text")
    expect(field).to_have_value("copied text")
    demo.get_by_role("button", name="Copy").click()
    page.wait_for_function(
        "navigator.clipboard.readText().then(t => t === 'copied text')"
    )
```

## rx.set_value

Set the value of a specified reference element.

```python demo
rx.hstack(
    rx.input(id="input1"),
    rx.button("Erase", on_click=rx.set_value("input1", "")),
)
```

```python test
def test_set_value_erases_input(demo):
    field = demo.get_by_role("textbox")
    field.fill("some text")
    demo.get_by_role("button", name="Erase").click()
    expect(field).to_have_value("")
```

With this event, you can modify the value of a particular HTML element, typically an input field or another form element.

## rx.window_alert

Create a window alert in the browser.

```python demo
rx.button("Alert", on_click=rx.window_alert("Hello World!"))
```

```python test
def test_window_alert(demo, page):
    page.once("dialog", lambda dialog: dialog.accept())
    with page.expect_event("dialog") as alert:
        demo.get_by_role("button", name="Alert").click()
    assert alert.value.type == "alert"
    assert alert.value.message == "Hello World!"
```

## rx.download

Download a file at a given path.

Parameters:

- `url`: The URL of the file to be downloaded.
- `data`: The data to be downloaded. Should be `str` or `bytes`, `data:` URI, `PIL.Image`, or any state Var (to be converted to JSON).
- `filename`: The desired filename of the downloaded file.

```md alert
# `url` and `data` args are mutually exclusive, and at least one of them must be provided.
```

```python demo
rx.button(
    "Download",
    on_click=rx.download(
        url="/reflex_banner.webp", filename="different_name_logo.webp"
    ),
    id="download button",
)
```

```python test
def test_download_url(demo, page):
    with page.expect_download() as download:
        demo.get_by_role("button", name="Download").click()
    assert download.value.suggested_filename == "different_name_logo.webp"
```

When the data to download is not already available at a known URL, return
`rx.download` from an event handler and pass the `data` directly:

```python demo exec
import random


class DownloadState(rx.State):
    @rx.event
    def download_random_data(self):
        return rx.download(
            data=",".join([str(random.randint(0, 100)) for _ in range(10)]),
            filename="random_numbers.csv",
        )


def download_random_data_button():
    return rx.button(
        "Download random numbers",
        on_click=DownloadState.download_random_data,
    )
```

```python test
def test_download_data_from_state(demo, page):
    with page.expect_download() as download:
        demo.get_by_role("button", name="Download random numbers").click()
    assert download.value.suggested_filename == "random_numbers.csv"
    numbers = download.value.path().read_text().split(",")
    assert len(numbers) == 10
    assert all(0 <= int(n) <= 100 for n in numbers)
```
