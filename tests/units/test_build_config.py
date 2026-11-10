"""Tests for the file selection of the workspace's hatch build configs."""

import importlib.util
import json
import shutil
import tarfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import tomlkit
from hatchling.builders.plugin.interface import BuilderInterface
from hatchling.builders.sdist import SdistBuilder
from hatchling.builders.wheel import WheelBuilder
from hatchling.metadata.core import ProjectMetadata

REPO_ROOT = Path(__file__).parents[2]

# The build hook that regenerates the stubs. The sdist ships it so that the
# wheel can be built from the sdist; the wheel itself has no use for it.
BUILD_HOOK = "scripts/hatch_build.py"

# Everything the reflex distributions are meant to ship: the package and its
# generated stubs.
SELECTED = [
    "reflex/app.py",
    "reflex/__init__.pyi",
    "reflex/components/__init__.pyi",
]

# Sibling workspace packages bundle their own stubs and templates, so none of
# their files belong in the reflex distributions. Neither do the pyi_generator
# golden files, which are only test fixtures.
NOT_SELECTED = [
    "packages/reflex-components-core/src/reflex_components_core/el/element.py",
    "packages/reflex-components-core/src/reflex_components_core/el/element.pyi",
    "packages/reflex-components-lucide/src/reflex_components_lucide/icon.pyi",
    "packages/reflex-frontend/src/utils/state.js",
    "tests/units/reflex_base/utils/pyi_generator/golden/var_types.pyi",
    "docs/app/docs.py",
]

BUILDERS = pytest.mark.parametrize(
    "builder_class", [SdistBuilder, WheelBuilder], ids=["sdist", "wheel"]
)


@pytest.fixture
def builder(builder_class: type[BuilderInterface]) -> BuilderInterface:
    return builder_class(str(REPO_ROOT))


def stub_packages() -> list[Path]:
    """Find the workspace packages that generate stubs at build time.

    Discovery keys off the build hook rather than off the artifact patterns, so
    that dropping a package's patterns fails its assertions below instead of
    quietly dropping it from the parametrization.

    Returns:
        The directory of every package that runs the stub generator.
    """
    packages = []
    for path in sorted((REPO_ROOT / "packages").glob("*/pyproject.toml")):
        build_config = SdistBuilder(str(path.parent)).config.build_config
        if "reflex-pyi" in build_config.get("hooks", {}):
            packages.append(path.parent)
    return packages


@BUILDERS
@pytest.mark.parametrize("relative_path", SELECTED)
def test_build_selects_reflex_files(builder: BuilderInterface, relative_path: str):
    assert builder.config.include_path(relative_path)


@BUILDERS
@pytest.mark.parametrize("relative_path", NOT_SELECTED)
def test_build_skips_files_outside_reflex(
    builder: BuilderInterface, relative_path: str
):
    assert not builder.config.include_path(relative_path)


@BUILDERS
def test_build_walks_only_the_reflex_tree(
    builder: BuilderInterface, builder_class: type[BuilderInterface]
):
    allowed = {BUILD_HOOK} if builder_class is SdistBuilder else set()
    selected = {
        Path(included.relative_path).as_posix()
        for included in builder.recurse_included_files()
    }
    outside = sorted(
        path
        for path in selected
        if not path.startswith("reflex/") and path not in allowed
    )
    assert outside == []


def test_sdist_ships_the_build_hook():
    assert SdistBuilder(str(REPO_ROOT)).config.include_path(BUILD_HOOK)


def test_wheel_omits_the_build_hook():
    assert not WheelBuilder(str(REPO_ROOT)).config.include_path(BUILD_HOOK)


@BUILDERS
@pytest.mark.parametrize("package", stub_packages(), ids=lambda path: path.name)
def test_package_ships_only_its_own_stubs(
    builder_class: type[BuilderInterface], package: Path
):
    config = builder_class(str(package)).config
    assert config.include_path("src/module/component.pyi")
    # Anything a package keeps beside `src` — fixtures, docs, a vendored
    # checkout — is not part of what it distributes.
    assert not config.include_path("tests/golden.pyi")


def build_hook(root: Path, directory: Path, target: str = "wheel"):
    """Load the stub-generating build hook and instantiate it against a root.

    Args:
        root: The project root the hook runs against.
        directory: The build output directory.
        target: The distribution target.

    Returns:
        The hook's module and an instance bound to `root`.
    """
    directory.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("hatch_build", REPO_ROOT / BUILD_HOOK)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hook = module.CustomBuilder(
        str(root),
        {},
        WheelBuilder(str(root)).config,
        ProjectMetadata(
            str(root), None, {"project": {"name": "reflex", "version": "0.0.0"}}
        ),
        str(directory),
        target,
    )
    return module, hook


@pytest.mark.parametrize("marker_exists", [False, True])
@pytest.mark.parametrize("workspace", [False, True])
def test_sdist_omits_workspace_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    marker_exists: bool,
    workspace: bool,
):
    """Source archives must build without the checkout's workspace members.

    Args:
        tmp_path: The temporary project directory.
        monkeypatch: The pytest monkeypatch fixture.
        marker_exists: Whether stub generation already ran.
        workspace: Whether the source contains workspace settings.
    """
    config = tomlkit.parse((REPO_ROOT / "pyproject.toml").read_text())
    config["project"]["version"] = "0.0.0"
    config["project"]["dynamic"].remove("version")
    del config["tool"]["hatch"]["version"]
    if not workspace:
        del config["tool"]["uv"]["sources"]
        del config["tool"]["uv"]["workspace"]
    pyproject = tmp_path / "pyproject.toml"
    original = tomlkit.dumps(config)
    pyproject.write_text(original)
    (tmp_path / "README.md").write_text("Reflex")
    (tmp_path / "reflex").mkdir()
    (tmp_path / "reflex" / "__init__.pyi").write_text("# generated")

    directory = tmp_path / "dist"
    module, hook = build_hook(tmp_path, directory, "sdist")
    monkeypatch.setattr(
        module, "subprocess", SimpleNamespace(run=lambda *a, **kw: None)
    )
    if marker_exists:
        hook.marker().touch()
    builder = SdistBuilder(str(tmp_path))
    monkeypatch.setattr(builder, "get_build_hooks", lambda _: {"custom": hook})

    artifact = next(builder.build(directory=str(directory)))

    with tarfile.open(artifact) as archive:
        names = archive.getnames()
        assert names.count("reflex-0.0.0/pyproject.toml") == 1
        assert "reflex-0.0.0/reflex/__init__.pyi" in names
        archived = archive.extractfile("reflex-0.0.0/pyproject.toml")
        assert archived is not None
        packaged = tomlkit.parse(archived.read().decode())

    assert pyproject.read_text() == original
    assert packaged["project"] == config["project"]
    assert packaged["build-system"] == config["build-system"]
    assert packaged["tool"]["hatch"] == config["tool"]["hatch"]
    assert "sources" not in packaged["tool"]["uv"]
    assert "workspace" not in packaged["tool"]["uv"]
    assert (
        packaged["tool"]["uv"]["required-version"]
        == config["tool"]["uv"]["required-version"]
    )


EXPECTED_STUBS = ["reflex/__init__.pyi", "reflex/experimental/memo.pyi"]


@pytest.mark.parametrize(
    ("build_version", "present", "regenerates"),
    [
        # An editable install builds against the checkout, so it must not
        # rewrite stubs that are already there from whatever the installing
        # environment resolved to.
        ("editable", EXPECTED_STUBS, False),
        # A fresh clone has no stubs — they are gitignored — so the editable
        # install that `uv sync` performs is what creates them.
        ("editable", [], True),
        # The generator logs and skips a module it cannot import, so a failed
        # run leaves a partial set that must not suppress the next one.
        ("editable", EXPECTED_STUBS[:1], True),
        ("standard", EXPECTED_STUBS, True),
    ],
    ids=["complete", "fresh-checkout", "partial", "standard"],
)
def test_build_hook_regenerates_stubs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    build_version: str,
    present: list[str],
    regenerates: bool,
):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "pyi_hashes.json").write_text(
        json.dumps(dict.fromkeys([*EXPECTED_STUBS, "packages/other/mod.pyi"], ""))
    )
    written = [tmp_path / name for name in present]
    for stub in written:
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text("# generated")

    runs = []
    module, hook = build_hook(tmp_path, tmp_path / "dist")
    monkeypatch.setattr(
        module, "subprocess", SimpleNamespace(run=lambda *a, **kw: runs.append(a))
    )

    hook.initialize(build_version, {})

    assert bool(runs) is regenerates
    # The generator is stubbed out, so a run that proceeded leaves the stubs it
    # would have rewritten unlinked; one that was skipped leaves them as found.
    if regenerates:
        assert not any(stub.exists() for stub in written)
    else:
        assert all(stub.exists() for stub in written)


@pytest.mark.parametrize(
    "manifest",
    ["", '{"reflex/__init__.pyi"', "[]", "null", "5"],
    ids=["empty", "truncated", "list", "null", "number"],
)
def test_build_hook_regenerates_on_an_unreadable_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, manifest: str
):
    """A manifest left half-written by an interrupted run must not fail the build."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "pyi_hashes.json").write_text(manifest)
    for name in EXPECTED_STUBS:
        stub = tmp_path / name
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text("# generated")

    runs = []
    module, hook = build_hook(tmp_path, tmp_path / "dist")
    monkeypatch.setattr(
        module, "subprocess", SimpleNamespace(run=lambda *a, **kw: runs.append(a))
    )

    hook.initialize("editable", {})

    assert runs


def test_build_hook_ignores_marker_for_incomplete_editable_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A marker left by an earlier build must not stand in for a missing stub."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "pyi_hashes.json").write_text(
        json.dumps(dict.fromkeys(EXPECTED_STUBS, ""))
    )
    stub = tmp_path / EXPECTED_STUBS[0]
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text("# generated")

    runs = []
    module, hook = build_hook(tmp_path, tmp_path / "dist")
    monkeypatch.setattr(
        module, "subprocess", SimpleNamespace(run=lambda *a, **kw: runs.append(a))
    )
    hook.marker().touch()

    hook.initialize("editable", {})

    assert runs


REFLEX_BASE = REPO_ROOT / "packages" / "reflex-base"
WEB_TEMPLATE = "reflex_base/.templates/web"


@pytest.fixture
def reflex_base_checkout(tmp_path: Path) -> Path:
    """Lay out reflex-base beside a frontend package, as in the repository.

    The project is the real one — its build config and its hook — with a fixed
    version, since a temporary directory has no tags to derive one from.

    Args:
        tmp_path: The temporary directory.

    Returns:
        The reflex-base project root.
    """
    root = tmp_path / "packages" / "reflex-base"
    (root / "src" / "reflex_base").mkdir(parents=True)
    (root / "src" / "reflex_base" / "__init__.py").touch()
    (root / "README.md").write_text("reflex-base")
    shutil.copy(REFLEX_BASE / "hatch_build.py", root)
    config = tomlkit.parse((REFLEX_BASE / "pyproject.toml").read_text())
    config["project"]["version"] = "0.0.0"
    config["project"]["dynamic"].remove("version")
    del config["tool"]["hatch"]["version"]
    (root / "pyproject.toml").write_text(tomlkit.dumps(config))

    frontend = tmp_path / "packages" / "reflex-frontend"
    (frontend / "src" / "utils").mkdir(parents=True)
    (frontend / "src" / "utils" / "state.js").write_text("// state")
    (frontend / "src" / ".gitignore").write_text("/node_modules")
    (frontend / "tests").mkdir()
    (frontend / "tests" / "state.test.js").write_text("// test")
    (frontend / "package.json").write_text("{}")
    return root


def build_wheel(root: Path, directory: Path, version: str = "standard") -> set[str]:
    """Build a wheel and list what it holds.

    Args:
        root: The project root.
        directory: The build output directory.
        version: The kind of wheel: `standard` or `editable`.

    Returns:
        The path of every file in the wheel.
    """
    builder = WheelBuilder(str(root))
    artifact = next(builder.build(directory=str(directory), versions=[version]))
    with zipfile.ZipFile(artifact) as archive:
        return set(archive.namelist())


def test_reflex_base_wheel_embeds_the_frontend(
    reflex_base_checkout: Path, tmp_path: Path
):
    """A wheel built in the repository carries the frontend's `src`, and only that."""
    names = build_wheel(reflex_base_checkout, tmp_path / "dist")
    assert f"{WEB_TEMPLATE}/utils/state.js" in names
    assert f"{WEB_TEMPLATE}/.gitignore" in names
    assert not any("test" in name or name.endswith("package.json") for name in names)
    assert "hatch_build.py" not in names


def test_reflex_base_wheel_builds_from_its_sdist(
    reflex_base_checkout: Path, tmp_path: Path
):
    """The sdist carries the frontend, so its wheel needs no repository."""
    builder = SdistBuilder(str(reflex_base_checkout))
    artifact = next(builder.build(directory=str(tmp_path / "dist")))
    with tarfile.open(artifact) as archive:
        names = set(archive.getnames())
        archive.extractall(tmp_path / "unpacked", filter="data")
    assert f"reflex_base-0.0.0/src/{WEB_TEMPLATE}/utils/state.js" in names
    assert "reflex_base-0.0.0/hatch_build.py" in names

    unpacked = tmp_path / "unpacked" / "reflex_base-0.0.0"
    assert build_wheel(unpacked, tmp_path / "from-sdist") == build_wheel(
        reflex_base_checkout, tmp_path / "from-checkout"
    )


def test_reflex_base_editable_install_embeds_nothing(reflex_base_checkout: Path):
    """An editable install reads the frontend package in place."""
    spec = importlib.util.spec_from_file_location(
        "reflex_base_hatch_build", reflex_base_checkout / "hatch_build.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    builder = WheelBuilder(str(reflex_base_checkout))
    hook = module.FrontendBuildHook(
        str(reflex_base_checkout), {}, builder.config, builder.metadata, "", "wheel"
    )

    editable = {"force_include": {}}
    hook.initialize("editable", editable)
    assert editable["force_include"] == {}

    standard = {"force_include": {}}
    hook.initialize("standard", standard)
    assert list(standard["force_include"].values()) == [WEB_TEMPLATE]


def test_reflex_base_refuses_to_build_without_a_frontend(
    reflex_base_checkout: Path, tmp_path: Path
):
    """A wheel with no web template could not initialize an app."""
    shutil.rmtree(reflex_base_checkout.parent / "reflex-frontend")
    with pytest.raises(FileNotFoundError, match="No frontend to embed"):
        build_wheel(reflex_base_checkout, tmp_path / "dist")


def test_frontend_package_is_where_the_build_hook_looks():
    """The hook and the checkout fallback both assume this location."""
    frontend = REFLEX_BASE.parent / "reflex-frontend"
    assert (frontend / "src" / "utils" / "state.js").is_file()
    assert (frontend / "package.json").is_file()
