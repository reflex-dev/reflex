```python exec box
import reflex as rx

cell_style = {
    "font_family": "Instrument Sans",
    "font_style": "normal",
    "font_weight": "500",
    "font_size": "14px",
    "line_height": "1.5",
    "letter_spacing": "-0.0125em",
    "color": "var(--c-slate-11)",
}


class RouterState(rx.State):
    pass


router_data = [
    {"name": "rx.State.router.url", "value": RouterState.router.url},
    {"name": "rx.State.router.url.scheme", "value": RouterState.router.url.scheme},
    {"name": "rx.State.router.url.netloc", "value": RouterState.router.url.netloc},
    {"name": "rx.State.router.url.origin", "value": RouterState.router.url.origin},
    {"name": "rx.State.router.url.path", "value": RouterState.router.url.path},
    {"name": "rx.State.router.url.query", "value": RouterState.router.url.query},
    {
        "name": "rx.State.router.url.query_parameters",
        "value": RouterState.router.url.query_parameters.to_string(),
    },
    {"name": "rx.State.router.url.fragment", "value": RouterState.router.url.fragment},
    {"name": "rx.State.router.route_id", "value": RouterState.router.route_id},
    {
        "name": "rx.State.router.session.client_token",
        "value": RouterState.router.session.client_token,
    },
    {
        "name": "rx.State.router.session.session_id",
        "value": RouterState.router.session.session_id,
    },
    {
        "name": "rx.State.router.session.client_ip",
        "value": RouterState.router.session.client_ip,
    },
    {"name": "rx.State.router.headers.host", "value": RouterState.router.headers.host},
    {
        "name": "rx.State.router.headers.origin",
        "value": RouterState.router.headers.origin,
    },
    {
        "name": "rx.State.router.headers.upgrade",
        "value": RouterState.router.headers.upgrade,
    },
    {
        "name": "rx.State.router.headers.connection",
        "value": RouterState.router.headers.connection,
    },
    {
        "name": "rx.State.router.headers.cookie",
        "value": RouterState.router.headers.cookie,
    },
    {
        "name": "rx.State.router.headers.pragma",
        "value": RouterState.router.headers.pragma,
    },
    {
        "name": "rx.State.router.headers.cache_control",
        "value": RouterState.router.headers.cache_control,
    },
    {
        "name": "rx.State.router.headers.user_agent",
        "value": RouterState.router.headers.user_agent,
    },
    {
        "name": "rx.State.router.headers.sec_websocket_version",
        "value": RouterState.router.headers.sec_websocket_version,
    },
    {
        "name": "rx.State.router.headers.sec_websocket_key",
        "value": RouterState.router.headers.sec_websocket_key,
    },
    {
        "name": "rx.State.router.headers.sec_websocket_extensions",
        "value": RouterState.router.headers.sec_websocket_extensions,
    },
    {
        "name": "rx.State.router.headers.accept_encoding",
        "value": RouterState.router.headers.accept_encoding,
    },
    {
        "name": "rx.State.router.headers.accept_language",
        "value": RouterState.router.headers.accept_language,
    },
    {
        "name": "rx.State.router.headers.raw_headers",
        "value": RouterState.router.headers.raw_headers.to_string(),
    },
]
```

# State Utility Methods

The state object has several methods and attributes that return information
about the current page, session, or state.

## Router Attributes

The `self.router` attribute has several sub-attributes that provide various information:

- `router.url`: the URL of the current page, parsed into its components (see [URL Attributes](#url-attributes) below).
- `router.route_id`: the route pattern that matched the current request (e.g. `/posts/[id]`). For [dynamic pages](/docs/pages/dynamic_routing) this contains the slug rather than the actual value used to load the page.

- `router.session`: data about the current session
  - `client_token`: UUID associated with the current tab's token. Each tab has a unique token.
  - `session_id`: The ID associated with the client's websocket connection. Each tab has a unique session ID.
  - `client_ip`: The IP address of the client. Many users may share the same IP address.

- `router.headers`: headers associated with the websocket connection. These values can only change when the websocket is re-established (for example, during page refresh).
  - `host`: The hostname and port serving the websocket (backend).
  - `origin`: The origin of the request.
  - `upgrade`: The upgrade header for websocket connections.
  - `connection`: The connection header.
  - `cookie`: The cookie header.
  - `pragma`: The pragma header.
  - `cache_control`: The cache control header.
  - `user_agent`: The user agent string of the client.
  - `sec_websocket_version`: The websocket version.
  - `sec_websocket_key`: The websocket key.
  - `sec_websocket_extensions`: The websocket extensions.
  - `accept_encoding`: The accepted encodings.
  - `accept_language`: The accepted languages.
  - `raw_headers`: A mapping of all HTTP headers as a frozen dictionary. This provides access to any header that was sent with the request, not just the common ones listed above.

## URL Attributes

`self.router.url` is the full URL of the page currently displayed in the browser, parsed into its components using Python's standard `urllib.parse.urlsplit`. It is a string subclass, so it can be used anywhere a string is expected (for example, passed to `rx.text(self.router.url)` to render the whole URL), and additionally exposes the following attributes:

- `scheme`: The URL scheme (e.g. `"http"` or `"https"`).
- `netloc`: The network location, including hostname and optional port (e.g. `"example.com:3000"`).
- `origin`: The scheme and netloc joined together (e.g. `"https://example.com:3000"`). Equivalent to `f"{scheme}://{netloc}"`.
- `path`: The URL path as displayed in the browser, including any filled-in dynamic segments but excluding the query string and fragment (e.g. `"/posts/123"`).
- `query`: The raw query string, without the leading `?` (e.g. `"tab=comments&sort=new"`).
- `query_parameters`: The query string parsed into a frozen, immutable `Mapping[str, str]`. Use this instead of parsing `query` by hand.
- `fragment`: The URL fragment, without the leading `#` (e.g. `"section-2"`). The client-side router sends the current fragment over the WebSocket, so this reflects whatever is shown in the browser URL bar.

### Example

For a request to `https://example.com:3000/posts/123?tab=comments#top` matching the route `/posts/[id]`:

| Attribute                            | Value                                                  |
| :----------------------------------- | :----------------------------------------------------- |
| `self.router.url`                    | `"https://example.com:3000/posts/123?tab=comments#top"`|
| `self.router.url.scheme`             | `"https"`                                              |
| `self.router.url.netloc`             | `"example.com:3000"`                                   |
| `self.router.url.origin`             | `"https://example.com:3000"`                           |
| `self.router.url.path`               | `"/posts/123"`                                         |
| `self.router.url.query`              | `"tab=comments"`                                       |
| `self.router.url.query_parameters`   | `{"tab": "comments"}`                                  |
| `self.router.url.fragment`           | `"top"`                                                |
| `self.router.route_id`               | `"/posts/[id]"`                                        |

### Reading Query Parameters

`query_parameters` is the preferred way to read values from the query string. It is a frozen mapping (immutable and hashable), so it is safe to use inside `@rx.var` computed vars and event handlers:

```python
class State(rx.State):
    @rx.var
    def selected_tab(self) -> str:
        return self.router.url.query_parameters.get("tab", "overview")

    def on_load(self):
        page = self.router.url.query_parameters.get("page", "1")
        # ... load the appropriate data for that page ...
```

For dynamic path segments such as `[id]` or `[[...splat]]`, see [Dynamic Routes](/docs/pages/dynamic_routing) — those values are exposed as state vars on the root state (e.g. `rx.State.id`, `rx.State.splat`), not through `router.url`.

## Migrating from `router.page`

The `self.router.page` namespace is deprecated as of Reflex 0.8.1 and will be removed in 1.0. Its functionality is now provided by `self.router.url` together with `self.router.route_id`. Use the table below to update existing code:

| Deprecated                          | Replacement                                                   | Notes                                                                 |
| :---------------------------------- | :------------------------------------------------------------ | :-------------------------------------------------------------------- |
| `self.router.page.path`             | `self.router.route_id`                                        | The route pattern, e.g. `/posts/[id]`.                                |
| `self.router.page.raw_path`         | `self.router.url.path`                                        | The actual path in the browser. Append `?{url.query}` if you also need query params. |
| `self.router.page.full_path`        | `f"{self.router.url.origin}{self.router.route_id}"`           | Origin prefixed onto the route pattern. Rarely needed.                |
| `self.router.page.full_raw_path`    | `self.router.url`                                             | `router.url` is itself the full URL as a string.                      |
| `self.router.page.host`             | `self.router.url.origin`                                      | Full origin including scheme (e.g. `"http://localhost:3000"`). Use `self.router.url.netloc` for just `host:port`. |
| `self.router.page.params`           | `self.router.url.query_parameters`                            | Now a frozen mapping rather than a plain dict.                        |

### Example Values on this Page

```python eval
rx.table.root(
    rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Name"),
            rx.table.column_header_cell("Value"),
        ),
    ),
    rx.table.body(*[
        rx.table.row(
            rx.table.cell(item["name"], style=cell_style),
            rx.table.cell(
                rx.code(
                    item["value"],
                    style={
                        "color": rx.color("violet", 11),
                        "border_radius": "0.25rem",
                        "border": f"1px solid {rx.color('violet', 5)}",
                        "background": rx.color("violet", 3),
                    },
                )
            ),
        )
        for item in router_data
    ]),
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
