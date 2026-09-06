"""Regression coverage for opt-in reuse of production frontend builds."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from reflex.plugins import Plugin
from reflex.utils import build


@pytest.fixture
def cached_build(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    """Create a frontend whose simulated build reads real source files.

    Returns:
        The frontend directory, mutable config, and build subprocess mock.
    """
    monkeypatch.setenv("REFLEX_FRONTEND_BUILD_CACHE", "true")
    web = tmp_path / ".web"
    (web / "app").mkdir(parents=True)
    (web / "app/page.js").write_text("original")
    (web / "public").mkdir()
    (web / "public/style.css").write_text("body{color:red}")
    (web / "node_modules/package").mkdir(parents=True)
    (web / "node_modules/package/index.js").write_text("old")
    (web / "package.json").write_text('{"scripts":{"export":"react-router build"}}')
    (web / "bun.lock").write_text("lock")
    (web / "env.json").write_text('{"EVENT":"https://first.example/_event"}')
    (web / "reflex.json").write_text('{"version":"1.0.0","project_hash":42}')
    runtime = tmp_path / "runtime"
    runtime.write_text("runtime")
    config = mocker.Mock()
    config.plugins = []
    config.frontend_compression_formats = ["gzip"]
    config.frontend_path = ""
    mocker.patch.object(build.prerequisites, "get_web_dir", return_value=web)
    mocker.patch.object(build, "get_config", return_value=config)
    mocker.patch.object(build.path_ops, "get_node_path", return_value=str(runtime))
    mocker.patch.object(
        build.js_runtimes,
        "get_js_package_executor",
        return_value=([str(runtime)], None),
    )

    def compile_frontend(*args, **kwargs):
        output = web / "build/client"
        output.mkdir(parents=True)
        if config.frontend_path:
            (output / config.frontend_path.strip("/")).mkdir(parents=True)
        (output / "index.html").write_text((web / "app/page.js").read_text())
        (output / "bundle.js").write_text("compiled")
        return mocker.Mock(returncode=0)

    process = mocker.patch.object(
        build.processes, "new_process", side_effect=compile_frontend
    )
    mocker.patch.object(build.processes, "show_progress")
    mocker.patch.object(build, "_compress_static_output")
    return web, config, process


@pytest.mark.skipif(os.name == "nt", reason="Cache uses POSIX change timestamps")
def test_unchanged_build_reuses_pristine_output(cached_build, mocker: MockerFixture):
    """Reuse Vite output while executing post-build work on every invocation."""
    web, config, process = cached_build
    compress = mocker.patch.object(build, "_compress_static_output")
    calls = []

    class AppendPlugin(Plugin):
        def post_build(self, **context):
            calls.append(len(calls) + 1)
            index = context["static_dir"] / "index.html"
            index.write_text(index.read_text() + f" hook{calls[-1]}")

    config.plugins = [AppendPlugin()]
    config.frontend_path = "/site"
    build.build()
    build.build()
    assert process.call_count == 1
    assert calls == [1, 2]
    assert (web / "build/client/site/index.html").read_text() == "original hook2"
    assert not (web / "build/client/site/site").exists()
    assert compress.call_count == 2


@pytest.mark.skipif(os.name == "nt", reason="Cache uses POSIX change timestamps")
def test_telemetry_timestamps_do_not_invalidate_build(cached_build):
    """Only the two private telemetry timestamps may be ignored."""
    web, _, process = cached_build
    build.build()
    metadata = web / "reflex.json"
    data = json.loads(metadata.read_text())
    data.update(last_reflex_run_datetime="later", last_version_check_datetime="later")
    metadata.write_text(json.dumps(data))
    build.build()
    assert process.call_count == 1
    data["version"] = "2.0.0"
    metadata.write_text(json.dumps(data))
    build.build()
    assert process.call_count == 2


@pytest.mark.parametrize(
    "name", ["app/page.js", "public/style.css", "env.json", "bun.lock", "package.json"]
)
def test_changed_build_inputs_rebuild(cached_build, name: str):
    """Changes to code, assets, URLs, locks, or package scripts invalidate output."""
    web, _, process = cached_build
    build.build()
    target = web / name
    target.write_text(target.read_text() + " ")
    build.build()
    assert process.call_count == 2


def test_dependency_edit_with_restored_mtime_rebuilds(cached_build):
    """POSIX ctime detects same-length dependency edits even if mtime is restored."""
    web, _, process = cached_build
    build.build()
    dependency = web / "node_modules/package/index.js"
    before = dependency.stat()
    dependency.write_text("new")
    os.utime(dependency, ns=(before.st_atime_ns, before.st_mtime_ns))
    build.build()
    assert process.call_count == 2


def test_disabled_cache_forces_and_refreshes_build(cached_build, monkeypatch):
    """Disabling the cache prevents an older snapshot from being reused later."""
    _, _, process = cached_build
    build.build()
    monkeypatch.setenv("REFLEX_FRONTEND_BUILD_CACHE", "false")
    build.build()
    monkeypatch.setenv("REFLEX_FRONTEND_BUILD_CACHE", "true")
    build.build()
    assert process.call_count == 3


def test_environment_change_rebuilds(cached_build, monkeypatch):
    """Build hooks may observe arbitrary environment values."""
    _, _, process = cached_build
    build.build()
    monkeypatch.setenv("CUSTOM_BUILD_VALUE", "new")
    build.build()
    assert process.call_count == 2


def test_failed_build_is_retried(cached_build):
    """A failed Vite run must never populate the cache."""
    _, _, process = cached_build
    compile_frontend = process.side_effect
    process.side_effect = None
    process.return_value.returncode = 1
    with pytest.raises(SystemExit):
        build.build()
    process.side_effect = compile_frontend
    build.build()
    assert process.call_count == 2


def test_failed_post_build_is_retried(cached_build):
    """Post-build failure must not publish partially processed output."""
    _, config, process = cached_build

    class FailingPlugin(Plugin):
        def post_build(self, **context):
            msg = "plugin failed"
            raise RuntimeError(msg)

    config.plugins = [FailingPlugin()]
    with pytest.raises(RuntimeError, match="plugin failed"):
        build.build()
    config.plugins = []
    build.build()
    assert process.call_count == 2


@pytest.mark.skipif(os.name == "nt", reason="Cache uses POSIX change timestamps")
def test_generated_dependency_caches_do_not_invalidate(cached_build):
    """Vite's transient dependency caches are excluded from tracked inputs."""
    web, _, process = cached_build
    build.build()
    for name in (".vite", ".vite-temp"):
        (web / "node_modules" / name).mkdir()
        (web / "node_modules" / name / "temporary.js").write_text("temporary")
    build.build()
    assert process.call_count == 1


@pytest.mark.parametrize(
    "mutation", ["missing", "content", "extra", "metadata", "mode"]
)
def test_damaged_snapshot_rebuilds(cached_build, mutation: str):
    """A missing, modified, or malformed snapshot cannot bypass a fresh build."""
    web, _, process = cached_build
    build.build()
    current = web / "reflex.build-cache/current"
    if os.name == "nt":
        assert not current.exists()
        return
    bundle = current / "build/client/bundle.js"
    if mutation == "missing":
        bundle.unlink()
    elif mutation == "content":
        bundle.write_text("tampered")
    elif mutation == "extra":
        (current / "build/client/extra.js").write_text("unexpected")
    elif mutation == "metadata":
        (current / "metadata.json").write_text("[]")
    else:
        bundle.chmod(0o600)
    build.build()
    assert process.call_count == 2
    assert (web / "build/client/bundle.js").read_text() == "compiled"


def test_input_changed_during_build_is_not_cached(cached_build):
    """An input change during Vite cannot label old output with a reusable key."""
    web, _, process = cached_build
    compile_frontend = process.side_effect

    def changing_build(*args, **kwargs):
        result = compile_frontend(*args, **kwargs)
        (web / "app/page.js").write_text("changed during build")
        return result

    process.side_effect = changing_build
    build.build()
    assert not (web / "reflex.build-cache/current").exists()
    process.side_effect = compile_frontend
    build.build()
    assert process.call_count == 2
    assert (web / "build/client/index.html").read_text() == "changed during build"


@pytest.mark.skipif(os.name == "nt", reason="Requires symlinks")
@pytest.mark.parametrize("directory", ["app", "node_modules"])
def test_external_symlink_bypasses_cache(cached_build, tmp_path: Path, directory: str):
    """Untracked external source or dependency targets force normal builds."""
    web, _, process = cached_build
    external = tmp_path / "external.js"
    external.write_text("external")
    (web / directory / "external.js").symlink_to(external)
    build.build()
    build.build()
    assert process.call_count == 2


@pytest.mark.skipif(os.name == "nt", reason="Requires symlinks")
def test_external_redirect_between_internal_sources_rebuilds(cached_build, tmp_path):
    """Resolve intermediate links again before reusing their internal target's output."""
    web, _, process = cached_build
    first = web / "app/first.js"
    second = web / "app/second.js"
    first.write_text("first")
    second.write_text("second")
    redirect = tmp_path / "redirect.js"
    redirect.symlink_to(first)
    source = web / "app/page.js"
    source.unlink()
    source.symlink_to(redirect)

    build.build()
    build.build()
    assert process.call_count == 1
    assert (web / "build/client/index.html").read_text() == "first"

    redirect.unlink()
    redirect.symlink_to(second)
    build.build()
    assert process.call_count == 2
    assert (web / "build/client/index.html").read_text() == "second"


@pytest.mark.skipif(os.name == "nt", reason="Requires symlinks")
def test_internal_dependency_symlink_is_tracked(cached_build):
    """Normal package executable links remain cacheable and their targets are tracked."""
    web, _, process = cached_build
    binaries = web / "node_modules/.bin"
    binaries.mkdir()
    (binaries / "package").symlink_to("../package/index.js")
    build.build()
    build.build()
    assert process.call_count == 1
    (web / "node_modules/package/index.js").write_text("new")
    build.build()
    assert process.call_count == 2


@pytest.mark.parametrize("mutation", ["add", "remove"])
def test_source_file_membership_invalidates(cached_build, mutation: str):
    """Added and removed source files both change the input fingerprint."""
    web, _, process = cached_build
    extra = web / "app/extra.js"
    if mutation == "remove":
        extra.write_text("extra")
    build.build()
    if mutation == "add":
        extra.write_text("extra")
    else:
        extra.unlink()
    build.build()
    assert process.call_count == 2


@pytest.mark.skipif(os.name == "nt", reason="Cache uses POSIX change timestamps")
def test_deleted_processed_output_restores_snapshot(cached_build):
    """The pristine snapshot can restore output deleted after a successful build."""
    web, _, process = cached_build
    build.build()
    build.path_ops.rm(web / "build")
    build.build()
    assert process.call_count == 1
    assert (web / "build/client/index.html").read_text() == "original"


@pytest.mark.skipif(os.name == "nt", reason="Requires symlinks")
def test_link_into_ignored_dependency_cache_bypasses(cached_build):
    """A link cannot turn an excluded transient file into an untracked input."""
    web, _, process = cached_build
    generated = web / "node_modules/.cache"
    generated.mkdir()
    (generated / "style.css").write_text("old")
    (web / "public/linked.css").symlink_to("../node_modules/.cache/style.css")
    build.build()
    (generated / "style.css").write_text("new")
    build.build()
    assert process.call_count == 2
    assert not (web / "reflex.build-cache/current").exists()


@pytest.mark.skipif(os.name == "nt", reason="Requires POSIX symlinks and modes")
@pytest.mark.parametrize("entry", ["directory", "current"])
def test_cache_symlink_never_changes_external_target(
    cached_build, tmp_path, monkeypatch, entry
):
    """Discard cache links without chmod or removal of their external targets."""
    web, _, _ = cached_build
    external = tmp_path / "external-cache"
    external.mkdir(mode=0o700)
    (external / "keep").write_text("keep")
    previous_mode = external.stat().st_mode
    directory = web / "reflex.build-cache"
    if entry == "directory":
        directory.symlink_to(external, target_is_directory=True)
        monkeypatch.setenv("REFLEX_FRONTEND_BUILD_CACHE", "false")
    else:
        directory.mkdir()
        (directory / "current").symlink_to(external, target_is_directory=True)
    build.build()
    assert external.stat().st_mode == previous_mode
    assert (external / "keep").read_text() == "keep"
