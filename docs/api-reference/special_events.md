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

When triggered, this event logs a specified message to the browser's developer console.
It's useful for debugging and monitoring the behavior of your application.

## rx.scroll_to

scroll to an element in the page

```python demo
rx.button("Scroll to download button", on_click=rx.scroll_to("download button"))
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

## rx.set_clipboard

Set the specified text content to the clipboard.

```python demo
rx.button(
    'Copy "Hello World" to clipboard',
    on_click=rx.set_clipboard("Hello World"),
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

### Copying text fetched from a URL

Pass the `url` keyword to copy text that the browser fetches from a URL:

```python
rx.button(
    "Copy the example file",
    on_click=rx.set_clipboard(url="/example.txt"),
)
```

The fetch runs in the browser, so the URL is resolved by the browser. A
relative path like `/example.txt` is served by your app. Cross-origin URLs
must allow the fetch through CORS, and the fetch uses the default
credentials mode.

This form has a stricter usage contract than the text form:

- The page must be in a secure context (HTTPS or localhost), and the
  browser must grant clipboard access.
- Call it as the direct, first or sole event of a user gesture trigger
  such as `on_click`. Backend round trips and timers drop the gesture's
  transient activation, and the copy can then fail or never settle. A
  throttled trigger keeps activation only on its leading edge; dropped
  events never run.
- Events returned from a backend event handler are not supported with
  `url`. Delivering the event through the backend loses the user gesture,
  so the write may be denied or stay pending without an error signal.
- The response must be text. Accepted content types are `text/*`,
  `application/json`, `application/javascript`, `application/xml`,
  `application/yaml`, `application/x-yaml`,
  `application/x-www-form-urlencoded`, and any `+json`, `+xml`, or `+yaml`
  suffix type. `text/html` and `application/xhtml+xml` are refused, as is
  any other type. The body is read as UTF-8 text.
- The write path is chosen by capability presence at runtime, not by
  version. When `ClipboardItem` and `navigator.clipboard.write` are both
  present, the write is armed with a promise-backed item so it stays
  bound to the gesture. Arming a promise-valued item requires Chrome 98+,
  Firefox 127+, or Safari 13.1+ per browser compatibility data. Browsers
  below that floor still expose the `ClipboardItem` interface (for
  example Chrome 76 through 97), so they take the promise-backed branch
  and the constructor or write fails there; that failure is tagged and
  reported like any other write failure. This below-floor behavior is
  inferred from the specification and is not separately verified. Only
  when `ClipboardItem` or `navigator.clipboard.write` is actually absent
  does a `writeText` fallback run after the fetch resolves, which no
  longer binds the write to the gesture and can be denied.

Failures are reported, never silent: a failed fetch (an HTTP error or a
refused content type) or a failed write logs a tagged
`_set_clipboard_from_url` console error and raises an unhandled
rejection, which Reflex forwards to the backend as a frontend exception
report. When the fetch fails, the clipboard content stays unchanged. If
the write itself fails for a different reason than the fetch (for
example a permission denial), it is reported as its own failure; the
exact error identity behavior is engine-dependent, and Firefox reports a
distinct, less specific error for fetch refusals.

Two rapid clicks race: in Chromium an earlier fetch can finish last and
overwrite a newer copy, while Firefox rejects the concurrent write. Do
not rely on last-click-wins ordering.

## rx.set_value

Set the value of a specified reference element.

```python demo
rx.hstack(
    rx.input(id="input1"),
    rx.button("Erase", on_click=rx.set_value("input1", "")),
)
```

With this event, you can modify the value of a particular HTML element, typically an input field or another form element.

## rx.window_alert

Create a window alert in the browser.

```python demo
rx.button("Alert", on_click=rx.window_alert("Hello World!"))
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
