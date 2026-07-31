"""Unit tests for SSR route-param extraction."""

from __future__ import annotations

from reflex.route import extract_route_params


class TestExtractRouteParams:
    """Tests for the extract_route_params utility function."""

    def test_simple_dynamic_route(self):
        """Single dynamic segment is extracted correctly."""
        result = extract_route_params("/blog/hello-world", "blog/[slug]")
        assert result == {"slug": "hello-world"}

    def test_multiple_dynamic_segments(self):
        """Multiple dynamic segments are extracted correctly."""
        result = extract_route_params("/users/42/posts/99", "users/[id]/posts/[pid]")
        assert result == {"id": "42", "pid": "99"}

    def test_no_dynamic_segments(self):
        """Static route returns empty dict."""
        result = extract_route_params("/about", "about")
        assert result == {}

    def test_root_path(self):
        """Root path with no segments returns empty dict."""
        result = extract_route_params("/", "/")
        assert result == {}

    def test_leading_slash_handling(self):
        """Leading slashes on both path and route are handled."""
        result = extract_route_params("/blog/my-post", "/blog/[slug]")
        assert result == {"slug": "my-post"}

    def test_optional_segment(self):
        """Optional dynamic segment ([[param]]) is extracted."""
        result = extract_route_params("/docs/intro", "docs/[[section]]")
        assert result == {"section": "intro"}

    def test_no_match_shorter_path(self):
        """When path has fewer segments than route, missing params are skipped."""
        result = extract_route_params("/blog", "blog/[slug]")
        assert result == {}

    def test_preserves_special_characters_in_value(self):
        """Values with hyphens and other URL-safe chars are preserved."""
        result = extract_route_params("/blog/my-great-post-2024", "blog/[slug]")
        assert result == {"slug": "my-great-post-2024"}
