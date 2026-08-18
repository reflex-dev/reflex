"""Tests for the reflex_otel browser plugin."""

from pathlib import Path

import pytest
from reflex_base.compiler.templates import vite_config_template
from reflex_base.constants.base import ReactRouter
from reflex_base.constants.compiler import Embed
from reflex_otel.plugin import (
    BROWSER_MODULE,
    FRONTEND_DEPENDENCIES,
    OtelPlugin,
    _patch_entry_client,
    _patch_vite_config,
)


def test_default_endpoint_follows_otel_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert OtelPlugin().endpoint == "http://localhost:4318/v1/traces"
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318/")
    assert OtelPlugin().endpoint == "http://collector:4318/v1/traces"
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "https://x/t")
    assert OtelPlugin().endpoint == "https://x/t"
    assert OtelPlugin(endpoint="http://y").endpoint == "http://y"


def test_frontend_dependencies_and_asset():
    plugin = OtelPlugin()
    assert plugin.get_frontend_dependencies() == FRONTEND_DEPENDENCIES
    ((path, source),) = plugin.get_static_assets()
    assert path == Path(BROWSER_MODULE)
    assert "window.__reflex_otel" in source
    assert "export const OtelRoot" in source


def test_env_json_entry():
    plugin = OtelPlugin(
        endpoint="http://c/v1/traces", headers={"x": "y"}, web_vitals=False
    )
    entry = plugin.update_env_json()["OTEL"]
    assert entry["endpoint"] == "http://c/v1/traces"
    assert entry["headers"] == {"x": "y"}
    assert entry["web_vitals"] is False
    assert entry["render_timing"] is False
    assert entry["sample_rate"] is OtelPlugin.sample_rate
    rate = 0.5
    assert OtelPlugin(sample_rate=rate).update_env_json()["OTEL"]["sample_rate"] is rate
    assert entry["service_name"].endswith("-frontend")
    assert (
        OtelPlugin(service_name="web").update_env_json()["OTEL"]["service_name"]
        == "web"
    )


def _pre_compile_tasks(plugin: OtelPlugin) -> list:
    tasks = []
    plugin.pre_compile(
        add_save_task=None,
        add_modify_task=lambda path, fn: tasks.append((path, fn)),
        radix_themes_plugin=None,
        unevaluated_pages=[],
    )
    return tasks


def test_pre_compile_patches_entry(caplog: pytest.LogCaptureFixture):
    ((path, fn),) = _pre_compile_tasks(OtelPlugin())
    assert path == Embed.ENTRY_PATH
    entry = "import x;\nhydrateRoot(document, createElement(HydratedRouter));\n"
    patched = fn(entry)
    assert patched.startswith('import { OtelRoot } from "$/utils/otel";\n')
    assert "createElement(OtelRoot, null, createElement(HydratedRouter))" in patched
    assert fn(patched) == patched
    with caplog.at_level("WARNING"):
        assert _patch_entry_client("other();\n") == (
            'import { OtelRoot } from "$/utils/otel";\nother();\n'
        )
    assert "render timing is disabled" in caplog.text


def test_render_timing_aliases_react_dom_profiling():
    (_, (path, fn)) = _pre_compile_tasks(OtelPlugin(render_timing=True))
    assert path == ReactRouter.VITE_CONFIG_FILE
    config = vite_config_template(
        base="/",
        hmr=False,
        force_full_reload=False,
        experimental_hmr=False,
        sourcemap=False,
    )
    patched = fn(config)
    # A single `resolve` key: a duplicate one would be overridden by the last.
    assert patched.count("resolve: {") == 1
    resolve_block = patched[patched.index("resolve: {") :]
    assert (
        'find: "react-dom/client", replacement: "react-dom/profiling"' in resolve_block
    )
    assert fn(patched) == patched
    with pytest.raises(RuntimeError, match="render_timing"):
        _patch_vite_config("export default {};\n")
