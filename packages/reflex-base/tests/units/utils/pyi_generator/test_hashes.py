"""Regression test: pyi_hashes.json must hash the final post-processed content.

``PyiGenerator.scan_all`` writes the raw ``ast.unparse`` output to disk and then
runs ``ruff format`` / ``ruff check --fix`` over the generated stubs. The hash
registry must be computed from the post-processed file contents: hashing the
intermediate pre-ruff output flags a change whenever the generator's raw output
shifts (quoting, line wrapping, ...), even when the ``.pyi`` file the user sees
is byte-for-byte identical.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from hashlib import md5
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

_SCAN_SCRIPT = (
    "from reflex_base.utils.pyi_generator import PyiGenerator; "
    "PyiGenerator().scan_all(['fake_pkg'], None, use_json=True)"
)


def test_pyi_hashes_reflect_post_ruff_content(tmp_path: Path):
    """The recorded hash matches the .pyi content after ruff post-processing.

    Args:
        tmp_path: A pytest-provided temporary directory (outside the repo).
    """
    root = tmp_path / "fake-root"
    pkg = root / "fake_pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "widget.py").write_text(_WIDGET_SOURCE)

    # An empty registry that scan_all discovers by walking up from the stub.
    hashes_file = root / "pyi_hashes.json"
    hashes_file.write_text("{}\n")

    # Run from root so _path_to_module_name produces a valid import name.
    subprocess.run(
        [sys.executable, "-c", _SCAN_SCRIPT],
        cwd=root,
        check=True,
    )

    pyi_path = pkg / "widget.pyi"
    assert pyi_path.exists()

    hashes = json.loads(hashes_file.read_text())
    assert list(hashes) == ["fake_pkg/widget.pyi"]
    assert hashes["fake_pkg/widget.pyi"] == (
        md5(pyi_path.read_text().encode()).hexdigest()
    )
