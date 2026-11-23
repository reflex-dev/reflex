"""Regression checks for shared documentation presentation."""

from typing import Literal, get_args

import pytest
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


@pytest.mark.parametrize("name", ["treemap", "sankeychart"])
def test_chart_previews_are_bundled(name):
    """Both theme previews exist locally instead of pointing at missing CDN files."""
    from pathlib import Path

    from reflex_docs.pages.library_previews import component_card

    rendered = str(component_card(name, f"/library/graphing/charts/{name}/", "charts"))
    for mode in ("light", "dark"):
        path = f"components_previews/charts/{mode}/{name}.svg"
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


def test_generated_preview_keeps_wide_components_scrollable():
    """The preview retains its example width inside a local scroll container."""
    from reflex_docs.pages.docs.component import component_docs

    rendered = component_docs(
        (type(rx.button()), "rx.button"),
        {"Button": 'lambda **props: rx.button("Wide preview", width="400px", **props)'},
    )
    playground = rendered.children[2].children[0]
    preview = playground.children[0]
    assert "overflow-x-auto" in str(preview.class_name)
    assert "400px" in str(preview.children[0])


@pytest.mark.parametrize(
    ("type_", "label"),
    [
        (dict[str, str | rx.Var | rx.Color], "str | Var | Color"),
        (dict[str, str | dict[str, str]], "str | dict[str, str]"),
        (dict[str, int], "int"),
        (dict[str, Literal["left", "right"]], 'Literal["left", "right"]'),
        (dict[str, Literal[1, 2] | None], "Literal[1, 2] | None"),
    ],
)
def test_dict_prop_value_types_use_short_names(type_, label):
    """Dict value types name each member without module paths on every Python."""
    from reflex_docs.pages.docs.component import _type_label

    assert _type_label(get_args(type_)[1]) == label


BUTTON_OWN_PROPS = [
    "as_child",
    "size",
    "variant",
    "color_scheme",
    "high_contrast",
    "radius",
    "loading",
    "auto_focus",
    "disabled",
    "form",
    "form_action",
    "form_enc_type",
    "form_method",
    "form_no_validate",
    "form_target",
    "name",
    "type",
    "value",
]
GLOBAL_HTML_ATTRIBUTES = [
    "access_key",
    "auto_capitalize",
    "content_editable",
    "context_menu",
    "dir",
    "draggable",
    "enter_key_hint",
    "hidden",
    "input_mode",
    "item_prop",
    "lang",
    "role",
    "slot",
    "spell_check",
    "tab_index",
    "title",
]


def _prop_names(table: rx.Component) -> list[str]:
    """Read the prop names from a props table, in row order."""
    pending, names = [table], []
    while pending:
        node = pending.pop(0)
        if isinstance(node, rx.el.tr.__self__) and isinstance(
            node.children[0], rx.el.td.__self__
        ):
            cell = node.children[0]
            while not isinstance(cell, rx.code.__self__):
                cell = cell.children[0]
            names.append(str(cell.children[0].contents).strip('"'))
            continue
        pending.extend(node.children)
    return names


def test_button_props_list_its_own_props_before_global_html_attributes():
    """Component props lead the table; global attributes are collapsed after them."""
    from reflex_docgen import generate_documentation

    from reflex_docs.pages.docs.component import component_docs, split_props

    button = type(rx.button())
    own, global_attrs = split_props(button, generate_documentation(button).props)
    assert [prop.name for prop in own] == BUTTON_OWN_PROPS
    assert [prop.name for prop in global_attrs] == GLOBAL_HTML_ATTRIBUTES

    rendered = component_docs((button, "rx.button"), {})
    props_table = rendered.children[2].children[-1]
    assert _prop_names(props_table) == BUTTON_OWN_PROPS
    disclosure = rendered.children[3]
    assert disclosure.tag == "details"
    summary, table = disclosure.children
    assert str(summary.children[0].contents) == '"Inherited HTML attributes (16)"'
    assert _prop_names(table) == GLOBAL_HTML_ATTRIBUTES


def test_component_reference_headings_nest_under_api_reference():
    """Component headings sit one level below API Reference, on the page and in the TOC."""
    from reflex_docs.pages.docs.component import api_reference_toc, component_docs
    from reflex_docs.templates.docpage import h3_comp

    h3_tag = h3_comp(text="").tag
    headings, pending = [], [component_docs((type(rx.button()), "rx.button"), {})]
    while pending:
        node = pending.pop(0)
        if node.tag == h3_tag:
            headings.append(("h3", str(node.text)))
        elif isinstance(node, rx.heading.__self__):
            headings.append((str(node.as_), str(node.children[0].contents)))
        pending.extend(node.children)
    assert headings == [
        ("h3", '"rx.button"'),
        ('"h4"', '"Props"'),
        ('"h4"', '"Event Triggers"'),
    ]
    assert api_reference_toc(["rx.button"], has_shared=False) == [
        (2, "API Reference"),
        (3, "rx.button"),
    ]
    assert api_reference_toc(["rx.el.div", "rx.el.input"], has_shared=True) == [
        (2, "API Reference"),
        (3, "rx.el.div"),
        (3, "rx.el.input"),
        (3, "Shared HTML props"),
    ]
    assert api_reference_toc([], has_shared=False) == []
