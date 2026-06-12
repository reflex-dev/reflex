"""Tests for the rendered frontend-skeleton output."""

from __future__ import annotations

import json

import pytest

from reflex.utils import frontend_skeleton


def test_package_json_has_no_inspector_specific_deps():
    """Inspector dev deps come from ``get_frontend_development_dependencies``.

    They are installed via ``bun add -d`` after the base install rather than
    being baked into the package.json template, so the rendered template
    must not name ``launch-editor``.
    """
    payload = json.loads(frontend_skeleton._compile_package_json())
    assert "launch-editor" not in payload.get("devDependencies", {})


def test_vite_config_template_is_plugin_agnostic(monkeypatch: pytest.MonkeyPatch):
    """The Vite template renders nothing inspector-specific by itself.

    Plugin-driven extras (e.g. the inspector import + plugin call) are
    injected later via ``add_modify_task`` from ``pre_compile``.
    """
    import reflex as rx

    config = rx.Config(app_name="test")
    monkeypatch.setattr(frontend_skeleton, "get_config", lambda: config)
    rendered = frontend_skeleton._compile_vite_config(config)
    assert "reflexInspectorPlugin" not in rendered
    assert "reflex-inspector-plugin.js" not in rendered
