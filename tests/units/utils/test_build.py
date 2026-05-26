"""Tests for reflex.utils.build."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
import reflex_base
from pytest_mock import MockerFixture

from reflex.plugins import EmbedPlugin, Plugin
from reflex.utils import build, path_ops


def test_compress_static_output_overwrites_stale_sidecars(
    tmp_path: Path, mocker: MockerFixture
):
    """Compression must rewrite sidecars whose source file has changed since the prior pass."""
    if path_ops.get_node_path() is None and path_ops.get_bun_path() is None:
        pytest.skip("Node.js or Bun is required for compression test")

    web_dir = tmp_path / ".web"
    web_dir.mkdir()
    compress_script = (
        Path(reflex_base.__file__).parent / ".templates/web/compress-static.js"
    )
    (web_dir / "compress-static.js").write_text(compress_script.read_text())

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    bundle = static_dir / "app.js"
    bundle.write_text("// fresh content " + "x" * 512)
    (static_dir / "app.js.gz").write_bytes(gzip.compress(b"// stale content"))

    mocker.patch("reflex.utils.build.prerequisites.get_web_dir", return_value=web_dir)

    build._compress_static_output(static_dir, ("gzip",))

    decompressed = gzip.decompress((static_dir / "app.js.gz").read_bytes())
    assert decompressed == bundle.read_bytes()


def test_build_compresses_after_post_build(tmp_path: Path, mocker: MockerFixture):
    """Compression must run after plugin.post_build so mutated files get fresh sidecars."""
    web_dir = tmp_path / ".web"
    static_dir = web_dir / "build" / "client"
    static_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<html>app</html>")

    calls: list[str] = []

    class TrackingPlugin(Plugin):
        def post_build(self, **context):
            calls.append("post_build")

    config = mocker.Mock()
    config.plugins = [TrackingPlugin()]
    config.frontend_compression_formats = ["gzip"]
    config.frontend_path = ""

    mocker.patch("reflex.utils.build.prerequisites.get_web_dir", return_value=web_dir)
    mocker.patch("reflex.utils.build.get_config", return_value=config)
    mocker.patch(
        "reflex.utils.build.js_runtimes.get_js_package_executor",
        return_value=(["fake-runtime"], None),
    )
    fake_process = mocker.Mock()
    fake_process.returncode = 0
    fake_process.wait.return_value = None
    mocker.patch("reflex.utils.build.processes.new_process", return_value=fake_process)
    mocker.patch("reflex.utils.build.processes.show_progress")
    mocker.patch("reflex.utils.build.path_ops.rm")

    def fake_compress(directory: Path, formats: tuple[str, ...]):
        calls.append("compress")

    mocker.patch(
        "reflex.utils.build._compress_static_output", side_effect=fake_compress
    )

    build.build()

    assert calls == ["post_build", "compress"]


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
