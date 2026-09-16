"""Regression checks for shared documentation presentation."""

import reflex as rx

from reflex_docs.pages.docs.source import stacked_description_rows
from reflex_docs.pages.docs_landing.views.ai_builder import card
from reflex_docs.pages.docs_landing.views.link_item import link_item
from reflex_docs.templates.docpage.docpage import breadcrumb


def test_mobile_breadcrumb_drawer_has_a_named_button_trigger():
    """The mobile navigation overlay must be keyboard and screen-reader usable."""
    rendered = str(breadcrumb("/getting-started/introduction/", rx.el.nav()))
    assert '"aria-label":"Open documentation navigation"' in rendered


def test_landing_card_link_has_an_accessible_name():
    """Overlay links remain understandable without the surrounding visual card."""
    rendered = str(link_item("BookOpen01Icon", "Learn Reflex", "Start here", "/intro/"))
    assert "aria-label" in rendered and "Learn Reflex" in rendered


def test_ai_card_focus_outline_is_inside_the_clipped_card():
    """The overlay's focus indicator must fit within the rounded clipping box."""
    rendered = str(
        card("AI Builder", "Build an app", rx.text("Preview"), "/ai/", "blue")
    )
    assert "focus-visible:-outline-offset-4" in rendered
    assert "focus-visible:outline-offset-4" not in rendered


def test_responsive_description_is_rendered_once():
    """Mobile and desktop layouts share one description and its element IDs."""
    calls = []

    def description():
        """Return content with a document-wide unique anchor."""
        calls.append(True)
        return rx.el.p("Field description", id="unique-description")

    rows = stacked_description_rows([(rx.text("Field"), "")], description, "2xl")
    assert len(calls) == 1
    assert sum(str(row).count('id:"unique-description"') for row in rows) == 1


def test_deferred_demo_preserves_code_and_defers_only_the_preview():
    """Heavy previews can wait for the viewport while their code stays readable."""
    from reflex_docs.docgen_pipeline import render_markdown

    rendered = str(
        render_markdown(
            '```python demo exec defer\nimport reflex as rx\ndef preview():\n    return rx.text("Preview")\n```'
        )
    )
    assert "DeferredDemo" in rendered
    assert "Preview" in rendered
    assert "rx.text" in rendered


def test_treemap_previews_are_bundled():
    """Both theme previews exist locally instead of pointing at missing CDN files."""
    from pathlib import Path

    from reflex_docs.pages.library_previews import component_card

    rendered = str(
        component_card("treemap", "/library/graphing/charts/treemap/", "charts")
    )
    for mode in ("light", "dark"):
        path = f"components_previews/charts/{mode}/treemap.svg"
        assert (Path(__file__).parents[1] / "assets" / path).is_file()
        assert path in rendered
    assert "web.reflex-assets.dev/components_previews/charts" not in rendered


def test_component_destinations_use_canonical_trailing_slash():
    """Component links avoid a redirect before loading the documentation."""
    from reflex_docs.templates.docpage.sidebar.sidebar_items.component_lib import (
        get_component_link,
    )

    assert (
        get_component_link("data-display", ["avatar"])
        == "/library/data-display/avatar/"
    )


def test_preview_cards_reserve_space_before_images_load():
    """Lazy preview images must not shift the catalog when they arrive."""
    from reflex_docs.pages.library_previews import component_card

    rendered = str(
        component_card("avatar", "/library/data-display/avatar/", "data-display")
    )
    assert "aspect-[320/232]" in rendered


def test_multi_component_reference_shares_only_identical_html_props():
    """Common HTML props appear once, while element-specific props stay local."""
    from reflex_docs.pages.docs.component import component_docs, shared_html_props

    components = [type(rx.el.div()), type(rx.el.input()), type(rx.el.portal())]
    shared = shared_html_props(components)
    assert "title" in {prop.name for prop in shared}
    assert "value" not in {prop.name for prop in shared}
    assert shared_html_props(components[:1]) == ()
    rendered = str(component_docs((components[1], "rx.el.input"), {}, shared))
    assert "#shared-html-props" in rendered
    assert '"value"' in rendered
    assert '"access_key"' not in rendered
    assert '"title"' not in rendered

    class OverrideTitle(type(rx.el.div())):
        title: rx.Var[int]

    override = str(component_docs((OverrideTitle, "OverrideTitle"), {}, shared))
    assert '"title"' in override
    assert '"access_key"' not in override


def test_state_catalog_offers_real_guides_instead_of_an_empty_grid():
    """The state catalog provides useful routes and can be found in the library."""
    from reflex_docs.pages.docs.library import library
    from reflex_docs.pages.library_previews import library_previews

    route = next(route for route in library_previews if route.path == "/library/state/")
    rendered = str(route.component())
    assert 'href:"/docs/state/overview/"' in rendered
    assert 'href:"/docs/events/events-overview/"' in rendered
    assert 'to:"/library/state/"' in str(library.component())


def test_docs_registers_its_own_not_found_page():
    """The registered 404 uses the docs recovery page."""
    from reflex_docs.pages import page404
    from reflex_docs.pages.page404 import not_found

    assert page404.component is not_found
    assert page404.meta == [{"name": "robots", "content": "noindex"}]


def test_cloud_overview_exposes_markdown_and_toc():
    """The Cloud guide provides the metadata consumed by docs page actions."""
    from reflex_docs.pages.docs.cloud import (
        CLOUD_OVERVIEW_MARKDOWN,
        cloud_overview_content,
    )

    (toc, markdown), body = cloud_overview_content()
    assert len(toc) >= 4
    assert markdown == CLOUD_OVERVIEW_MARKDOWN
    assert "Deploy your first app" in str(body)
