"""Import all classes and functions the end user will need to make an app.

Anything imported here will be available in the default Reflex import as `rx.*`.

Dynamic Imports
---------------
Reflex utilizes dynamic imports, or lazy loading, to reduce startup/import times.
With this approach, imports are delayed until they are actually needed. We use
the `lazy_loader` library(https://github.com/scientific-python/lazy_loader) to achieve this.

How it works
--------------
`lazy_loader.attach` takes two optional arguments: `submodules` and `submod_attrs`.
- `submodules` typically points to directories or files to be accessed.
- `submod_attrs` defines a mapping of directory or file names as keys with a list
  of attributes or modules to access.

Example directory structure:

reflex/
    |_ components/
            |_ radix/
                |_ themes/
                    |_ components/
                        |_ box.py

To add `box` under the `rx` namespace (`rx.box`), add the relative path to `submod_attrs` in
`reflex/__init__.py` (this file):

```python
lazy_loader.attach(
    submodules={"components"},
    submod_attrs={
        "components.radix.themes.components.box": ["box"]
    }
)
```

This implies that `box` will be imported from `reflex/components/radix/themes/components/box.py`.

To add box under the `rx.radix` namespace (`rx.radix.box`), add the relative path to the
submod_attrs argument in `reflex/components/radix/__init__.py`:

```python
lazy_loader.attach(
    submodules = {"themes"},
    submod_attrs = {
        "themes.components.box": ["box"]
    }
)
```

Note: It is important to specify the immediate submodules of a directory in the submodules
argument to ensure they are registered at runtime. For example, 'components' for reflex,
'radix' for components, 'themes' for radix, etc.


Pyi_generator
--------------
To generate `.pyi` files for `__init__.py` files, we read the `_SUBMODULES` and `_SUBMOD_ATTRS`
attributes to generate the import statements. It is highly recommended to define these with
the provided annotations to facilitate their generation.


Aliases
------------
This is a special case to specify an alias for a component.
As an example, we use this typically for `rx.list` where defining `list` attribute in the list.py
overshadows python's list object which messes up the pyi generation for `list.pyi`. As a result, aliases
should be used for similar cases like this. Note that this logic is employed to fix the pyi generation and alias
should still be defined or accessible. Check out the __getattr__ logic in `reflex/components/radix/themes/layouts/list.py`

```python
lazy_loader.attach(
    submodules={"components"},
    submod_attrs={
        "components.radix.themes.layouts": [("list_ns", "list")]
    }
)
```

In the example above, you will be able to do `rx.list`
"""

from __future__ import annotations

from reflex.utils import (
    compat,  # for side-effects
    lazy_loader,
)

# import this here explicitly to avoid returning the page module since page attr has the
# same name as page module(page.py)
from .page import page as page

# Remove the `compat` name from the namespace, it was imported for side-effects only.
del compat

RADIX_THEMES_MAPPING: dict = {
    "components.radix.themes.base": ["color_mode", "theme", "theme_panel"],
    "components.radix.themes.color_mode": ["color_mode"],
}
RADIX_THEMES_COMPONENTS_MAPPING: dict = {
    **{
        f"components.radix.themes.components.{mod}": [mod]
        for mod in [
            "alert_dialog",
            "aspect_ratio",
            "avatar",
            "badge",
            "button",
            "callout",
            "card",
            "checkbox",
            "context_menu",
            "data_list",
            "dialog",
            "hover_card",
            "icon_button",
            "input",
            "inset",
            "popover",
            "scroll_area",
            "select",
            "skeleton",
            "slider",
            "spinner",
            "switch",
            "table",
            "tabs",
            "text_area",
            "tooltip",
            "segmented_control",
            "radio_cards",
            "checkbox_cards",
            "checkbox_group",
        ]
    },
    "components.radix.themes.components.text_field": ["text_field", "input"],
    "components.radix.themes.components.radio_group": ["radio", "radio_group"],
    "components.radix.themes.components.dropdown_menu": ["menu", "dropdown_menu"],
    "components.radix.themes.components.separator": ["divider", "separator"],
}

RADIX_THEMES_LAYOUT_MAPPING: dict = {
    "components.radix.themes.layout.box": [
        "box",
    ],
    "components.radix.themes.layout.center": [
        "center",
    ],
    "components.radix.themes.layout.container": [
        "container",
    ],
    "components.radix.themes.layout.flex": [
        "flex",
    ],
    "components.radix.themes.layout.grid": [
        "grid",
    ],
    "components.radix.themes.layout.section": [
        "section",
    ],
    "components.radix.themes.layout.spacer": [
        "spacer",
    ],
    "components.radix.themes.layout.stack": [
        "stack",
        "hstack",
        "vstack",
    ],
    "components.radix.themes.layout.list": [
        ("list_ns", "list"),
        "list_item",
        "ordered_list",
        "unordered_list",
    ],
}

RADIX_THEMES_TYPOGRAPHY_MAPPING: dict = {
    "components.radix.themes.typography.blockquote": [
        "blockquote",
    ],
    "components.radix.themes.typography.code": [
        "code",
    ],
    "components.radix.themes.typography.heading": [
        "heading",
    ],
    "components.radix.themes.typography.link": [
        "link",
    ],
    "components.radix.themes.typography.text": [
        "text",
    ],
}

RADIX_PRIMITIVES_MAPPING: dict = {
    "components.radix.primitives.accordion": [
        "accordion",
    ],
    "components.radix.primitives.drawer": [
        "drawer",
    ],
    "components.radix.primitives.form": [
        "form",
    ],
    "components.radix.primitives.progress": ["progress"],
}

COMPONENTS_CORE_MAPPING: dict = {
    "components.core.banner": [
        "connection_banner",
        "connection_modal",
    ],
    "components.core.cond": ["cond", "color_mode_cond"],
    "components.core.foreach": ["foreach"],
    "components.core.debounce": ["debounce_input"],
    "components.core.html": ["html"],
    "components.core.match": ["match"],
    "components.core.clipboard": ["clipboard"],
    "components.core.colors": ["color"],
    "components.core.breakpoints": ["breakpoints"],
    "components.core.responsive": [
        "desktop_only",
        "mobile_and_tablet",
        "mobile_only",
        "tablet_and_desktop",
        "tablet_only",
    ],
    "components.core.upload": [
        "cancel_upload",
        "clear_selected_files",
        "get_upload_dir",
        "get_upload_url",
        "selected_files",
        "upload",
    ],
}

COMPONENTS_BASE_MAPPING: dict = {
    "components.base.fragment": ["fragment", "Fragment"],
    "components.base.script": ["script", "Script"],
}

RADIX_MAPPING: dict = {
    **RADIX_THEMES_MAPPING,
    **RADIX_THEMES_COMPONENTS_MAPPING,
    **RADIX_THEMES_TYPOGRAPHY_MAPPING,
    **RADIX_THEMES_LAYOUT_MAPPING,
    **RADIX_PRIMITIVES_MAPPING,
}

_MAPPING: dict = {
    "experimental": ["_x"],
    "admin": ["AdminDash"],
    "app": ["App", "UploadFile"],
    "base": ["Base"],
    "components.component": [
        "Component",
        "NoSSRComponent",
        "memo",
        "ComponentNamespace",
    ],
    "components.el.elements.media": ["image"],
    "components.lucide": ["icon"],
    **COMPONENTS_BASE_MAPPING,
    "components.suneditor": [
        "editor",
        "EditorButtonList",
        "EditorOptions",
    ],
    "components": ["el", "radix", "lucide", "recharts", "next"],
    "components.markdown": ["markdown"],
    **RADIX_MAPPING,
    "components.plotly": ["plotly"],
    "components.react_player": ["audio", "video"],
    **COMPONENTS_CORE_MAPPING,
    "components.datadisplay.code": [
        "code_block",
    ],
    "components.datadisplay.dataeditor": [
        "data_editor",
        "data_editor_theme",
    ],
    "components.sonner.toast": ["toast"],
    "components.datadisplay.logo": ["logo"],
    "components.gridjs": ["data_table"],
    "components.moment": ["MomentDelta", "moment"],
    "config": ["Config", "DBConfig"],
    "constants": ["Env"],
    "event": [
        "EventChain",
        "EventHandler",
        "background",
        "call_script",
        "clear_local_storage",
        "clear_session_storage",
        "console_log",
        "download",
        "prevent_default",
        "redirect",
        "remove_cookie",
        "remove_local_storage",
        "remove_session_storage",
        "set_clipboard",
        "set_focus",
        "scroll_to",
        "set_value",
        "stop_propagation",
        "upload_files",
        "window_alert",
    ],
    "middleware": ["middleware", "Middleware"],
    "model": ["session", "Model"],
    "state": [
        "var",
        "Cookie",
        "LocalStorage",
        "SessionStorage",
        "ComponentState",
        "State",
    ],
    "style": ["Style", "toggle_color_mode"],
    "utils.imports": ["ImportVar"],
    "utils.serializers": ["serializer"],
    "vars": ["cached_var", "Var"],
}

_SUBMODULES: set[str] = {
    "components",
    "event",
    "app",
    "style",
    "admin",
    "base",
    "model",
    "testing",
    "utils",
    "vars",
    "config",
    "compiler",
}
_SUBMOD_ATTRS: dict = _MAPPING
getattr, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)


def __getattr__(name):
    if name == "chakra":
        from reflex.utils import console

        console.deprecate(
            "rx.chakra",
            reason="and moved to a separate package. "
            "To continue using Chakra UI components, install the `reflex-chakra` package via `pip install "
            "reflex-chakra`.",
            deprecation_version="0.6.0",
            removal_version="0.7.0",
            dedupe=True,
        )
        import reflex_chakra as rc

        return rc
    return getattr(name)
