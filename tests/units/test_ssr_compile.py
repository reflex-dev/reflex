"""Unit tests for SSR route-param extraction."""

from __future__ import annotations

from reflex.route import extract_route_params


def test_simple_dynamic_route():
    """Single dynamic segment is extracted correctly."""
    result = extract_route_params("/blog/hello-world", "blog/[slug]")
    assert result == {"slug": "hello-world"}


def test_multiple_dynamic_segments():
    """Multiple dynamic segments are extracted correctly."""
    result = extract_route_params("/users/42/posts/99", "users/[id]/posts/[pid]")
    assert result == {"id": "42", "pid": "99"}


def test_no_dynamic_segments():
    """Static route returns empty dict."""
    result = extract_route_params("/about", "about")
    assert result == {}


def test_root_path():
    """Root path with no segments returns empty dict."""
    result = extract_route_params("/", "/")
    assert result == {}


def test_leading_slash_handling():
    """Leading slashes on both path and route are handled."""
    result = extract_route_params("/blog/my-post", "/blog/[slug]")
    assert result == {"slug": "my-post"}


def test_optional_segment():
    """Optional dynamic segment ([[param]]) is extracted."""
    result = extract_route_params("/docs/intro", "docs/[[section]]")
    assert result == {"section": "intro"}


def test_no_match_shorter_path():
    """When path has fewer segments than route, missing params are skipped."""
    result = extract_route_params("/blog", "blog/[slug]")
    assert result == {}


def test_preserves_special_characters_in_value():
    """Values with hyphens and other URL-safe chars are preserved."""
    result = extract_route_params("/blog/my-great-post-2024", "blog/[slug]")
    assert result == {"slug": "my-great-post-2024"}


def test_catch_all_captures_remaining_segments():
    """A catch-all captures every remaining segment as a list, like the client."""
    result = extract_route_params("/docs/a/b/c", "docs/[[...splat]]")
    assert result == {"splat": ["a", "b", "c"]}


def test_catch_all_without_segments():
    """An empty catch-all is omitted, like the client."""
    result = extract_route_params("/docs", "docs/[[...splat]]")
    assert result == {}
