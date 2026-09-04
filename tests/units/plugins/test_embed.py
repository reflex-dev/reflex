"""Unit tests for the embed plugin."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from reflex_base import constants
from reflex_base.plugins.embed import (
    EmbedPlugin,
    _inject_vite_dev_preview,
    _mount_attrs_for_selector,
    _render_dev_host_html,
    compile_embed_manifest,
    get_embed_plugin,
)

from reflex.compiler import utils


def test_explicit_args_set_fields():
    plugin = EmbedPlugin(mount_target="#root", embed_origin="https://cdn.example")
    assert plugin.mount_target == "#root"
    assert plugin.embed_origin == "https://cdn.example"


def test_env_fallback_populates_fields(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REFLEX_MOUNT_TARGET", "#widget")
    monkeypatch.setenv("REFLEX_EMBED_ORIGIN", "https://cdn.example")
    plugin = EmbedPlugin()
    assert plugin.mount_target == "#widget"
    assert plugin.embed_origin == "https://cdn.example"


def test_explicit_args_override_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REFLEX_MOUNT_TARGET", "#env-target")
    plugin = EmbedPlugin(mount_target="#explicit")
    assert plugin.mount_target == "#explicit"


def test_missing_mount_target_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("REFLEX_MOUNT_TARGET", raising=False)
    monkeypatch.delenv("REFLEX_EMBED_ORIGIN", raising=False)
    with pytest.raises(ValueError, match="mount_target"):
        EmbedPlugin()


def test_update_env_json_returns_mount_target():
    plugin = EmbedPlugin(mount_target="#widget")
    assert plugin.update_env_json() == {"MOUNT_TARGET": "#widget"}


def test_provides_entry_client_is_true():
    plugin = EmbedPlugin(mount_target="#widget")
    assert plugin.provides_entry_client() is True


def test_pre_compile_registers_save_tasks():
    plugin = EmbedPlugin(mount_target="#root")
    saved: list[tuple] = []

    def add_save_task(task, *args, **kwargs):
        saved.append((task, args, kwargs))

    plugin.pre_compile(
        add_save_task=add_save_task,
        add_modify_task=lambda *_args, **_kwargs: None,
        radix_themes_plugin=None,
        unevaluated_pages=[],
    )

    assert len(saved) == 2
    task_names = {task.__name__ for task, _, _ in saved}
    assert task_names == {"_embed_entry_task", "_embed_manifest_task"}


def test_get_embed_plugin_returns_instance(mocker: MockerFixture):
    plugin = EmbedPlugin(mount_target="#root")
    config = mocker.Mock()
    config.plugins = [plugin]
    mocker.patch("reflex_base.config.get_config", return_value=config)
    assert get_embed_plugin() is plugin


def test_get_embed_plugin_returns_none_when_absent(mocker: MockerFixture):
    config = mocker.Mock()
    config.plugins = []
    mocker.patch("reflex_base.config.get_config", return_value=config)
    assert get_embed_plugin() is None


@pytest.mark.parametrize(
    ("selector", "expected_attrs"),
    [
        ("#reflex-root", {"id": "reflex-root"}),
        (".widget", {"class": "widget"}),
        ("[data-mount]", {"data-mount": ""}),
        ('[data-mount="x"]', {"data-mount": "x"}),
        ("#reflex-root.widget", {"id": "reflex-root", "class": "widget"}),
    ],
)
def test_mount_attrs_for_selector_parses_simple_selectors(
    selector: str, expected_attrs: dict[str, str]
):
    attrs, ok = _mount_attrs_for_selector(selector)
    assert ok is True
    assert attrs == expected_attrs


def test_mount_attrs_for_selector_falls_back_for_complex():
    attrs, ok = _mount_attrs_for_selector("div > .child")
    assert ok is False
    assert attrs == {"id": "reflex-dev-root"}


def test_render_dev_host_html_is_minimal():
    html = _render_dev_host_html("#reflex-root")
    assert 'id="reflex-root"' in html
    assert 'src="/app/entry.client.js"' in html
    assert "<style" not in html
    assert "banner" not in html.lower()


def _noop_save_task(task, *args, **kwargs) -> None:
    return None


def test_dev_preview_off_by_default_skips_modify_task():
    plugin = EmbedPlugin(mount_target="#root")
    modified: list = []
    plugin.pre_compile(
        add_save_task=_noop_save_task,
        add_modify_task=lambda path, fn: modified.append((path, fn)),
        radix_themes_plugin=None,
        unevaluated_pages=[],
    )
    assert modified == []


def test_dev_preview_enabled_registers_modify_task():
    plugin = EmbedPlugin(mount_target="#root", dev_preview=True)
    modified: list = []
    plugin.pre_compile(
        add_save_task=_noop_save_task,
        add_modify_task=lambda path, fn: modified.append((path, fn)),
        radix_themes_plugin=None,
        unevaluated_pages=[],
    )
    assert any(path == "vite.config.js" for path, _ in modified)


def test_inject_vite_dev_preview_adds_plugin_to_array():
    original = (
        'import { reactRouter } from "@react-router/dev/vite";\n'
        "function alwaysUseReactDomServerNode() { return {}; }\n"
        "export default defineConfig((config) => ({\n"
        '  base: "/",\n'
        "  plugins: [\n"
        "    alwaysUseReactDomServerNode(),\n"
        "    reactRouter(),\n"
        "  ],\n"
        "}));\n"
    )
    modify = _inject_vite_dev_preview("#reflex-root")
    out = modify(original)
    assert "function reflexEmbedDevPreview" in out
    assert out.index("reflexEmbedDevPreview(") < out.index(
        "alwaysUseReactDomServerNode(),"
    )


def test_inject_vite_dev_preview_is_idempotent():
    original = (
        "function reflexEmbedDevPreview() {}\n"
        "export default defineConfig((config) => ({}));"
    )
    modify = _inject_vite_dev_preview("#reflex-root")
    assert modify(original) == original


_ENTRY_RE = re.compile(
    r'\{\s*path:\s*"([^"]*)",\s*load:\s*\(\)\s*=>\s*import\("([^"]*)"\)\s*\}'
)


def test_compile_embed_manifest_pairs_translated_paths_with_specifiers(
    mocker: MockerFixture, tmp_path: Path
):
    """Each route produces one entry pairing its React-Router path with its import specifier."""
    mocker.patch("reflex.utils.prerequisites.get_web_dir", return_value=tmp_path)

    routes = [
        "index",
        "users/[id]",
        "posts/[[slug]]",
        "docs/[[...splat]]",
        constants.Page404.SLUG,
    ]
    expected_pairs = [
        ("", utils.get_page_import_specifier("index")),
        ("users/:id", utils.get_page_import_specifier("users/[id]")),
        ("posts/:slug?", utils.get_page_import_specifier("posts/[[slug]]")),
        ("docs/*", utils.get_page_import_specifier("docs/[[...splat]]")),
        ("*", utils.get_page_import_specifier(constants.Page404.SLUG)),
    ]

    output_path, code = compile_embed_manifest(routes)

    assert output_path == str(
        tmp_path / constants.Dirs.PAGES / constants.Embed.MANIFEST_FILE
    )
    assert _ENTRY_RE.findall(code) == expected_pairs


def _make_static_dir(tmp_path: Path, entry_names: list[str]) -> Path:
    """Create a fake Vite static dir with ``assets/<name>`` for each entry.

    Returns:
        The created static-dir path.
    """
    static_dir = tmp_path / "client"
    assets = static_dir / "assets"
    assets.mkdir(parents=True)
    for name in entry_names:
        (assets / name).write_text("// chunk\n")
    return static_dir


def test_post_build_emits_shim_pointing_at_hashed_asset(tmp_path: Path):
    static_dir = _make_static_dir(tmp_path, ["entry.client-abc123.js"])
    plugin = EmbedPlugin(mount_target="#root")

    plugin.post_build(static_dir=static_dir)

    shim = static_dir / constants.Embed.ENTRY_PATH
    assert shim.exists()
    assert shim.read_text() == 'import "/assets/entry.client-abc123.js";\n'


def test_post_build_prefixes_embed_origin(tmp_path: Path):
    static_dir = _make_static_dir(tmp_path, ["entry.client-deadbeef.js"])
    plugin = EmbedPlugin(mount_target="#root", embed_origin="https://cdn.example.com/")

    plugin.post_build(static_dir=static_dir)

    shim = static_dir / constants.Embed.ENTRY_PATH
    assert (
        shim.read_text()
        == 'import "https://cdn.example.com/assets/entry.client-deadbeef.js";\n'
    )


def test_post_build_raises_when_no_entry_chunk(tmp_path: Path):
    static_dir = _make_static_dir(tmp_path, [])
    plugin = EmbedPlugin(mount_target="#root")

    with pytest.raises(RuntimeError, match="Expected exactly one Vite entry chunk"):
        plugin.post_build(static_dir=static_dir)


def test_post_build_raises_when_multiple_entry_chunks(tmp_path: Path):
    static_dir = _make_static_dir(
        tmp_path, ["entry.client-aaa.js", "entry.client-bbb.js"]
    )
    plugin = EmbedPlugin(mount_target="#root")

    with pytest.raises(
        RuntimeError, match=r"Expected exactly one Vite entry chunk.*found 2: \["
    ):
        plugin.post_build(static_dir=static_dir)
