"""Tests for reflex.utils.build."""

from __future__ import annotations

import json
from pathlib import Path

from pytest_mock import MockerFixture

from reflex.plugins import EmbedPlugin, Plugin
from reflex.utils import build


def _patch_env_json(
    mocker: MockerFixture, tmp_path: Path, plugins: list[Plugin] | None = None
):
    web_dir = tmp_path / ".web"
    web_dir.mkdir()
    mocker.patch("reflex.utils.build.prerequisites.get_web_dir", return_value=web_dir)
    config = mocker.Mock()
    config.transport = "websocket"
    config.plugins = plugins or []
    mocker.patch("reflex.utils.build.get_config", return_value=config)
    mocker.patch("reflex.utils.build.is_in_app_harness", return_value=False)
    return web_dir


def test_set_env_json_merges_plugin_contributions(
    tmp_path: Path, mocker: MockerFixture
):
    """``update_env_json`` returns merge on top of the base env dict."""
    web_dir = _patch_env_json(
        mocker, tmp_path, plugins=[EmbedPlugin(mount_target="#reflex-root")]
    )

    build.set_env_json()

    env = json.loads((web_dir / "env.json").read_text())
    assert env["MOUNT_TARGET"] == "#reflex-root"
    assert env["TRANSPORT"] == "websocket"


def test_set_env_json_omits_plugin_keys_when_plugin_absent(
    tmp_path: Path, mocker: MockerFixture
):
    """Plugin-contributed keys are absent from env.json when no plugin contributes."""
    web_dir = _patch_env_json(mocker, tmp_path, plugins=[])

    build.set_env_json()

    env = json.loads((web_dir / "env.json").read_text())
    assert "MOUNT_TARGET" not in env
    assert env["TRANSPORT"] == "websocket"


def test_set_env_json_later_plugin_wins(tmp_path: Path, mocker: MockerFixture):
    """Later plugins override earlier ones on conflicting keys."""

    class FirstPlugin(Plugin):
        def update_env_json(self, **context):
            return {"SHARED": "first", "ONLY_FIRST": 1}

    class SecondPlugin(Plugin):
        def update_env_json(self, **context):
            return {"SHARED": "second", "ONLY_SECOND": 2}

    web_dir = _patch_env_json(mocker, tmp_path, plugins=[FirstPlugin(), SecondPlugin()])

    build.set_env_json()

    env = json.loads((web_dir / "env.json").read_text())
    assert env["SHARED"] == "second"
    assert env["ONLY_FIRST"] == 1
    assert env["ONLY_SECOND"] == 2
