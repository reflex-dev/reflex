"""Unit tests for reflex/custom_components/custom_components.py."""

from __future__ import annotations

from pathlib import Path

from reflex.custom_components import custom_components


def test_make_pyi_files_delegates_recursive_scan_without_path_walk(
    monkeypatch, tmp_path: Path
):
    """``_make_pyi_files`` delegates recursive scanning without ``Path.walk``.

    ``pathlib.Path.walk`` only exists on Python 3.12+, but Reflex supports 3.10
    and 3.11 too, so the build must not depend on it. ``Path.walk`` is removed
    here to reproduce the 3.10/3.11 environment on any interpreter.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        tmp_path: A temporary directory used as the project root.
    """
    package = tmp_path / "my_component"
    nested = package / "sub"
    nested.mkdir(parents=True)
    (package / "__pycache__").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / ".hidden").mkdir()

    scans: list[list[Path]] = []

    class _RecordingGenerator:
        def scan_all(self, targets, *_args, **_kwargs):
            scans.append([Path(target) for target in targets])

    monkeypatch.setattr(
        "reflex_base.utils.pyi_generator.PyiGenerator", _RecordingGenerator
    )
    monkeypatch.delattr(Path, "walk", raising=False)
    monkeypatch.chdir(tmp_path)

    custom_components._make_pyi_files()

    assert scans == [[package]]
