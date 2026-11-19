"""Unit tests for SSR route-param extraction and compile output."""

from __future__ import annotations

from pytest_mock import MockerFixture
from reflex_base import constants
from reflex_base.compiler.templates import app_root_template

import reflex as rx
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


def _render_root(mocker: MockerFixture, ssr_mode: constants.SsrMode) -> str:
    """Render the app root template with minimal params.

    Args:
        mocker: Patches the config the template reads the SSR mode from.
        ssr_mode: The SSR mode to render with.

    Returns:
        Rendered template string.
    """
    mocker.patch(
        "reflex_base.ssr.get_config",
        return_value=rx.Config(app_name="test", ssr_mode=ssr_mode),
    )
    return app_root_template(
        imports=[],
        custom_codes=[],
        hooks={},
        window_libraries=[],
        render={"contents": "children"},
        dynamic_imports=set(),
    )


SSR_ROOT_LOADER = """export async function loader({ request }) {
  // Fetch on_load-hydrated state from the Python /_ssr_data endpoint so the
  // server-rendered HTML already contains real data.
  try {
    const url = new URL(request.url);
    const res = await fetch(getBackendURL(env.SSR_DATA), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(request.headers.get("cookie") ? { Cookie: request.headers.get("cookie") } : {}),
      },
      body: JSON.stringify({
        path: url.pathname,
        search: url.search,
        headers: Object.fromEntries(request.headers),
      }),
    });
    if (res.ok) return res.json();
  } catch (e) {
    console.error("SSR data fetch failed:", e);
  }
  // The page renders with default state; the error status keeps it out of
  // caches (the ISR render tier keeps the stale page or serves the shell).
  return ssrData({ state: null }, { status: 503 });
}

// The client reads the loader's state only on mount and the live session runs
// on_load, so client-side navigations skip the loader instead of running the
// page's on_load handlers a second time on the backend.
export function shouldRevalidate() {
  return false;
}
"""


def test_root_template_ssr_loader(mocker: MockerFixture):
    """With SSR on, the root loads the page state, fails with 503 and never revalidates."""
    plain = _render_root(mocker, constants.SsrMode.OFF)
    imports_anchor = "import { Outlet } from 'react-router';\n"
    loader_anchor = "\nfunction ReflexProviders("
    layout_body = "  return jsx(AppLayout, {}, jsx(ReflexProviders, {}, children));"
    for anchor in (imports_anchor, loader_anchor, layout_body):
        assert plain.count(anchor) == 1, anchor
    expected = (
        plain
        .replace(
            imports_anchor,
            imports_anchor
            + 'import { data as ssrData, useLoaderData } from "react-router";\n'
            + 'import { getBackendURL } from "$/utils/state";\n'
            + 'import { SSRStateContext } from "$/utils/context";\n'
            + 'import env from "$/env.json";\n',
        )
        .replace(loader_anchor, SSR_ROOT_LOADER + loader_anchor)
        .replace(
            layout_body,
            "  const loaderData = useLoaderData();\n"
            "  const ssrState = loaderData?.state ?? null;\n"
            "  return jsx(AppLayout, {}, jsx(SSRStateContext.Provider, "
            "{value: ssrState}, jsx(ReflexProviders, {}, children)));",
        )
    )

    assert _render_root(mocker, constants.SsrMode.ALWAYS) == expected
