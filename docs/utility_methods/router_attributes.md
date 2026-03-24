```python exec box
import reflex as rx
from pcweb.styles.styles import get_code_style, cell_style

class RouterState(rx.State):
    pass


router_data = [
      {"name": "rx.State.router.page.host", "value": RouterState.router.page.host},
      {"name": "rx.State.router.page.path", "value": RouterState.router.page.path},
      {"name": "rx.State.router.page.raw_path", "value": RouterState.router.page.raw_path},
      {"name": "rx.State.router.page.full_path", "value": RouterState.router.page.full_path},
      {"name": "rx.State.router.page.full_raw_path", "value": RouterState.router.page.full_raw_path},
      {"name": "rx.State.router.page.params", "value": RouterState.router.page.params.to_string()},
      {"name": "rx.State.router.session.client_token", "value": RouterState.router.session.client_token},
      {"name": "rx.State.router.session.session_id", "value": RouterState.router.session.session_id},
      {"name": "rx.State.router.session.client_ip", "value": RouterState.router.session.client_ip},
      {"name": "rx.State.router.headers.host", "value": RouterState.router.headers.host},
      {"name": "rx.State.router.headers.origin", "value": RouterState.router.headers.origin},
      {"name": "rx.State.router.headers.upgrade", "value": RouterState.router.headers.upgrade},
      {"name": "rx.State.router.headers.connection", "value": RouterState.router.headers.connection},
      {"name": "rx.State.router.headers.cookie", "value": RouterState.router.headers.cookie},
      {"name": "rx.State.router.headers.pragma", "value": RouterState.router.headers.pragma},
      {"name": "rx.State.router.headers.cache_control", "value": RouterState.router.headers.cache_control},
      {"name": "rx.State.router.headers.user_agent", "value": RouterState.router.headers.user_agent},
      {"name": "rx.State.router.headers.sec_websocket_version", "value": RouterState.router.headers.sec_websocket_version},
      {"name": "rx.State.router.headers.sec_websocket_key", "value": RouterState.router.headers.sec_websocket_key},
      {"name": "rx.State.router.headers.sec_websocket_extensions", "value": RouterState.router.headers.sec_websocket_extensions},
      {"name": "rx.State.router.headers.accept_encoding", "value": RouterState.router.headers.accept_encoding},
      {"name": "rx.State.router.headers.accept_language", "value": RouterState.router.headers.accept_language},
      {"name": "rx.State.router.headers.raw_headers", "value": RouterState.router.headers.raw_headers.to_string()},
  ]

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

* `router.headers`: headers associated with the websocket connection. These values can only change when the websocket is re-established (for example, during page refresh).
  * `host`: The hostname and port serving the websocket (backend).
  * `origin`: The origin of the request.
  * `upgrade`: The upgrade header for websocket connections.
  * `connection`: The connection header.
  * `cookie`: The cookie header.
  * `pragma`: The pragma header.
  * `cache_control`: The cache control header.
  * `user_agent`: The user agent string of the client.
  * `sec_websocket_version`: The websocket version.
  * `sec_websocket_key`: The websocket key.
  * `sec_websocket_extensions`: The websocket extensions.
  * `accept_encoding`: The accepted encodings.
  * `accept_language`: The accepted languages.
  * `raw_headers`: A mapping of all HTTP headers as a frozen dictionary. This provides access to any header that was sent with the request, not just the common ones listed above.

### Example Values on this Page

```python eval
rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Value"),
            ),
        ),
        rx.table.body(
            *[
                rx.table.row(
                    rx.table.cell(item["name"], style=cell_style),
                    rx.table.cell(rx.code(item["value"], style=get_code_style("violet"))),
                )
                for item in router_data
            ]
        ),
        variant="surface",
        margin_y="1em",
    )
```

### Accessing Raw Headers

The `raw_headers` attribute provides access to all HTTP headers as a frozen dictionary. This is useful when you need to access headers that are not explicitly defined in the `HeaderData` class:

```python box
# Access a specific header
custom_header_value = self.router.headers.raw_headers.get("x-custom-header", "")

# Example of accessing common headers
user_agent = self.router.headers.raw_headers.get("user-agent", "")
content_type = self.router.headers.raw_headers.get("content-type", "")
authorization = self.router.headers.raw_headers.get("authorization", "")

# You can also check if a header exists
has_custom_header = "x-custom-header" in self.router.headers.raw_headers
```

This is particularly useful for accessing custom headers or when working with specific HTTP headers that are not part of the standard set exposed as direct attributes.
