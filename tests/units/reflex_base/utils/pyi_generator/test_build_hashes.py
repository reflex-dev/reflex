"""Regression test: building a package must not rewrite pyi_hashes.json.

The build hooks (``scripts/hatch_build.py`` for the main ``reflex`` package and
``hatch-reflex-pyi`` for the component subpackages) invoke the pyi_generator
module entrypoint to emit ``.pyi`` stubs into the wheel. They must NOT touch
``pyi_hashes.json``: that registry is owned solely by the
``scripts/make_pyi.py`` pre-commit step.

Otherwise a single-package build replaces the whole registry with just that
package's entries, wiping every unrelated entry. That is exactly what forced
the re-checkout workaround in ``.github/workflows/pre-commit.yml`` and what
corrupts ``pyi_hashes.json`` on a bare ``uv build packages/<pkg>``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

_WIDGET_SOURCE = textwrap.dedent(
    '''\
    """A fake component module."""

    from reflex_base.components.component import Component
    from reflex_base.vars.base import Var


    class Widget(Component):
        """A widget."""

        value: Var[str]
    '''
)


def test_build_entrypoint_does_not_touch_pyi_hashes(tmp_path: Path):
    """The build entrypoint emits .pyi stubs without rewriting pyi_hashes.json.

    Args:
        tmp_path: A pytest-provided temporary directory (outside the repo).
    """
    root = tmp_path / "fake-pkg"
    pkg = root / "src" / "fake_pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "widget.py").write_text(_WIDGET_SOURCE)

    # A pre-existing registry with entries unrelated to fake_pkg.
    hashes_file = root / "pyi_hashes.json"
    original_text = (
        json.dumps(
            {"another/package/bar.pyi": "1111", "some/other/foo.pyi": "0000"},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    hashes_file.write_text(original_text)

    # Mirror how the build hooks invoke the generator: from the src/ dir,
    # targeting the package by name (see hatch_reflex_pyi.plugin).
    subprocess.run(
        [sys.executable, "-m", "reflex_base.utils.pyi_generator", "fake_pkg"],
        cwd=root / "src",
        check=True,
    )

    # The stub must have been generated for the wheel...
    assert (pkg / "widget.pyi").exists()
    # ...the empty __init__.py yields no stub and must not crash the scan
    # (inspect.getsource raises OSError for an empty file on Python < 3.13)...
    assert not (pkg / "__init__.pyi").exists()
    # ...but the hash registry must be byte-for-byte untouched.
    assert hashes_file.read_text() == original_text
