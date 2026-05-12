"""Unit tests for frontend build helpers."""

from pathlib import Path

from reflex.utils.build import _duplicate_index_html_to_parent_directory


def test_duplicate_index_html_to_parent_directory_copies_sidecars(tmp_path: Path):
    """Duplicate index.html sidecars alongside copied route HTML files."""
    route_dir = tmp_path / "docs"
    route_dir.mkdir()
    (route_dir / "index.html").write_text("<html>docs</html>")
    (route_dir / "index.html.gz").write_bytes(b"gzip")
    (route_dir / "index.html.br").write_bytes(b"brotli")

    _duplicate_index_html_to_parent_directory(tmp_path, (".gz", ".br"))

    assert (tmp_path / "docs.html").read_text() == "<html>docs</html>"
    assert (tmp_path / "docs.html.gz").read_bytes() == b"gzip"
    assert (tmp_path / "docs.html.br").read_bytes() == b"brotli"
