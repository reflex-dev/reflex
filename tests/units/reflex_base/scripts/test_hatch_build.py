"""Tests for the reflex-base build hook that packs the frontend npm tarball."""

import gzip
import importlib.util
import io
import json
import os
import tarfile
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parents[4] / "packages/reflex-base/scripts/hatch_build.py"

spec = importlib.util.spec_from_file_location("reflex_base_hatch_build", HOOK_PATH)
assert spec is not None
assert spec.loader is not None
hatch_build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hatch_build)


@pytest.mark.parametrize(
    ("pep440", "semver"),
    [
        ("0.9.10", "0.9.10"),
        ("0.9.10a1", "0.9.10-a.1"),
        ("0.9.10b2", "0.9.10-b.2"),
        ("0.9.10rc1", "0.9.10-rc.1"),
        ("0.9.10.dev1", "0.9.10-dev.1"),
        ("0.9.10.post1", "0.9.10-post.1"),
        ("0.9.10a1.dev2", "0.9.10-a.1.dev.2"),
        ("0.0.0dev0", "0.0.0-dev.0"),
        ("1.0", "1.0.0"),
        ("0.9.8.post46.dev0+abc_123", "0.9.8-post.46.dev.0+abc-123"),
    ],
)
def test_pep440_to_npm_semver(pep440: str, semver: str):
    """PEP 440 versions map to npm-compatible semver strings."""
    assert hatch_build.pep440_to_npm_semver(pep440) == semver


def test_npm_tarball_basename():
    """The basename follows npm pack's scoped-package convention."""
    assert (
        hatch_build.npm_tarball_basename("@reflex-dev/reflex-base", "1.2.3")
        == "reflex-dev-reflex-base-1.2.3.tgz"
    )
    assert hatch_build.npm_tarball_basename("plain", "0.1.0") == "plain-0.1.0.tgz"


def _make_source(tmp_path: Path) -> Path:
    source = tmp_path / "frontend"
    (source / "helpers").mkdir(parents=True)
    (source / "tests").mkdir()
    (source / "node_modules" / "react").mkdir(parents=True)
    (source / "package.json").write_text(
        json.dumps({
            "name": "@reflex-dev/reflex-base",
            "version": "0.0.0",
            "files": ["state.js", "helpers/"],
            "dependencies": {"react": "1.0.0"},
        })
    )
    (source / "state.js").write_text("export const x = 1;\n")
    (source / "helpers" / "debounce.js").write_text("export default 1;\n")
    (source / "README.md").write_text("readme\n")
    (source / "tests" / "state.test.js").write_text("excluded\n")
    (source / "node_modules" / "react" / "index.js").write_text("excluded\n")
    (source / ".hidden").write_text("excluded\n")
    return source


def test_tarball_structure_and_stamping(tmp_path: Path):
    """The tarball is npm-shaped, deterministic in metadata, version-stamped."""
    source = _make_source(tmp_path)
    out = tmp_path / "out.tgz"
    hatch_build.build_frontend_tarball(source, "1.2.3", out)

    raw = gzip.decompress(out.read_bytes())
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        manifest_file = tar.extractfile("package/package.json")
        assert manifest_file is not None
        manifest = json.load(manifest_file)

    assert names[0] == "package/package.json"
    assert names[1:] == sorted(names[1:])
    assert set(names) == {
        "package/package.json",
        "package/README.md",
        "package/state.js",
        "package/helpers/debounce.js",
    }
    assert manifest["version"] == "1.2.3"
    for member in members:
        assert (member.uid, member.gid) == (0, 0)
        assert (member.uname, member.gname) == ("", "")
        assert member.mtime == 0
        assert member.mode in (0o644, 0o755)


def test_tarball_bytes_are_deterministic(tmp_path: Path):
    """Rebuilds produce identical bytes regardless of mtimes or output name."""
    source = _make_source(tmp_path)
    first = tmp_path / "a.tgz"
    second = tmp_path / "b-different-name.tgz"
    hatch_build.build_frontend_tarball(source, "1.2.3", first)
    os.utime(source / "state.js")
    hatch_build.build_frontend_tarball(source, "1.2.3", second)
    assert first.read_bytes() == second.read_bytes()


def test_tarball_rejects_negation_patterns(tmp_path: Path):
    """Unsupported npm `files` negation patterns fail the build loudly."""
    source = _make_source(tmp_path)
    manifest = json.loads((source / "package.json").read_text())
    manifest["files"] = ["state.js", "!state.test.js"]
    (source / "package.json").write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="negation"):
        hatch_build.build_frontend_tarball(source, "1.2.3", tmp_path / "out.tgz")


def test_real_manifest_packs_without_tests(tmp_path: Path):
    """The in-repo frontend source packs cleanly and excludes its tests dir."""
    source = HOOK_PATH.parents[1] / "src/reflex_base/frontend"
    out = tmp_path / "real.tgz"
    hatch_build.build_frontend_tarball(source, "9.9.9", out)
    with tarfile.open(out) as tar:
        names = tar.getnames()
    assert "package/state.js" in names
    assert "package/runtime.js" in names
    assert not any("/tests/" in name or "node_modules" in name for name in names)
