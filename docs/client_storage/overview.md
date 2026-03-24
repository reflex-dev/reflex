```python exec
import reflex as rx
```

# Client-storage

You can use the browser's local storage to persist state between sessions.
This allows user preferences, authentication cookies, other bits of information
to be stored on the client and accessed from different browser tabs.

A client-side storage var looks and acts like a normal `str` var, except the
default value is either `rx.Cookie` or `rx.LocalStorage` depending on where the
value should be stored. The key name will be based on the var name, but this
can be overridden by passing `name="my_custom_name"` as a keyword argument.

For more information see [Browser Storage](/docs/api-reference/browser-storage/).

Try entering some values in the text boxes below and then load the page in a separate
tab or check the storage section of browser devtools to see the values saved in the browser.

```python demo exec
class ClientStorageState(rx.State):
    my_cookie: str = rx.Cookie("")
    my_local_storage: str = rx.LocalStorage("")
    custom_cookie: str = rx.Cookie(name="CustomNamedCookie", max_age=3600)

    @rx.event
    def set_my_cookie(self, value: str):
        self.my_cookie = value

    @rx.event
    def set_my_local_storage(self, value: str):
        self.my_local_storage = value

    @rx.event
    def set_custom_cookie(self, value: str):
        self.custom_cookie = value

def client_storage_example():
    return rx.vstack(
        rx.hstack(rx.text("my_cookie"), rx.input(value=ClientStorageState.my_cookie, on_change=ClientStorageState.set_my_cookie)),
        rx.hstack(rx.text("my_local_storage"), rx.input(value=ClientStorageState.my_local_storage, on_change=ClientStorageState.set_my_local_storage)),
        rx.hstack(rx.text("custom_cookie"), rx.input(value=ClientStorageState.custom_cookie, on_change=ClientStorageState.set_custom_cookie)),
    )
```
