"""Tests for docs build-time Shiki highlighting."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from reflex_site_shared import static_shiki
from reflex_site_shared.components.blocks.code import (
    _copy_button,
    code_block,
    code_block_dark,
    doccmdoutput,
    literal_shiki_code_block,
)


@pytest.fixture(autouse=True)
def reset_static_shiki_state(monkeypatch):
    """Reset process-local Shiki state between tests."""
    monkeypatch.delenv(static_shiki.BUILD_PHASE_ENV, raising=False)
    monkeypatch.delenv(static_shiki.CACHE_DIR_ENV, raising=False)
    static_shiki._reset_for_testing()
    yield
    static_shiki._reset_for_testing()


def _write_cache(tmp_path, *requests):
    """Write a valid cache for the supplied requests."""
    entries = {
        static_shiki.request_key(request): {
            "request": request,
            "html": ('<pre class="shiki"><code>' + request["code"] + "</code></pre>"),
        }
        for request in requests
    }
    (tmp_path / static_shiki.CACHE_FILENAME).write_text(
        json.dumps({
            "schema_version": static_shiki.SCHEMA_VERSION,
            "shiki_version": static_shiki.SHIKI_VERSION,
            "entries": entries,
        })
    )


def test_request_key_is_stable_and_normalizes_aliases():
    """Equivalent requests have the same content-addressed key."""
    request = static_shiki.make_request("echo hi", language="bash")

    assert request == {
        "code": "echo hi",
        "language": "shellscript",
        "themes": {"dark": "one-dark-pro", "light": "one-light"},
    }
    assert static_shiki.request_key(request) == static_shiki.request_key(
        dict(reversed(request.items()))
    )


@pytest.mark.parametrize(
    ("alias", "language"),
    [
        ("console", "shellsession"),
        ("py", "python"),
        ("js", "javascript"),
        ("text", "plain"),
    ],
)
def test_request_normalizes_common_docs_language_aliases(alias, language):
    """Discovery uses Shiki's canonical identifiers for docs aliases."""
    assert static_shiki.make_request("code", language=alias)["language"] == language


def test_build_phase_defaults_to_client_and_rejects_unknown_values(monkeypatch):
    """Ordinary development keeps the existing client component path."""
    assert static_shiki.get_build_phase() == static_shiki.CLIENT_PHASE

    monkeypatch.setenv(static_shiki.BUILD_PHASE_ENV, "benchmark")

    with pytest.raises(static_shiki.StaticShikiError, match="benchmark"):
        static_shiki.get_build_phase()


def test_discovery_manifest_is_sorted_and_deduplicated(tmp_path, monkeypatch):
    """Discovery writes deterministic, content-addressed requests."""
    monkeypatch.setenv(static_shiki.CACHE_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(static_shiki.BUILD_PHASE_ENV, static_shiki.DISCOVERY_PHASE)
    second = static_shiki.make_request("print(2)", language="python")
    first = static_shiki.make_request("print(1)", language="python")

    static_shiki.register_request(second)
    static_shiki.register_request(first)
    static_shiki.register_request(second)
    manifest_path = static_shiki.flush_discovery_manifest()

    manifest = json.loads(manifest_path.read_text())
    assert list(manifest["requests"]) == sorted(manifest["requests"])
    assert len(manifest["requests"]) == 2
    assert manifest["schema_version"] == static_shiki.SCHEMA_VERSION
    assert manifest["shiki_version"] == static_shiki.SHIKI_VERSION


def test_plugin_flushes_only_the_discovery_manifest(tmp_path, monkeypatch):
    """The compiler hook writes the complete manifest before its process exits."""
    monkeypatch.setenv(static_shiki.CACHE_DIR_ENV, str(tmp_path))
    plugin = static_shiki.StaticShikiPlugin()
    request = static_shiki.make_request("print(1)", language="python")
    static_shiki.register_request(request)

    monkeypatch.setenv(static_shiki.BUILD_PHASE_ENV, static_shiki.CLIENT_PHASE)
    plugin.pre_compile()
    assert not (tmp_path / static_shiki.MANIFEST_FILENAME).exists()

    monkeypatch.setenv(static_shiki.BUILD_PHASE_ENV, static_shiki.DISCOVERY_PHASE)
    plugin.pre_compile()
    assert (tmp_path / static_shiki.MANIFEST_FILENAME).exists()


def test_plugin_prepares_static_cache_automatically_in_production(
    tmp_path, monkeypatch
):
    """A normal production compile owns discovery and cache generation."""
    calls = []
    web_dir = tmp_path / "web"
    web_dir.mkdir()

    class TemporaryDirectory:
        def __init__(self, **kwargs):
            calls.append(("temporary", kwargs))
            self.name = str(tmp_path / "build-cache")
            Path(self.name).mkdir()

        def cleanup(self):
            calls.append(("cleanup", self.name))

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    def generate_cache(runtime_dir):
        calls.append(("generate", runtime_dir))
        cache_dir = Path(static_shiki.get_cache_dir())
        _write_cache(cache_dir)
        return cache_dir / static_shiki.CACHE_FILENAME

    monkeypatch.setattr(static_shiki, "is_prod_mode", lambda: True)
    monkeypatch.setattr(static_shiki.prerequisites, "get_web_dir", lambda: web_dir)
    monkeypatch.setattr(static_shiki.tempfile, "TemporaryDirectory", TemporaryDirectory)
    monkeypatch.setattr(static_shiki.subprocess, "run", run)
    monkeypatch.setattr(static_shiki, "generate_cache", generate_cache)
    monkeypatch.setattr(static_shiki.path_ops, "get_bun_path", lambda: Path("/bun"))

    plugin = static_shiki.StaticShikiPlugin()

    assert plugin.get_frontend_dependencies() == ()
    child = next(call for call in calls if isinstance(call[0], list))
    assert child[0][:4] == [sys.executable, "-m", "reflex", "compile"]
    assert "--dry" in child[0]
    assert child[1]["env"][static_shiki.BUILD_PHASE_ENV] == (
        static_shiki.DISCOVERY_PHASE
    )
    install = next(call for call in calls if call[0][0:1] == ["/bun"])
    assert install[0][-2:] == ["--frozen-lockfile", "--ignore-scripts"]
    assert (tmp_path / "build-cache/shiki-runtime/bun.lock").exists()
    assert static_shiki.get_build_phase() == static_shiki.RENDER_PHASE
    assert Path(static_shiki.get_cache_dir()) == tmp_path / "build-cache/shiki-cache"

    plugin.post_build()
    assert static_shiki.get_build_phase() == static_shiki.CLIENT_PHASE
    assert static_shiki.CACHE_DIR_ENV not in os.environ
    assert ("cleanup", str(tmp_path / "build-cache")) in calls


def test_plugin_leaves_development_and_child_phases_unchanged(monkeypatch):
    """Development remains one-pass and the discovery child cannot recurse."""
    plugin = static_shiki.StaticShikiPlugin()
    monkeypatch.setattr(static_shiki, "is_prod_mode", lambda: False)
    assert plugin.get_frontend_dependencies() == ()

    monkeypatch.setattr(static_shiki, "is_prod_mode", lambda: True)
    monkeypatch.setenv(static_shiki.BUILD_PHASE_ENV, static_shiki.DISCOVERY_PHASE)
    assert plugin.get_frontend_dependencies() == ()


def test_cached_html_rejects_stale_and_missing_requests(tmp_path, monkeypatch):
    """A render build cannot silently use stale or incomplete output."""
    monkeypatch.setenv(static_shiki.CACHE_DIR_ENV, str(tmp_path))
    request = static_shiki.make_request("print(1)", language="python")
    key = static_shiki.request_key(request)
    (tmp_path / static_shiki.CACHE_FILENAME).write_text(
        json.dumps({
            "schema_version": static_shiki.SCHEMA_VERSION,
            "shiki_version": static_shiki.SHIKI_VERSION,
            "entries": {
                key: {
                    "request": {**request, "code": "print(2)"},
                    "html": "x",
                }
            },
        })
    )

    with pytest.raises(static_shiki.StaticShikiError, match="does not match"):
        static_shiki.get_cached_html(request)

    static_shiki._reset_for_testing()
    _write_cache(tmp_path)
    with pytest.raises(static_shiki.StaticShikiError, match="not present"):
        static_shiki.get_cached_html(request)


def test_cache_generation_rejects_empty_discovery(tmp_path, monkeypatch):
    """A false-success discovery compile cannot proceed to the final build."""
    monkeypatch.setenv(static_shiki.CACHE_DIR_ENV, str(tmp_path))
    (tmp_path / static_shiki.MANIFEST_FILENAME).write_text(
        json.dumps({
            "schema_version": static_shiki.SCHEMA_VERSION,
            "shiki_version": static_shiki.SHIKI_VERSION,
            "requests": {},
        })
    )

    with pytest.raises(static_shiki.StaticShikiError, match="no requests"):
        static_shiki.generate_cache(tmp_path / "web")


def test_literal_component_uses_client_during_development(monkeypatch):
    """Local development remains one-pass and supports dynamic client behavior."""
    sentinel = object()

    def client_component(code, **props):
        assert code == "print(1)"
        assert props == {"language": "python"}
        return sentinel

    monkeypatch.setenv(static_shiki.BUILD_PHASE_ENV, static_shiki.CLIENT_PHASE)

    assert (
        literal_shiki_code_block(
            "print(1)", language="python", client_component=client_component
        )
        is sentinel
    )


def test_literal_component_discovers_before_using_client(tmp_path, monkeypatch):
    """Discovery records a request without changing the rendered component."""
    sentinel = object()
    monkeypatch.setenv(static_shiki.CACHE_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(static_shiki.BUILD_PHASE_ENV, static_shiki.DISCOVERY_PHASE)

    result = literal_shiki_code_block(
        "output",
        language="console",
        client_component=lambda *_args, **_kwargs: sentinel,
    )

    assert result is sentinel
    manifest = json.loads(static_shiki.flush_discovery_manifest().read_text())
    assert next(iter(manifest["requests"].values()))["language"] == "shellsession"


def test_literal_component_renders_cached_html_without_client_import(
    tmp_path, monkeypatch
):
    """The final component contains HTML and no Shiki runtime dependency."""
    monkeypatch.setenv(static_shiki.CACHE_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(static_shiki.BUILD_PHASE_ENV, static_shiki.RENDER_PHASE)
    request = static_shiki.make_request("print(1)", language="python")
    _write_cache(tmp_path, request)

    component = literal_shiki_code_block(
        "print(1)", language="python", class_name="code-block", can_copy=True
    )

    assert not any(
        "shiki" in library.lower() for library in component._get_all_imports()
    )
    rendered = str(component.render())
    assert "static-shiki code-block" in rendered
    assert "print(1)" in rendered


def test_all_literal_docs_code_paths_use_cached_html(tmp_path, monkeypatch):
    """Dark demos and command output cannot reintroduce client-side Shiki."""
    monkeypatch.setenv(static_shiki.CACHE_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(static_shiki.BUILD_PHASE_ENV, static_shiki.RENDER_PHASE)
    requests = [
        static_shiki.make_request("print(1)", language="python"),
        static_shiki.make_request(
            "reflex run",
            language="bash",
            themes={"light": "ayu-dark", "dark": "ayu-dark"},
        ),
        static_shiki.make_request(
            "Running...",
            language="log",
            themes={"light": "ayu-dark", "dark": "ayu-dark"},
        ),
    ]
    _write_cache(tmp_path, *requests)

    components = (
        code_block("print(1)", "python"),
        code_block_dark("print(1)", "python"),
        doccmdoutput("reflex run", "Running..."),
    )

    for component in components:
        assert not any(
            "shiki" in library.lower() for library in component._get_all_imports()
        )


def test_static_component_respects_disabled_copy_button(tmp_path, monkeypatch):
    """Honor an explicitly disabled custom copy control like the client block."""
    monkeypatch.setenv(static_shiki.CACHE_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(static_shiki.BUILD_PHASE_ENV, static_shiki.RENDER_PHASE)
    request = static_shiki.make_request("print(1)", language="python")
    _write_cache(tmp_path, request)

    component = literal_shiki_code_block(
        "print(1)",
        language="python",
        can_copy=True,
        copy_button=False,
    )

    assert 'aria-label":"Copy code' not in str(component.render())


def test_request_rejects_dynamic_code_and_unsupported_options(monkeypatch):
    """The static path fails clearly for values it cannot reproduce exactly."""
    import reflex as rx

    with pytest.raises(static_shiki.StaticShikiError, match="literal string"):
        static_shiki.make_request(rx.Var.create("dynamic"), language="python")

    monkeypatch.setenv(static_shiki.BUILD_PHASE_ENV, static_shiki.DISCOVERY_PHASE)
    with pytest.raises(static_shiki.StaticShikiError, match="not supported"):
        literal_shiki_code_block("print(1)", language="python", use_transformers=True)


def test_docs_code_block_discovers_before_using_original_memo(tmp_path, monkeypatch):
    """Discovery records literals without exposing them to client prop validation."""
    sentinel = object()

    def plain_code_block(**props):
        assert props == {"code": "output", "language": "console"}
        return sentinel

    monkeypatch.setenv(static_shiki.BUILD_PHASE_ENV, static_shiki.DISCOVERY_PHASE)
    monkeypatch.setenv(static_shiki.CACHE_DIR_ENV, str(tmp_path))
    monkeypatch.setitem(code_block.__globals__, "_plain_code_block", plain_code_block)

    assert code_block("output", "console") is sentinel
    manifest = json.loads(static_shiki.flush_discovery_manifest().read_text())
    assert next(iter(manifest["requests"].values()))["language"] == "shellsession"


def test_copy_button_strips_transformer_markers():
    """Static copy controls copy source without display-only annotations."""
    button = _copy_button('print("hello")  # [!code highlight]')

    rendered = str(button.render())
    assert "hello" in rendered
    assert "[!code highlight]" not in rendered
    assert button.type._var_value == "button"


def test_dark_tokens_do_not_paint_the_block_background():
    """Token spans stay transparent instead of becoming gray rectangles."""
    stylesheet = (
        Path(__file__).parents[1] / "assets" / "tailwind-theme.css"
    ).read_text()

    rule = stylesheet.split(".dark .static-shiki .shiki span", maxsplit=1)[1]
    rule = rule.split("}", maxsplit=1)[0]
    assert "background-color: transparent !important" in rule


def test_intro_route_avoids_runtime_markdown_highlighter():
    """Static prose must not pull React Syntax Highlighter into the key route."""
    source = (Path(__file__).parents[2] / "getting_started/introduction.md").read_text()

    assert "rx.markdown(" not in source
    assert 'href="/pages/overview/"' in source


def test_docs_register_static_shiki_plugin_unconditionally():
    """Production highlighting must not depend on an experiment selector."""
    from rxconfig import config

    assert any(
        isinstance(plugin, static_shiki.StaticShikiPlugin) for plugin in config.plugins
    )


def test_shiki_runtime_has_a_frozen_direct_dependency():
    """The isolated generator cannot drift from the validated Shiki version."""
    runtime_dir = Path(static_shiki.__file__).with_name("static_shiki_runtime")
    package = json.loads((runtime_dir / "package.json").read_text())

    assert package["dependencies"] == {"shiki": static_shiki.SHIKI_VERSION}
    assert (runtime_dir / "bun.lock").is_file()
