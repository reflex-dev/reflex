"""Tests for the file selection of the workspace's hatch build configs."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
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
    "packages/reflex-base/src/reflex_base/.templates/web/components/reflex/color_mode.js",
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


def build_hook(root: Path, directory: Path):
    """Load the stub-generating build hook and instantiate it against a root.

    Args:
        root: The project root the hook runs against.
        directory: The build output directory.

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
        "wheel",
    )
    return module, hook


@pytest.mark.parametrize(
    ("build_version", "regenerates"), [("editable", False), ("standard", True)]
)
def test_build_hook_skips_editable_installs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    build_version: str,
    regenerates: bool,
):
    """An editable install must leave the working tree's stubs untouched.

    `uv pip install -e .` builds an editable wheel against the checkout, so
    regenerating there rewrites the developer's stubs from whatever the
    installing environment resolved to.
    """
    (tmp_path / "scripts").mkdir()
    stub = tmp_path / "reflex" / "__init__.pyi"
    stub.parent.mkdir()
    stub.write_text("# generated")

    runs = []
    module, hook = build_hook(tmp_path, tmp_path / "dist")
    monkeypatch.setattr(
        module, "subprocess", SimpleNamespace(run=lambda *a, **kw: runs.append(a))
    )

    hook.initialize(build_version, {})

    assert bool(runs) is regenerates
    assert stub.exists() is not regenerates
