"""Regressions for app-owned HTTP routing exports."""

from types import SimpleNamespace

import pytest
from reflex_site_shared.http_routing import render_routing


def pages(*routes):
    return [SimpleNamespace(route=route) for route in routes]


def test_registered_routes_include_noindex_and_client_pages():
    redirects, inventory = render_routing(pages("index", "booked", "client", "404"), {})
    assert '"/booked"' in inventory
    assert '"/client"' in inventory
    assert '"/404"' not in inventory
    assert "error @unknownPage 404" in inventory
    assert "redir " not in redirects


def test_mount_and_dynamic_catalog_are_exact():
    _, inventory = render_routing(
        pages("index", "templates/[slug]", "templates/real"),
        {},
        frontend_path="/blog",
        excluded_dynamic_routes=("templates/[slug]",),
    )
    assert '"/blog"' in inventory
    assert '"/blog/templates/real"' in inventory
    assert "*" not in inventory
    with pytest.raises(ValueError, match="dynamic"):
        render_routing(pages("templates/[slug]"), {})


def test_redirect_chains_flatten_and_preserve_query_and_fragment():
    redirects, _ = render_routing(
        pages("enterprise"),
        {"/old": "/middle", "/middle": "/enterprise#details"},
    )
    assert '"/enterprise/{querySuffix}#details" 301' in redirects
    assert 'path "/old" "/old/"' in redirects
    assert "method GET HEAD" in redirects
    assert '"/middle/{querySuffix}' not in redirects


def test_missing_targets_cycles_and_unsafe_paths_fail_build():
    for aliases in [
        {"/old": "/missing"},
        {"/a": "/b", "/b": "/a"},
        {"/bad*": "/valid"},
    ]:
        with pytest.raises(ValueError):
            render_routing(pages("valid"), aliases)


def test_external_targets_are_not_slash_normalized():
    redirects, _ = render_routing(
        pages("index"), {"/releases": "https://github.com/org/repo/releases"}
    )
    assert "https://github.com/org/repo/releases{querySuffix}" in redirects


def test_empty_route_inventory_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        render_routing([], {})


def test_plugin_schedules_both_export_assets(monkeypatch):
    from reflex_site_shared import http_routing

    monkeypatch.setattr(
        http_routing, "get_config", lambda: SimpleNamespace(frontend_path="/blog")
    )
    files = []
    plugin = http_routing.HttpRoutingPlugin(redirects={"/blog/old": "/blog/new"})
    plugin.pre_compile(
        unevaluated_pages=pages("index", "new"),
        add_save_task=lambda task, *args: files.extend(task(*args)),
    )
    assert len(files) == 2
    assert files[0][0].endswith("__http_routing__/app-redirects.caddy")
    assert files[1][0].endswith("__http_routing__/app-pages.caddy")
    assert '"/blog/new/{querySuffix}" 301' in files[0][1]
    assert '"/blog/new"' in files[1][1]
