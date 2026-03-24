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

```md alert warning
# **The default value of a Cookie is never set in the browser!**

The Cookie value is only set when the Var is assigned. If you need to set a
default value, you can assign a value to the cookie in an `on_load` event
handler.
```

## Accessing Cookies

Cookies are accessed like any other Var in the state. If another state needs access
to the value of a cookie, the state should be a substate of the state that defines
the cookie. Alternatively the `get_state` API can be used to access the other state.

For rendering cookies in the frontend, import the state that defines the cookie and
reference it directly.

```md alert warning
# **Two separate states should _avoid_ defining `rx.Cookie` with the same name.**

Although it is technically possible, the cookie options may differ, leading to
unexpected results.

Additionally, updating the cookie value in one state will not automatically
update the value in the other state without a page refresh or navigation event.
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
- `sync`: Boolean indicates if the state should be kept in sync across tabs of the same browser.

```python
class LocalStorageState(rx.State):
    # local storage with default settings
    l1: str = rx.LocalStorage()

    # local storage with custom settings
    l2: str = rx.LocalStorage("l2 default")
    l3: str = rx.LocalStorage(name="l3")

    # local storage that automatically updates in other states across tabs
    l4: str = rx.LocalStorage(sync=True)
```

### Syncing Vars

Because LocalStorage applies to the entire browser, all LocalStorage Vars are
automatically shared across tabs.

The `sync` parameter controls whether an update in one tab should be actively
propagated to other tabs without requiring a navigation or page refresh event.

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

## rx.SessionStorage

Represents a state Var that is stored in sessionStorage in the browser. Similar to localStorage, but the data is cleared when the page session ends (when the browser/tab is closed). Currently only supports string values.

Parameters

- `name`: The name of the storage key on the client side.

```python
class SessionStorageState(rx.State):
    # session storage with default settings
    s1: str = rx.SessionStorage()

    # session storage with custom settings
    s2: str = rx.SessionStorage("s2 default")
    s3: str = rx.SessionStorage(name="s3")
```

### Session Persistence

SessionStorage data is cleared when the page session ends. A page session lasts as long as the browser is open and survives page refreshes and restores, but is cleared when the tab or browser is closed.

Unlike LocalStorage, SessionStorage is isolated to the tab/window in which it was created, so it's not shared with other tabs/windows of the same origin.

## rx.remove_session_storage

Remove a session storage item from the client's browser.

Parameters

- `key`: The key to remove from session storage.

```python
rx.button(
    'Remove Session Storage',
    on_click=rx.remove_session_storage('key'),
)
```

This event can also be returned from an event handler:

```python
class SessionStorageState(rx.State):
    ...
    def logout(self):
        return rx.remove_session_storage('session_storage_state.s1')
```

## rx.clear_session_storage()

Clear all session storage items from the client's browser. This may affect other
apps running in the same domain or libraries within your app that use session
storage.

```python
rx.button(
    'Clear all Session Storage',
    on_click=rx.clear_session_storage(),
)
```

# Serialization Strategies

If a non-trivial data structure should be stored in a `Cookie`, `LocalStorage`, or `SessionStorage` var it needs to be serialized before and after storing it. It is recommended to use a pydantic class for the data which provides simple serialization helpers and works recursively in complex object structures.

```python demo exec
import reflex as rx
import pydantic


class AppSettings(pydantic.BaseModel):
    theme: str = 'light'
    sidebar_visible: bool = True
    update_frequency: int = 60
    error_messages: list[str] = pydantic.Field(default_factory=list)


class ComplexLocalStorageState(rx.State):
    data_raw: str = rx.LocalStorage("{}")
    data: AppSettings = AppSettings()
    settings_open: bool = False

    @rx.event
    def save_settings(self):
        self.data_raw = self.data.model_dump_json()
        self.settings_open = False

    @rx.event
    def open_settings(self):
        self.data = AppSettings.model_validate_json(self.data_raw)
        self.settings_open = True

    @rx.event
    def set_field(self, field, value):
        setattr(self.data, field, value)


def app_settings():
    return rx.form.root(
        rx.foreach(
            ComplexLocalStorageState.data.error_messages,
            rx.text,
        ),
        rx.form.field(
            rx.flex(
                rx.form.label(
                    "Theme",
                    rx.input(
                        value=ComplexLocalStorageState.data.theme,
                        on_change=lambda v: ComplexLocalStorageState.set_field(
                            "theme", v
                        ),
                    ),
                ),
                rx.form.label(
                    "Sidebar Visible",
                    rx.switch(
                        checked=ComplexLocalStorageState.data.sidebar_visible,
                        on_change=lambda v: ComplexLocalStorageState.set_field(
                            "sidebar_visible",
                            v,
                        ),
                    ),
                ),
                rx.form.label(
                    "Update Frequency (seconds)",
                    rx.input(
                        value=ComplexLocalStorageState.data.update_frequency,
                        on_change=lambda v: ComplexLocalStorageState.set_field(
                            "update_frequency",
                            v,
                        ),
                    ),
                ),
                rx.dialog.close(rx.button("Save", type="submit")),
                gap=2,
                direction="column",
            )
        ),
        on_submit=lambda _: ComplexLocalStorageState.save_settings(),
    )

def app_settings_example():
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button("App Settings", on_click=ComplexLocalStorageState.open_settings),
        ),
        rx.dialog.content(
            rx.dialog.title("App Settings"),
            app_settings(),
        ),
    )
```

# Comparison of Storage Types

Here's a comparison of the different client-side storage options in Reflex:

| Feature | rx.Cookie | rx.LocalStorage | rx.SessionStorage |
|---------|-----------|----------------|------------------|
| Persistence | Until cookie expires | Until explicitly deleted | Until browser/tab is closed |
| Storage Limit | ~4KB | ~5MB | ~5MB |
| Sent with Requests | Yes | No | No |
| Accessibility | Server & Client | Client Only | Client Only |
| Expiration | Configurable | Never | End of session |
| Scope | Configurable (domain, path) | Origin (domain) | Tab/Window |
| Syncing Across Tabs | No | Yes (with sync=True) | No |
| Use Case | Authentication, Server-side state | User preferences, App state | Temporary session data |

# When to Use Each Storage Type

## Use rx.Cookie When:
- You need the data to be accessible on the server side (cookies are sent with HTTP requests)
- You're handling user authentication
- You need fine-grained control over expiration and scope
- You need to limit the data to specific paths in your app

## Use rx.LocalStorage When:
- You need to store larger amounts of data (up to ~5MB)
- You want the data to persist indefinitely (until explicitly deleted)
- You need to share data between different tabs/windows of your app
- You want to store user preferences that should be remembered across browser sessions

## Use rx.SessionStorage When:
- You need temporary data that should be cleared when the browser/tab is closed
- You want to isolate data to a specific tab/window
- You're storing sensitive information that shouldn't persist after the session ends
- You're implementing per-session features like form data, shopping carts, or multi-step processes
- You want to persist data for a state after Redis expiration (for server-side state that needs to survive longer than Redis TTL)
