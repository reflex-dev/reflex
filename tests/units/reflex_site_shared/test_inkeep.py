"""Tests for the shared Inkeep configuration."""

from types import SimpleNamespace

from reflex_site_shared.components.inkeep import Search


def test_inkeep_uses_frontend_path_search_icon(monkeypatch) -> None:
    """Preserve the official search icon under each site's frontend path."""
    monkeypatch.setattr(
        "reflex_site_shared.components.inkeep.get_config",
        lambda: SimpleNamespace(frontend_path="/docs/product"),
    )

    hooks = "\n".join(Search.create().add_hooks())

    assert 'customIcons: {search: {custom: "/docs/product/icons/search.svg"}}' in hooks
