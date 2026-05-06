"""Tests for reflex.utils.build."""

from __future__ import annotations

import json
from pathlib import Path

from pytest_mock import MockerFixture

from reflex.plugins import EmbedPlugin
from reflex.utils import build


def _patch_env_json(
    mocker: MockerFixture, tmp_path: Path, embed_plugin: EmbedPlugin | None = None
):
    web_dir = tmp_path / ".web"
    web_dir.mkdir()
    mocker.patch("reflex.utils.build.prerequisites.get_web_dir", return_value=web_dir)
    config = mocker.Mock()
    config.transport = "websocket"
    mocker.patch("reflex.utils.build.get_config", return_value=config)
    mocker.patch("reflex.utils.build.get_embed_plugin", return_value=embed_plugin)
    mocker.patch("reflex.utils.build.is_in_app_harness", return_value=False)
    return web_dir


def test_set_env_json_includes_mount_target(tmp_path: Path, mocker: MockerFixture):
    """MOUNT_TARGET appears in env.json when EmbedPlugin is registered."""
    web_dir = _patch_env_json(
        mocker, tmp_path, embed_plugin=EmbedPlugin(mount_target="#reflex-root")
    )

    build.set_env_json()

    env = json.loads((web_dir / "env.json").read_text())
    assert env["MOUNT_TARGET"] == "#reflex-root"
    assert env["TRANSPORT"] == "websocket"


def test_set_env_json_mount_target_null_when_unset(
    tmp_path: Path, mocker: MockerFixture
):
    """MOUNT_TARGET is null in env.json when EmbedPlugin is not registered."""
    web_dir = _patch_env_json(mocker, tmp_path, embed_plugin=None)

    build.set_env_json()

    env = json.loads((web_dir / "env.json").read_text())
    assert env["MOUNT_TARGET"] is None
