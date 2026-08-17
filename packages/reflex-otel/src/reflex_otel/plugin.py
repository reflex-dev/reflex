"""Compile-time plugin that adds browser-side OpenTelemetry to a Reflex app."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from reflex_base.config import get_config
from reflex_base.constants.base import ReactRouter, Reflex
from reflex_base.constants.compiler import Embed
from reflex_base.plugins.base import Plugin

logger = logging.getLogger(__name__)

BROWSER_MODULE = "utils/otel.js"
_BROWSER_MODULE_SOURCE = Path(__file__).with_name("otel.js")

# Pinned npm packages for the browser module.
FRONTEND_DEPENDENCIES = (
    "@opentelemetry/api@1.9.1",
    "@opentelemetry/core@2.10.0",
    "@opentelemetry/exporter-trace-otlp-http@0.221.0",
    "@opentelemetry/resources@2.10.0",
    "@opentelemetry/sdk-trace-web@2.10.0",
    "web-vitals@6.1.1",
)

_ENTRY_IMPORT = 'import { OtelRoot } from "$/utils/otel";\n'
_ENTRY_ROOT_ANCHOR = "createElement(HydratedRouter)"
_ENTRY_ROOT_WRAPPED = "createElement(OtelRoot, null, createElement(HydratedRouter))"

# React strips <Profiler> from production builds; the profiling build keeps it.
_VITE_CONFIG_ANCHOR = "export default defineConfig((config) => ({\n"
_VITE_PROFILING_ALIAS = (
    '  resolve: { alias: { "react-dom/client": "react-dom/profiling" } },\n'
)


def _default_endpoint() -> str:
    """Resolve the OTLP/HTTP traces URL the browser exports to.

    Mirrors the SDK environment variables so one configuration covers both
    the backend exporter and the browser.

    Returns:
        The traces endpoint URL.
    """
    if traces := os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"):
        return traces
    base = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    return base.rstrip("/") + "/v1/traces"


def _patch_entry_client(content: str) -> str:
    """Load the browser module and profile the React root in ``entry.client.js``.

    Args:
        content: The current entry file.

    Returns:
        The patched entry file.
    """
    if _ENTRY_IMPORT in content:
        return content
    if _ENTRY_ROOT_ANCHOR not in content:
        logger.warning(
            "OtelPlugin: %r not found in %s; React render timing is disabled.",
            _ENTRY_ROOT_ANCHOR,
            Embed.ENTRY_PATH,
        )
    return _ENTRY_IMPORT + content.replace(_ENTRY_ROOT_ANCHOR, _ENTRY_ROOT_WRAPPED, 1)


def _patch_vite_config(content: str) -> str:
    """Alias react-dom to its profiling build so <Profiler> works in production.

    Args:
        content: The current ``vite.config.js``.

    Returns:
        The patched config.

    Raises:
        RuntimeError: If the config no longer has the expected shape.
    """
    if _VITE_PROFILING_ALIAS in content:
        return content
    if _VITE_CONFIG_ANCHOR not in content:
        msg = (
            f"OtelPlugin cannot enable render_timing: {_VITE_CONFIG_ANCHOR!r} "
            f"was not found in {ReactRouter.VITE_CONFIG_FILE}."
        )
        raise RuntimeError(msg)
    return content.replace(
        _VITE_CONFIG_ANCHOR, _VITE_CONFIG_ANCHOR + _VITE_PROFILING_ALIAS, 1
    )


@dataclass
class OtelPlugin(Plugin):
    """Ship the reflex-otel browser module with the compiled frontend.

    Add it to ``rx.Config(plugins=[...])``. Every event sent to the backend
    then carries a W3C ``traceparent`` (the backend event span becomes a
    child of the browser span), and web vitals, React commit timings and
    socket (re)connects are exported as spans.

    The endpoint must accept OTLP/HTTP from the browser (CORS). ``headers``
    are compiled into the public bundle, so never put secrets there.
    """

    # OTLP/HTTP traces URL; defaults follow OTEL_EXPORTER_OTLP_* env vars.
    endpoint: str = field(default_factory=_default_endpoint)
    # Resource service.name of the browser spans; defaults to "<app_name>-frontend".
    service_name: str | None = None
    # Extra HTTP headers sent by the browser exporter (public!).
    headers: dict[str, str] = field(default_factory=dict)
    web_vitals: bool = True
    # One `react.render` span per React commit (uses the react-dom profiling
    # build in production). Off by default because of the span volume.
    render_timing: bool = False

    def get_frontend_dependencies(self, **context: Any) -> tuple[str, ...]:
        """Return the npm packages the browser module imports.

        Args:
            context: The context for the plugin.

        Returns:
            The pinned package specifiers.
        """
        return FRONTEND_DEPENDENCIES

    def get_static_assets(self, **context: Any) -> list[tuple[Path, str]]:
        """Return the browser module to write into ``.web``.

        Args:
            context: The context for the plugin.

        Returns:
            The module path and its source.
        """
        return [(Path(BROWSER_MODULE), _BROWSER_MODULE_SOURCE.read_text())]

    def pre_compile(self, **context: Any) -> None:
        """Patch the client entry to load the module and profile the root.

        Args:
            context: The pre-compile plugin context.
        """
        context["add_modify_task"](Embed.ENTRY_PATH, _patch_entry_client)
        if self.render_timing:
            context["add_modify_task"](ReactRouter.VITE_CONFIG_FILE, _patch_vite_config)

    def update_env_json(self, **context: Any) -> dict[str, Any]:
        """Expose the browser configuration through ``env.json``.

        Args:
            context: The context for the plugin.

        Returns:
            The ``OTEL`` entry read by the browser module.
        """
        return {
            "OTEL": {
                "endpoint": self.endpoint,
                "service_name": self.service_name
                or f"{get_config().app_name}-frontend",
                "headers": self.headers,
                "web_vitals": self.web_vitals,
                "render_timing": self.render_timing,
                "version": Reflex.VERSION,
            }
        }
