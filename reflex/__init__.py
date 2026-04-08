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

import sys

from reflex_base.utils import lazy_loader

if sys.version_info < (3, 11):
    from reflex_base.utils import console

    console.warn(
        "Reflex support for Python 3.10 is deprecated and will be removed in a future release. Please upgrade to Python 3.11 or higher for continued support."
    )
    del console
del sys

from reflex_components_radix.mappings import RADIX_MAPPING  # noqa: E402

_COMPONENTS_CORE_MAPPING: lazy_loader.SubmodAttrsType = {
    "reflex_components_core.core.banner": [
        "connection_banner",
        "connection_modal",
    ],
    "reflex_components_core.core.cond": ["cond", "color_mode_cond"],
    "reflex_components_core.core.foreach": ["foreach"],
    "reflex_components_core.core.debounce": ["debounce_input"],
    "reflex_components_core.core.html": ["html"],
    "reflex_components_core.core.match": ["match"],
    "reflex_components_core.core.clipboard": ["clipboard"],
    "reflex_components_core.core.colors": ["color"],
    "reflex_components_core.core.breakpoints": ["breakpoints"],
    "reflex_components_core.core.responsive": [
        "desktop_only",
        "mobile_and_tablet",
        "mobile_only",
        "tablet_and_desktop",
        "tablet_only",
    ],
    "reflex_components_core.core.upload": [
        "cancel_upload",
        "clear_selected_files",
        "get_upload_dir",
        "get_upload_url",
        "selected_files",
        "upload",
    ],
    "reflex_components_core.core.auto_scroll": ["auto_scroll"],
    "reflex_components_core.core.window_events": ["window_event_listener"],
}

_COMPONENTS_BASE_MAPPING: lazy_loader.SubmodAttrsType = {
    "reflex_components_core.base.fragment": ["fragment", "Fragment"],
    "reflex_components_core.base.script": ["script", "Script"],
}

_ALL_COMPONENTS_MAPPING: lazy_loader.SubmodAttrsType = {
    "reflex_base.components.component": [
        "Component",
        "NoSSRComponent",
        "memo",
        "ComponentNamespace",
    ],
    "reflex_components_core.el.elements.media": ["image"],
    "reflex_components_lucide": ["icon"],
    **_COMPONENTS_BASE_MAPPING,
    "reflex_components_core": ["el"],
    "reflex_components_markdown.markdown": ["markdown"],
    **RADIX_MAPPING,
    "reflex_components_plotly": ["plotly"],
    "reflex_components_react_player": ["audio", "video"],
    **_COMPONENTS_CORE_MAPPING,
    "reflex_components_code.code": [
        "code_block",
    ],
    "reflex_components_dataeditor.dataeditor": [
        "data_editor",
        "data_editor_theme",
    ],
    "reflex_components_sonner.toast": ["toast"],
    "reflex_base.components.props": ["PropsBase"],
    "reflex_components_core.datadisplay.logo": ["logo"],
    "reflex_components_gridjs": ["data_table"],
    "reflex_components_moment": ["MomentDelta", "moment"],
}

_COMPONENT_NAME_TO_PATH: dict[str, str] = {
    lazy_loader.comp_alias(comp): lazy_loader.comp_path(path, comp)
    for path, comps in _ALL_COMPONENTS_MAPPING.items()
    for comp in comps
} | {
    "radix": "reflex_components_radix",
    "lucide": "reflex_components_lucide",
    "recharts": "reflex_components_recharts",
}

_MAPPING: lazy_loader.SubmodAttrsType = {
    "experimental": ["_x"],
    "admin": ["AdminDash"],
    "app": ["App", "UploadFile"],
    "assets": ["asset"],
    "config": ["Config", "DBConfig"],
    "constants": ["Env"],
    "constants.colors": ["Color"],
    "_upload": [
        "UploadChunk",
        "UploadChunkIterator",
    ],
    "event": [
        "event",
        "EventChain",
        "EventHandler",
        "call_script",
        "call_function",
        "run_script",
        "clear_local_storage",
        "clear_session_storage",
        "console_log",
        "download",
        "noop",
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
        "upload_files_chunk",
        "window_alert",
    ],
    "istate.storage": [
        "Cookie",
        "LocalStorage",
        "SessionStorage",
    ],
    "istate.manager.token": ["StateToken", "BaseStateToken"],
    "middleware": ["middleware", "Middleware"],
    "model": ["asession", "session", "Model", "ModelRegistry"],
    "page": ["page"],
    "state": [
        "var",
        "ComponentState",
        "State",
        "dynamic",
    ],
    "istate.shared": ["SharedState"],
    "istate.wrappers": ["get_state"],
    "style": ["Style", "toggle_color_mode"],
    "utils.imports": ["ImportDict", "ImportVar"],
    "utils.misc": ["run_in_thread"],
    "utils.serializers": ["serializer"],
    "vars": ["Var", "field", "Field", "RestProp"],
}

_SUBMODULES: set[str] = {
    "components",
    "app",
    "style",
    "admin",
    "base",
    "constants",
    "model",
    "testing",
    "utils",
    "vars",
    "config",
    "compiler",
    "plugins",
}
_SUBMOD_ATTRS: lazy_loader.SubmodAttrsType = _MAPPING
_EXTRA_MAPPINGS: dict[str, str] = _COMPONENT_NAME_TO_PATH
getattr, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
    **_EXTRA_MAPPINGS,
)


def __getattr__(name: str):
    return getattr(name)
