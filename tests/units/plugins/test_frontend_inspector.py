"""Tests for the FrontendInspectorPlugin."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from reflex_base import inspector
from reflex_base.constants import Env
from reflex_base.plugins.frontend_inspector import (
    FrontendInspectorPlugin,
    _inject_inspector_into_vite_config,
    _vite_plugin_text,
)

from reflex.utils import frontend_skeleton


def test_vite_plugin_is_dev_only():
    """The rendered Vite plugin file is ``apply: 'serve'`` (dev only)."""
    rendered = _vite_plugin_text(editor="")
    assert "apply: 'serve'" in rendered
    assert "configureServer" in rendered
    assert "reflexEditorMiddleware" in rendered


def test_vite_plugin_omits_editor_when_unset():
    rendered = _vite_plugin_text(editor="")
    assert "REFLEX_EDITOR" not in rendered


def test_vite_plugin_threads_editor_through():
    rendered = _vite_plugin_text(editor="code -g")
    assert 'process.env.REFLEX_EDITOR ||= "code -g";' in rendered


def test_inject_inspector_into_vite_config_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
):
    """Re-injecting into an already-modified Vite config is a no-op."""
    import reflex as rx

    config = rx.Config(app_name="test")
    monkeypatch.setattr(frontend_skeleton, "get_config", lambda: config)
    rendered = frontend_skeleton._compile_vite_config(config)

    once = _inject_inspector_into_vite_config(rendered)
    assert "reflexInspectorPlugin()" in once
    assert './reflex-inspector-plugin.js"' in once
    # One import + one plugin call; idempotency means counts stay at 1.
    assert once.count("reflexInspectorPlugin()") == 1
    twice = _inject_inspector_into_vite_config(once)
    assert twice == once


def test_static_assets_include_browser_files_and_plugin(
    monkeypatch: pytest.MonkeyPatch,
):
    """Active plugin yields the JS/CSS assets and the Vite plugin file."""
    monkeypatch.setenv("REFLEX_ENV_MODE", Env.DEV.value)
    plugin = FrontendInspectorPlugin()
    paths = {Path(p).as_posix(): content for p, content in plugin.get_static_assets()}
    public = Path("public") / inspector.PUBLIC_DIRNAME
    assert (public / "inspector.js").as_posix() in paths
    assert (public / "inspector.css").as_posix() in paths
    assert (public / "dev_server_middleware.js").as_posix() in paths
    assert (public / inspector.SOURCE_MAP_FILENAME).as_posix() in paths
    assert inspector.INSPECTOR_PLUGIN_FILE in paths
    plugin_text = paths[inspector.INSPECTOR_PLUGIN_FILE]
    assert isinstance(plugin_text, str)
    assert "reflexInspectorPlugin" in plugin_text


def test_inactive_plugin_yields_nothing(monkeypatch: pytest.MonkeyPatch):
    """Every emission hook returns empty under ``REFLEX_ENV_MODE=prod``."""
    monkeypatch.setenv("REFLEX_ENV_MODE", Env.PROD.value)
    plugin = FrontendInspectorPlugin()
    assert plugin.get_static_assets() == ()
    assert plugin.get_frontend_development_dependencies() == []


def _noop_save_task(task, /, *args, **kwargs):
    return None


def test_pre_compile_registers_modify_task(monkeypatch: pytest.MonkeyPatch):
    """``pre_compile`` queues a Vite-config modify task when active."""
    import reflex_base.constants as base_constants

    monkeypatch.setenv("REFLEX_ENV_MODE", Env.DEV.value)
    plugin = FrontendInspectorPlugin()
    queued: list[tuple[str, Callable[[str], str]]] = []

    plugin.pre_compile(
        add_save_task=_noop_save_task,
        add_modify_task=lambda path, fn: queued.append((path, fn)),
        radix_themes_plugin=None,
        unevaluated_pages=[],
    )
    assert queued
    target_path, modify_fn = queued[0]
    assert target_path == base_constants.ReactRouter.VITE_CONFIG_FILE
    sample = (
        'import safariCacheBustPlugin from "./vite-plugin-safari-cachebust";\n'
        "    safariCacheBustPlugin(),\n"
    )
    assert "reflexInspectorPlugin()" in modify_fn(sample)


def test_pre_compile_inactive_does_nothing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REFLEX_ENV_MODE", Env.PROD.value)
    plugin = FrontendInspectorPlugin()
    queued: list[tuple[str, Callable[[str], str]]] = []
    plugin.pre_compile(
        add_save_task=_noop_save_task,
        add_modify_task=lambda path, fn: queued.append((path, fn)),
        radix_themes_plugin=None,
        unevaluated_pages=[],
    )
    assert queued == []
