"""Dev-only frontend inspector.

The inspector maps rendered DOM nodes back to the Python ``Component`` call
site that produced them. Each piece is independently testable:

- ``state`` toggles the global enabled flag (set by ``integration``).
- ``capture`` walks the call stack and records the user-code frame.
- ``emit`` writes the lookup table consumed by the browser script.
- ``shortcut`` parses the keyboard shortcut configured in ``rx.Config``.
- ``integration`` is the coordinator the rest of Reflex talks to.

The browser-side counterpart lives under ``reflex_base/assets/inspector``.
The constants below are the shared contract between the Python compile-time
side and the JS runtime — pinned by ``tests/.../test_browser_contract.py``.
"""

from __future__ import annotations

from . import capture, shortcut, state

DATA_ATTR = "data-rx"
PUBLIC_DIRNAME = "__reflex"
INSPECTOR_PLUGIN_FILE = "reflex-inspector-plugin.js"
SOURCE_MAP_FILENAME = "source-map.json"
SOURCE_MAP_URL = f"/{PUBLIC_DIRNAME}/{SOURCE_MAP_FILENAME}"
INSPECTOR_JS_URL = f"/{PUBLIC_DIRNAME}/inspector.js"
INSPECTOR_CSS_URL = f"/{PUBLIC_DIRNAME}/inspector.css"
EDITOR_URL = "/__open-in-editor"
WINDOW_CONFIG_KEY = "__REFLEX_INSPECTOR_CONFIG__"
SHORTCUT_CONFIG_KEY = "shortcut"

__all__ = [
    "DATA_ATTR",
    "EDITOR_URL",
    "INSPECTOR_CSS_URL",
    "INSPECTOR_JS_URL",
    "INSPECTOR_PLUGIN_FILE",
    "PUBLIC_DIRNAME",
    "SHORTCUT_CONFIG_KEY",
    "SOURCE_MAP_FILENAME",
    "SOURCE_MAP_URL",
    "WINDOW_CONFIG_KEY",
    "capture",
    "shortcut",
    "state",
]
