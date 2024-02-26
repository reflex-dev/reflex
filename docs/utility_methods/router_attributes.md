```python exec
import reflex as rx
```

# State Utility Methods

The state object has several methods and attributes that return information
about the current page, session, or state.

## Router Attributes

The `self.router` attribute has several sub-attributes that provide various information:

* `router.page`: data about the current page and route
  * `host`: The hostname and port serving the current page (frontend).
  * `path`: The path of the current page (for dynamic pages, this will contain the slug)
  * `raw_path`: The path of the page displayed in the browser (including params and dynamic values)
  * `full_path`: `path` with `host` prefixed
  * `full_raw_path`: `raw_path` with `host` prefixed
  * `params`: Dictionary of query params associated with the request

* `router.session`: data about the current session
  * `client_token`: UUID associated with the current tab's token. Each tab has a unique token.
  * `session_id`: The ID associated with the client's websocket connection. Each tab has a unique session ID.
  * `client_ip`: The IP address of the client. Many users may share the same IP address.

* `router.headers`: a selection of common headers associated with the websocket
  connection. These values can only change when the websocket is re-established
  (for example, during page refresh). All other headers are available in the
  dictionary `self.router_data.headers`.
  * `host`: The hostname and port serving the websocket (backend).

### Example Values on this Page

```python demo exec alignItems=start
class RouterState(rx.State):
    pass


def router_values():
    return rx.chakra.table(
        headers=["Name", "Value"],
        rows=[
            [rx.text("router.page.host"), rx.code(RouterState.router.page.host)],
            [rx.text("router.page.path"), rx.code(RouterState.router.page.path)],
            [rx.text("router.page.raw_path"), rx.code(RouterState.router.page.raw_path)],
            [rx.text("router.page.full_path"), rx.code(RouterState.router.page.full_path)],
            [rx.text("router.page.full_raw_path"), rx.code(RouterState.router.page.full_raw_path)],
            [rx.text("router.page.params"), rx.code(RouterState.router.page.params.to_string())],
            [rx.text("router.session.client_token"), rx.code(RouterState.router.session.client_token)],
            [rx.text("router.session.session_id"), rx.code(RouterState.router.session.session_id)],
            [rx.text("router.session.client_ip"), rx.code(RouterState.router.session.client_ip)],
            [rx.text("router.headers.host"), rx.code(RouterState.router.headers.host)],
            [rx.text("router.headers.user_agent"), rx.code(RouterState.router.headers.user_agent)],
            [rx.text("router.headers.to_string()"), rx.code(RouterState.router.headers.to_string())],
        ],
        overflow_x="auto",
    )
```
