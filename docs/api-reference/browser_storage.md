# Browser Storage

## rx.Cookie

Represents a state Var that is stored as a cookie in the browser. Currently only supports string values.

 Parameters

- `name` : The name of the cookie on the client side.
- `path`: The cookie path. Use `/` to make the cookie accessible on all pages.
- `max_age` : Relative max age of the cookie in seconds from when the client receives it.
- `domain`: Domain for the cookie (e.g., `sub.domain.com` or `.allsubdomains.com`).
- `secure`: If the cookie is only accessible through HTTPS.
- `same_site`: Whether the cookie is sent with third-party requests. Can be one of (`True`, `False`, `None`, `lax`, `strict`).

```python
class CookieState(rx.State):
    c1: str = rx.Cookie()
    c2: str = rx.Cookie('c2 default')

    # cookies with custom settings
    c3: str = rx.Cookie(max_age=2)  # expires after 2 second
    c4: str = rx.Cookie(same_site='strict')
    c5: str = rx.Cookie(path='/foo/')  # only accessible on `/foo/`
    c6: str = rx.Cookie(name='c6-custom-name')
```

## rx.remove_cookies

Remove a cookie from the client's browser.

Parameters:

- `key`: The name of cookie to remove.

```python
rx.button(
    'Remove cookie', on_click=rx.remove_cookie('key')
)
```

This event can also be returned from an event handler:

```python
class CookieState(rx.State):
    ...
    def logout(self):
        return rx.remove_cookie('auth_token')
```

## rx.LocalStorage

Represents a state Var that is stored in localStorage in the browser. Currently only supports string values.

Parameters

- `name`: The name of the storage key on the client side.

```python
class LocalStorageState(rx.State):
    # local storage with default settings
    l1: str = rx.LocalStorage()

    # local storage with custom settings
    l2: str = rx.LocalStorage("l2 default")
    l3: str = rx.LocalStorage(name="l3")
```

## rx.remove_local_storage

Remove a local storage item from the client's browser.

Parameters

- `key`: The key to remove from local storage.

```python
rx.button(
    'Remove Local Storage',
    on_click=rx.remove_local_storage('key'),
)
```

This event can also be returned from an event handler:

```python
class LocalStorageState(rx.State):
    ...
    def logout(self):
        return rx.remove_local_storage('local_storage_state.l1')
```

## rx.clear_local_storage()

Clear all local storage items from the client's browser. This may affect other
apps running in the same domain or libraries within your app that use local
storage.

```python
rx.button(
    'Clear all Local Storage',
    on_click=rx.clear_local_storage(),
)
```

# Serialization Strategies

If a non-trivial data structure should be stored in a `Cookie` or `LocalStorage` var it needs to
be serialized before and after storing it. It is recommended to use `rx.Base` for the data
which provides simple serialization helpers and works recursively in complex object structures.

```python demo exec
import reflex as rx


class AppSettings(rx.Base):
    theme: str = 'light'
    sidebar_visible: bool = True
    update_frequency: int = 60
    error_messages: list[str] = []


class ComplexLocalStorageState(rx.State):
    data_raw: str = rx.LocalStorage("{}")
    data: AppSettings = AppSettings()
    settings_open: bool = False

    def save_settings(self):
        self.data_raw = self.data.json()
        self.settings_open = False

    def open_settings(self):
        self.data = AppSettings.parse_raw(self.data_raw)
        self.settings_open = True

    def set_field(self, field, value):
        setattr(self.data, field, value)


def app_settings():
    return rx.chakra.form(
        rx.foreach(
            ComplexLocalStorageState.data.error_messages,
            rx.text,
        ),
        rx.chakra.form_label(
            "Theme",
            rx.chakra.input(
                value=ComplexLocalStorageState.data.theme,
                on_change=lambda v: ComplexLocalStorageState.set_field("theme", v),
            ),
        ),
        rx.chakra.form_label(
            "Sidebar Visible",
            rx.chakra.switch(
                is_checked=ComplexLocalStorageState.data.sidebar_visible,
                on_change=lambda v: ComplexLocalStorageState.set_field(
                    "sidebar_visible",
                    v,
                ),
            ),
        ),
        rx.chakra.form_label(
            "Update Frequency (seconds)",
            rx.chakra.number_input(
                value=ComplexLocalStorageState.data.update_frequency,
                on_change=lambda v: ComplexLocalStorageState.set_field(
                    "update_frequency",
                    v,
                ),
            ),
        ),
        rx.button("Save", type="submit"),
        on_submit=lambda _: ComplexLocalStorageState.save_settings(),
    )

def app_settings_example():
    return rx.fragment(
        rx.chakra.modal(
            rx.chakra.modal_overlay(
                rx.chakra.modal_content(
                    rx.chakra.modal_header("App Settings"),
                    rx.chakra.modal_body(app_settings()),
                ),
            ),
            is_open=ComplexLocalStorageState.settings_open,
            on_close=ComplexLocalStorageState.set_settings_open(False),
        ),
        rx.button("App Settings", on_click=ComplexLocalStorageState.open_settings),
    )
```
