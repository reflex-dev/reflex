# reflex-webmcp

Reflex plugin that automatically exposes backend events already bound to
components as [WebMCP](https://learn.chatgpt.com/docs/webmcp) site tools.

```python
import reflex as rx
from reflex_webmcp import WebMCPPlugin

config = rx.Config(app_name="my_app", plugins=[WebMCPPlugin()])
```

Each unique state handler bound to a component becomes one tool named
`reflex_<StateClass>_<handler>`; the docstring supplies its description and
the parameter annotations become the JSON input schema.
