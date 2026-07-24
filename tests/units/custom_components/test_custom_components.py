"""Unit tests for reflex/custom_components/custom_components.py."""

from __future__ import annotations

from pathlib import Path

from reflex.custom_components import custom_components


def test_make_pyi_files_walks_without_path_walk(monkeypatch, tmp_path: Path):
    """``_make_pyi_files`` scans component dirs without relying on ``Path.walk``.

    ``pathlib.Path.walk`` only exists on Python 3.12+, but Reflex supports 3.10
    and 3.11 too, so the build must not depend on it. ``Path.walk`` is removed
    here to reproduce the 3.10/3.11 environment on any interpreter; the function
    must still recurse (skipping ``__pycache__``) instead of raising
    ``AttributeError``.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        tmp_path: A temporary directory used as the project root.
    """
    package = tmp_path / "my_component"
    nested = package / "sub"
    nested.mkdir(parents=True)
    (package / "__pycache__").mkdir()
    (tmp_path / ".hidden").mkdir()

    scanned: list[str] = []

    class _RecordingGenerator:
        def scan_all(self, targets, *_args, **_kwargs):
            scanned.extend(str(target) for target in targets)

    monkeypatch.setattr(
        "reflex_base.utils.pyi_generator.PyiGenerator", _RecordingGenerator
    )
    monkeypatch.delattr(Path, "walk", raising=False)
    monkeypatch.chdir(tmp_path)

    custom_components._make_pyi_files()

    scanned_names = {Path(target).name for target in scanned}
    assert "my_component" in scanned_names
    assert "sub" in scanned_names
    assert "__pycache__" not in scanned_names
    assert ".hidden" not in scanned_names
