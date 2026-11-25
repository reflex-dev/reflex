"""Tests for assigning docs routes to navbar tabs and sidebar sections."""

import json
import subprocess

import pytest
import reflex as rx

from reflex_docs import sections

ROUTE_SECTIONS = [
    ("/", "overview", "overview"),
    ("/ai/", "ai", "ai"),
    ("/ai/integrations/mcp-overview/", "ai", "ai"),
    ("/getting-started/introduction/", "framework", "framework"),
    ("/wrapping-react/library-and-tags/", "framework", "framework"),
    ("/utility-methods/exception-handlers/", "framework", "framework"),
    ("/library/", "components", "framework"),
    ("/library/forms/button/", "components", "framework"),
    ("/api-reference/app/", "api-reference", "framework"),
    ("/changelog/", "api-reference", "framework"),
    ("/changelog/reflex-hosting-cli/", "api-reference", "framework"),
    ("/changelog/reflex-enterprise/", "api-reference", "framework"),
    ("/enterprise/overview/", "enterprise", "framework"),
    ("/hosting/overview/", "cloud", "cloud"),
    ("/hosting/cli/deploy/", "cloud", "cloud"),
    ("/xy/", "xy", "xy"),
]


@pytest.mark.parametrize(("path", "section", "tab"), ROUTE_SECTIONS)
def test_route_section_comes_from_its_first_segment(path, section, tab):
    """Only the first path segment picks a section, never a substring of the route.

    Regression test: "library" in /wrapping-react/library-and-tags/ selected the
    Components sidebar, and "hosting" in /changelog/reflex-hosting-cli/ lit the
    Cloud tab.
    """
    assert (sections.docs_section(path), sections.navbar_tab(path)) == (section, tab)


def _sidebar_links(items) -> list[str]:
    """Collect the page links of sidebar items, including nested ones.

    Cross-references into another section are skipped.

    Args:
        items: Sidebar items.

    Returns:
        Each linked route.
    """
    links = []
    for item in items:
        if item.link and not item.exclude_from_prev_next:
            links.append(item.link)
        links.extend(_sidebar_links(item.children))
    return links


def test_every_sidebar_page_belongs_to_the_section_that_lists_it():
    """A page in a section's sidebar renders that sidebar and its navbar tab."""
    from reflex_docs.templates.docpage.sidebar.sidebar import (
        agent_toolkit_items,
        ai_builder_integrations,
        ai_builder_overview_items,
        api_reference,
        backend,
        changelog_items,
        component_lib,
        enterprise_items,
        frontend,
        graphing_libs,
        hosting,
        html_lib,
        learn,
        mcp_items,
        recipes,
        skills_items,
        workflows,
    )

    listed = {
        sections.FRAMEWORK: (learn, frontend, backend, workflows, recipes),
        sections.COMPONENTS: (component_lib, graphing_libs, html_lib),
        sections.API_REFERENCE: (api_reference, changelog_items),
        sections.ENTERPRISE: (enterprise_items,),
        sections.CLOUD: (hosting,),
        sections.AI: (
            ai_builder_overview_items,
            ai_builder_integrations,
            agent_toolkit_items,
            mcp_items,
            skills_items,
        ),
    }
    misplaced = {
        link: (expected, sections.docs_section(link))
        for expected, groups in listed.items()
        for items in groups
        for link in _sidebar_links(items)
        if sections.docs_section(link) != expected
    }
    # User Interface > Components links to the component library's landing page.
    assert misplaced == {"/library/": (sections.FRAMEWORK, sections.COMPONENTS)}


def test_client_section_matches_build_time_section():
    """The persistent sidebar picks the same section in the browser as the build does."""
    from reflex_docs.templates.docpage.sidebar.sidebar import flat_items

    # "/constructor/" must not resolve to an inherited Object property.
    paths = sorted(
        {path for path, _, _ in ROUTE_SECTIONS}
        | {item.link for item in flat_items}
        | {"/constructor/"}
    )
    expression = str(sections.docs_section_var(rx.Var("path", _var_type=str).to(str)))
    script = (
        f"const paths = {json.dumps(paths)};"
        "process.stdout.write(JSON.stringify(paths.map((path) => " + expression + ")));"
    )
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True
    )
    assert json.loads(result.stdout) == [sections.docs_section(p) for p in paths]
