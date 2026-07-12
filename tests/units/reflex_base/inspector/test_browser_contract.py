"""Contract test pinning the Python <-> JS inspector boundary.

The browser script ``inspector.js`` is hand-written; the head ``<script>``
tags are emitted by ``FrontendInspectorPlugin.get_head_components``. Both
refer to the same constants (``data-rx`` attribute, ``/__reflex/...`` URLs,
``__REFLEX_INSPECTOR_CONFIG__`` window key, ``shortcut`` payload key). This
test asserts that every constant defined on the Python side appears verbatim
in the JS, so a future rename on either side fails CI instead of desyncing
silently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reflex_base import inspector
from reflex_base.constants import Env
from reflex_base.plugins.frontend_inspector import _asset_source_dir

import reflex as rx


@pytest.fixture
def inspector_js_text() -> str:
    return _asset_source_dir().joinpath("inspector.js").read_text()


@pytest.mark.parametrize(
    "constant",
    [
        inspector.DATA_ATTR,
        inspector.SOURCE_MAP_URL,
        inspector.INSPECTOR_CSS_URL,
        inspector.EDITOR_URL,
        inspector.WINDOW_CONFIG_KEY,
        inspector.SHORTCUT_CONFIG_KEY,
    ],
)
def test_browser_script_references_python_constants(
    inspector_js_text: str, constant: str
):
    """Every shared constant must appear verbatim in ``inspector.js``."""
    assert constant in inspector_js_text, (
        f"Inspector JS does not reference Python constant {constant!r}; "
        f"either the Python constant or the JS file drifted."
    )


def test_head_payload_uses_shortcut_key(monkeypatch: pytest.MonkeyPatch):
    """The window-config payload uses the agreed ``shortcut`` key.

    The browser reads ``config.shortcut`` — if the Python side ever
    renames the key, this test fails before it ships.
    """
    monkeypatch.setenv("REFLEX_ENV_MODE", Env.DEV.value)
    plugin = rx.plugins.FrontendInspectorPlugin()
    components = plugin._build_head_components()
    config_script = components[0].render()
    rendered = json.dumps(config_script)
    assert inspector.SHORTCUT_CONFIG_KEY in rendered
    assert inspector.WINDOW_CONFIG_KEY in rendered


def test_asset_directory_exists():
    """The bundled asset directory must exist where the plugin reads from."""
    src_dir = _asset_source_dir()
    assert src_dir.is_dir(), f"Inspector asset directory missing: {src_dir}"
    assert (src_dir / "inspector.js").is_file()
    assert (src_dir / "inspector.css").is_file()
    assert (src_dir / "dev_server_middleware.js").is_file()


def test_source_map_url_matches_emit_path(tmp_path: Path):
    """``SOURCE_MAP_URL`` must resolve to the path the plugin writes to."""
    expected_disk_path = (
        tmp_path / inspector.PUBLIC_DIRNAME / inspector.SOURCE_MAP_FILENAME
    )
    expected_url_path = inspector.SOURCE_MAP_URL.lstrip("/")
    assert expected_disk_path.relative_to(tmp_path).as_posix() == expected_url_path
