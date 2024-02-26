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
rx.button('Log', on_click=rx.console_log('Hello World!'))
```

When triggered, this event logs a specified message to the browser's developer console.
It's useful for debugging and monitoring the behavior of your application.

## rx.redirect

Redirect the user to a new path within the application.

### Parameters

- `path`: The destination path or URL to which the user should be redirected.
- `external`: If set to True, the redirection will open in a new tab. Defaults to `False`.

```python demo
rx.vstack(
    rx.button("open in tab", on_click=rx.redirect("/docs/api-reference/special-events")),
    rx.button("open in new tab", on_click=rx.redirect('https://github.com/reflex-dev/reflex/', external=True))
)
```

When this event is triggered, it navigates the user to a different page or location within your Reflex application.
By default, the redirection occurs in the same tab. However, if you set the external parameter to True, the redirection
will open in a new tab or window, providing a seamless user experience.

## rx.set_clipboard

Set the specified text content to the clipboard.

```python demo
rx.button('Copy "Hello World" to clipboard',on_click=rx.set_clipboard('Hello World'),)
```

This event allows you to copy a given text or content to the user's clipboard.
It's handy when you want to provide a "Copy to Clipboard" feature in your application,
allowing users to easily copy information to paste elsewhere.

## rx.set_value

Set the value of a specified reference element.

```python demo
rx.hstack(
    rx.chakra.input(id='input1'),
    rx.button(
        'Erase', on_click=rx.set_value('input1', '')
    ),
)
```

With this event, you can modify the value of a particular HTML element, typically an input field or another form element.

## rx.window_alert

Create a window alert in the browser.

```python demo
rx.button('Alert', on_click=rx.window_alert('Hello World!'))
```

## rx.download

Download a file at a given path.

Parameters:

- `url`: The URL of the file to be downloaded.
- `data`: The data to be downloaded. Should be `str` or `bytes`, `data:` URI, `PIL.Image`, or any state Var (to be converted to JSON).
- `filename`: The desired filename of the downloaded file.

```md alert
`url` and `data` args are mutually exclusive, and at least one of them must be provided.
```

```python demo
rx.button("Download", on_click=rx.download(url="/reflex_banner.png", filename="different_name_logo.png"))
```
