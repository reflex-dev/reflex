"""Regression tests for shared documentation demo controls."""

from reflex_site_shared.components.blocks.demo import docdemo
from reflex_site_shared.components.blocks.tabs import doc_tab_list, doc_tab_trigger

import reflex as rx


def test_demo_header_holds_only_the_tabs():
    """Demos carry no promotional link above them, only their view/code tabs."""
    demo = docdemo("rx.text('Example')", comp=rx.text("Example"))
    header = demo.children[0].children[0]
    assert str(header) == str(
        rx.el.div(
            doc_tab_list(
                doc_tab_trigger("View", value="view", icon="eye"),
                doc_tab_trigger("Code", value="code", icon="code-xml"),
            ),
            class_name="docs-demo-header flex w-full items-end justify-end",
        )
    )


def test_selected_demo_tab_has_a_contrasting_surface():
    """Keep the selected tab connected to the neutral demo surface."""
    classes = str(doc_tab_trigger("View", value="view", icon="eye").class_name)
    assert "data-[state=active]:!bg-secondary-2" in classes
    assert "data-[state=active]:!text-secondary-12" in classes
    assert "dark:data-[state=active]:!bg-muted" not in classes
