"""Tests for the file selection of the reflex package's hatch build config."""

from pathlib import Path

import pytest
from hatchling.builders.plugin.interface import BuilderInterface
from hatchling.builders.sdist import SdistBuilder
from hatchling.builders.wheel import WheelBuilder

REPO_ROOT = Path(__file__).parents[2]

# Everything the reflex distributions are meant to ship: the package itself,
# its generated stubs, and the build hook that regenerates them when the wheel
# is built from the sdist.
SELECTED = [
    "reflex/app.py",
    "reflex/__init__.pyi",
    "reflex/components/__init__.pyi",
    "scripts/hatch_build.py",
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


@pytest.fixture(params=[SdistBuilder, WheelBuilder], ids=["sdist", "wheel"])
def builder(request) -> BuilderInterface:
    return request.param(str(REPO_ROOT))


@pytest.mark.parametrize("relative_path", SELECTED)
def test_build_selects_reflex_files(builder: BuilderInterface, relative_path: str):
    assert builder.config.include_path(relative_path)


@pytest.mark.parametrize("relative_path", NOT_SELECTED)
def test_build_skips_files_outside_reflex(
    builder: BuilderInterface, relative_path: str
):
    assert not builder.config.include_path(relative_path)


def test_build_walks_only_the_reflex_tree(builder: BuilderInterface):
    selected = {
        Path(included.relative_path).as_posix()
        for included in builder.recurse_included_files()
    }
    outside = sorted(
        path
        for path in selected
        if not path.startswith("reflex/") and path != "scripts/hatch_build.py"
    )
    assert outside == []
