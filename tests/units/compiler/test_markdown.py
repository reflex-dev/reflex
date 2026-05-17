"""Tests for the Rust-accelerated Markdown wrapper."""

from __future__ import annotations

import pytest

from reflex.compiler import markdown


def test_basic_rendering() -> None:
    out = markdown.markdown_to_html("# Hello\n\nworld")
    assert "<h1>Hello</h1>" in out
    assert "<p>world</p>" in out


def test_tables_supported() -> None:
    """Rust wheel ships with tables enabled by default. mistletoe also does."""
    out = markdown.markdown_to_html("| a | b |\n|---|---|\n| 1 | 2 |")
    assert "<table>" in out
    assert "<td>1</td>" in out


def test_strikethrough_supported() -> None:
    out = markdown.markdown_to_html("a ~~b~~ c")
    assert "<del>b</del>" in out or "<s>b</s>" in out


def test_rust_backend_when_available() -> None:
    """When the wheel is installed, the auto backend should choose Rust."""
    try:
        from reflex_markdown_rust import markdown_to_html as _rust  # noqa: F401
    except ImportError:
        pytest.skip("reflex_markdown_rust wheel not installed")
    # Trigger the lazy resolution.
    markdown.markdown_to_html("")
    assert markdown.is_rust()


def test_explicit_python_backend_when_mistletoe_present(monkeypatch) -> None:
    try:
        import mistletoe  # noqa: F401
    except ImportError:
        pytest.skip("mistletoe not installed")
    monkeypatch.setenv("REFLEX_MARKDOWN", "python")
    # Reset the cached implementation.
    monkeypatch.setattr(markdown, "_impl", None)
    out = markdown.markdown_to_html("# X")
    assert "<h1>X</h1>" in out
    assert not markdown.is_rust()
