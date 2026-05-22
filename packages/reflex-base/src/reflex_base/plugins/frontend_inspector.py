"""Plugin for the dev-only frontend inspector.

The inspector maps rendered DOM nodes back to the Python ``Component``
call site that produced them. Wiring it up requires multiple compile-time
artifacts; this plugin owns all of them so users opt in with a single
``rxconfig.py`` entry:

.. code-block:: python

    config = rx.Config(
        app_name="my_app",
        plugins=[rx.plugins.FrontendInspectorPlugin()],
    )

The plugin is a no-op under ``REFLEX_ENV_MODE=prod`` so the same
``rxconfig.py`` works for ``reflex run`` and ``reflex export``.
"""

from __future__ import annotations

import dataclasses
import functools
import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from typing_extensions import Unpack

from reflex_base import constants
from reflex_base.inspector import (
    DATA_ATTR,
    EDITOR_URL,
    INSPECTOR_CSS_URL,
    INSPECTOR_JS_URL,
    INSPECTOR_PLUGIN_FILE,
    PUBLIC_DIRNAME,
    SHORTCUT_CONFIG_KEY,
    SOURCE_MAP_FILENAME,
    SOURCE_MAP_URL,
    WINDOW_CONFIG_KEY,
    capture,
    state,
)
from reflex_base.inspector.shortcut import parse_shortcut

from .base import CommonContext, Plugin, PreCompileContext, StartCompileContext

if TYPE_CHECKING:
    from reflex_base.components.component import Component

LAUNCH_EDITOR_VERSION = "^2.6.1"
_INSPECTOR_VITE_IMPORT = "reflexInspectorPlugin"
_VITE_INSPECTOR_IMPORT_LINE = (
    f'import {_INSPECTOR_VITE_IMPORT} from "./{INSPECTOR_PLUGIN_FILE}";\n'
)
_VITE_INSPECTOR_PLUGIN_CALL = f"    {_INSPECTOR_VITE_IMPORT}(),\n"
_VITE_PLUGINS_ANCHOR = "    safariCacheBustPlugin(),\n"


@dataclasses.dataclass
class FrontendInspectorPlugin(Plugin):
    """Maps rendered DOM nodes back to their Python call site (dev-only).

    Attributes:
        shortcut: Keyboard shortcut for toggling the inspector. Modifier
            aliases like ``cmd``/``option`` are accepted.
        editor: Editor invocation forwarded to ``launch-editor`` via
            ``REFLEX_EDITOR``. Empty string defers to the user's existing
            ``REFLEX_EDITOR``/``VISUAL``/``EDITOR`` environment variables.
    """

    shortcut: str = "alt+x"
    editor: str = ""
    _injected_into_apps: set[int] = dataclasses.field(
        default_factory=set, init=False, repr=False
    )

    def _is_active(self) -> bool:
        # `environment` imports back from `reflex_base.plugins`; lazy import
        # avoids the cycle.
        from reflex_base.environment import environment

        return environment.REFLEX_ENV_MODE.get() != constants.Env.PROD

    def start_compile(self, **context: Unpack[StartCompileContext]) -> None:
        """Reset capture, flip the runtime flag, and inject head scripts.

        ``app.head_components`` has to be extended here rather than in
        ``pre_compile`` because ``compile_document_root`` reads it during
        the page-rendering phase, which runs before ``pre_compile``.

        Args:
            context: The context for the plugin.
        """
        app = context["app"]
        active = self._is_active()
        # Force off so the inspector's own ``<Script>`` head components do
        # not capture themselves into the source map.
        state.set_enabled(False)
        capture.reset()
        if not active:
            return
        if id(app) not in self._injected_into_apps:
            app.head_components.extend(self._build_head_components())
            self._injected_into_apps.add(id(app))
        state.set_enabled(True)

    def pre_compile(self, **context: Unpack[PreCompileContext]) -> None:
        """Splice the inspector plugin into ``vite.config.js``.

        Args:
            context: Pre-compile context supplying ``add_save_task`` and
                ``add_modify_task``.
        """
        if not self._is_active():
            return
        context["add_modify_task"](
            constants.ReactRouter.VITE_CONFIG_FILE,
            _inject_inspector_into_vite_config,
        )

    def get_frontend_development_dependencies(
        self, **context: Unpack[CommonContext]
    ) -> list[str]:
        """Add ``launch-editor`` so the dev-server middleware can open files.

        Args:
            context: The context for the plugin.

        Returns:
            ``["launch-editor@..."]`` when active, otherwise empty.
        """
        base = list(super().get_frontend_development_dependencies(**context))
        if self._is_active():
            base.append(f"launch-editor@{LAUNCH_EDITOR_VERSION}")
        return base

    def get_static_assets(
        self, **context: Unpack[CommonContext]
    ) -> Sequence[tuple[Path, str | bytes]]:
        """Browser assets, source map, and the Vite plugin file.

        Args:
            context: The context for the plugin.

        Returns:
            ``(path, content)`` pairs for each generated artifact, or an
            empty tuple when inactive.
        """
        if not self._is_active():
            return ()
        public = Path(constants.Dirs.PUBLIC) / PUBLIC_DIRNAME
        assets: list[tuple[Path, str | bytes]] = [
            (public / name, content) for name, content in _asset_payloads()
        ]
        assets.extend((
            (
                public / SOURCE_MAP_FILENAME,
                json.dumps(_source_map_payload(), separators=(",", ":")),
            ),
            (
                Path(INSPECTOR_PLUGIN_FILE),
                _vite_plugin_text(self.editor),
            ),
        ))
        return assets

    def _build_head_components(self) -> list[Component]:
        from reflex_components_core.el.elements.scripts import Script

        from reflex_base.config import get_config

        config = get_config()
        payload = json.dumps({
            SHORTCUT_CONFIG_KEY: parse_shortcut(self.shortcut).to_json_payload(),
            "sourceMapUrl": config.prepend_frontend_path(SOURCE_MAP_URL),
            "cssUrl": config.prepend_frontend_path(INSPECTOR_CSS_URL),
            "editorUrl": config.prepend_frontend_path(EDITOR_URL),
        })
        return [
            Script.create(f"window.{WINDOW_CONFIG_KEY} = {payload};"),
            Script.create(
                type="module", src=config.prepend_frontend_path(INSPECTOR_JS_URL)
            ),
        ]


def _inject_inspector_into_vite_config(content: str) -> str:
    """Splice the inspector import + plugin call into a rendered Vite config.

    Idempotent: a second call is a no-op when the import is already present.

    Args:
        content: The current ``vite.config.js`` source.

    Returns:
        The Vite config with the inspector wired in.
    """
    if _VITE_INSPECTOR_IMPORT_LINE in content:
        return content
    out = content.replace(
        'import safariCacheBustPlugin from "./vite-plugin-safari-cachebust";\n',
        'import safariCacheBustPlugin from "./vite-plugin-safari-cachebust";\n'
        + _VITE_INSPECTOR_IMPORT_LINE,
        1,
    )
    return out.replace(
        _VITE_PLUGINS_ANCHOR,
        _VITE_PLUGINS_ANCHOR + _VITE_INSPECTOR_PLUGIN_CALL,
        1,
    )


def _asset_source_dir() -> Path:
    import reflex_base

    return Path(reflex_base.__file__).resolve().parent / "assets" / "inspector"


@functools.cache
def _asset_payloads() -> tuple[tuple[str, bytes], ...]:
    """Read the bundled inspector browser assets once per process.

    Returns:
        ``(filename, bytes)`` for every file under ``assets/inspector/``.
    """
    return tuple(
        (asset.name, asset.read_bytes())
        for asset in _asset_source_dir().iterdir()
        if asset.is_file()
    )


def _source_map_payload() -> dict[str, dict[str, Any]]:
    return {
        str(cid): {
            "file": info.file,
            "line": info.line,
            "column": info.column,
            "component": info.component,
        }
        for cid, info in capture.snapshot().items()
    }


@functools.cache
def _vite_plugin_text(editor: str) -> str:
    """Render the Vite plugin file content.

    Args:
        editor: Editor invocation forwarded to ``launch-editor`` via
            ``REFLEX_EDITOR``. Empty string defers to env vars.

    Returns:
        The plugin source code as a string.
    """
    editor_literal = json.dumps(editor)
    editor_clause = (
        f"      process.env.REFLEX_EDITOR ||= {editor_literal};\n" if editor else ""
    )
    return rf"""// Auto-generated by Reflex frontend inspector. Do not edit.
import reflexEditorMiddleware from "./public/{PUBLIC_DIRNAME}/dev_server_middleware.js";

export default function {_INSPECTOR_VITE_IMPORT}() {{
  return {{
    name: "reflex-frontend-inspector",
    apply: 'serve',
    configureServer(server) {{
{editor_clause}      server.middlewares.use(reflexEditorMiddleware);
    }},
  }};
}}
"""


INSPECTOR_DATA_ATTR = DATA_ATTR

__all__ = [
    "INSPECTOR_DATA_ATTR",
    "FrontendInspectorPlugin",
]
