"""Unit tests for the sitemap plugin."""

import datetime
from unittest.mock import MagicMock, patch

import reflex as rx
from reflex.app import UnevaluatedPage
from reflex.plugins.sitemap import SitemapLink, generate_links_for_sitemap, generate_xml


def test_generate_xml_empty_links():
    """Test generate_xml with an empty list of links."""
    xml_output = generate_xml([])
    expected = """<?xml version='1.0' encoding='utf-8'?>
<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9" />"""
    assert xml_output == expected


def test_generate_xml_single_link_loc_only():
    """Test generate_xml with a single link having only loc."""
    links: list[SitemapLink] = [{"loc": "https://example.com"}]
    xml_output = generate_xml(links)
    expected = """<?xml version='1.0' encoding='utf-8'?>
<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com</loc>
  </url>
</urlset>"""
    assert xml_output == expected


def test_generate_xml_multiple_links_all_fields():
    """Test generate_xml with multiple links having all fields."""
    now = datetime.datetime(2023, 6, 13, 12, 0, 0)
    links: list[SitemapLink] = [
        {
            "loc": "https://example.com/page1",
            "lastmod": now,
            "changefreq": "daily",
            "priority": 0.8,
        },
        {
            "loc": "https://example.com/page2",
            "lastmod": datetime.datetime(2023, 1, 1, 0, 0, 0),
            "changefreq": "weekly",
            "priority": 0.5,
        },
    ]
    xml_output = generate_xml(links)
    expected = """<?xml version='1.0' encoding='utf-8'?>
<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
    <changefreq>daily</changefreq>
    <lastmod>2023-06-13T12:00:00</lastmod>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://example.com/page2</loc>
    <changefreq>weekly</changefreq>
    <lastmod>2023-01-01T00:00:00</lastmod>
    <priority>0.5</priority>
  </url>
</urlset>"""
    assert xml_output == expected


@patch("reflex.config.get_config")
@patch("reflex.utils.console.warn")
def test_generate_links_for_sitemap_static_routes(
    mock_warn: MagicMock, mock_get_config: MagicMock
):
    """Test generate_links_for_sitemap with static routes.

    Args:
        mock_warn: Mock for the console.warn function.
        mock_get_config: Mock for the get_config function.
    """
    mock_get_config.return_value.deploy_url = "https://example.com"

    def mock_component():
        return rx.text("Test")

    pages = [
        UnevaluatedPage(
            component=mock_component,
            route="index",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={},
        ),
        UnevaluatedPage(
            component=mock_component,
            route="about",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={},
        ),
        UnevaluatedPage(
            component=mock_component,
            route="contact",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": {"priority": 0.7, "changefreq": "monthly"}},
        ),
    ]
    links = generate_links_for_sitemap(pages)
    assert len(links) == 3
    assert {"loc": "https://example.com/"} in links
    assert {"loc": "https://example.com/about"} in links
    assert {
        "loc": "https://example.com/contact",
        "priority": 0.7,
        "changefreq": "monthly",
    } in links
    mock_warn.assert_not_called()


@patch("reflex.config.get_config")
@patch("reflex.utils.console.warn")
def test_generate_links_for_sitemap_dynamic_routes(
    mock_warn: MagicMock, mock_get_config: MagicMock
):
    """Test generate_links_for_sitemap with dynamic routes.

    Args:
        mock_warn: Mock for the console.warn function.
        mock_get_config: Mock for the get_config function.
    """
    mock_get_config.return_value.deploy_url = "https://sub.example.org"
    now = datetime.datetime(2023, 6, 13, 12, 0, 0)

    def mock_component():
        return rx.text("Test")

    pages = [
        UnevaluatedPage(
            component=mock_component,
            route="blog/[id]",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={
                "sitemap": {
                    "loc": "/custom-blog-path",
                    "lastmod": now,
                    "priority": 0.9,
                }
            },
        ),
        UnevaluatedPage(
            component=mock_component,
            route="products/[name]",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={},
        ),  # No sitemap config
        UnevaluatedPage(
            component=mock_component,
            route="user/[user_id]/profile",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": {"changefreq": "yearly"}},
        ),  # Has sitemap config but no loc
    ]
    links = generate_links_for_sitemap(pages)
    assert len(links) == 1
    expected_link = {
        "loc": "https://sub.example.org/custom-blog-path",
        "lastmod": now,
        "priority": 0.9,
    }
    assert expected_link in links
    assert mock_warn.call_count == 1
    mock_warn.assert_any_call(
        "Dynamic route 'user/[user_id]/profile' does not have a 'loc' in sitemap configuration. Skipping."
    )


@patch("reflex.config.get_config")
@patch("reflex.utils.console.warn")
def test_generate_links_for_sitemap_404_route(
    mock_warn: MagicMock, mock_get_config: MagicMock
):
    """Test generate_links_for_sitemap with the 404 route.

    Args:
        mock_warn: Mock for the console.warn function.
        mock_get_config: Mock for the get_config function.
    """
    mock_get_config.return_value.deploy_url = None  # No deploy URL

    def mock_component():
        return rx.text("404")

    pages = [
        UnevaluatedPage(
            component=mock_component,
            route="404",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": {"loc": "/custom-404", "priority": 0.1}},
        ),
        UnevaluatedPage(
            component=mock_component,
            route="404",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": {"priority": 0.2}},
        ),  # Has sitemap config but no loc
    ]
    links = generate_links_for_sitemap(pages)
    assert len(links) == 1
    assert {"loc": "/custom-404", "priority": 0.1} in links
    mock_warn.assert_called_once_with(
        "Route 404 '404' does not have a 'loc' in sitemap configuration. Skipping."
    )


@patch("reflex.config.get_config")
def test_generate_links_for_sitemap_opt_out(mock_get_config: MagicMock):
    """Test generate_links_for_sitemap with sitemap set to None.

    Args:
        mock_get_config: Mock for the get_config function.
    """
    mock_get_config.return_value.deploy_url = None  # No deploy URL

    def mock_component():
        return rx.text("Unlisted")

    pages = [
        UnevaluatedPage(
            component=mock_component,
            route="unlisted",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": None},
        ),
        UnevaluatedPage(
            component=mock_component,
            route="listed",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={},
        ),
    ]
    links = generate_links_for_sitemap(pages)
    assert len(links) == 1
    assert {"loc": "/listed"} in links


@patch("reflex.config.get_config")
def test_generate_links_for_sitemap_loc_override(mock_get_config: MagicMock):
    """Test generate_links_for_sitemap with loc override in sitemap config.

    Args:
        mock_get_config: Mock for the get_config function.
    """
    mock_get_config.return_value.deploy_url = "http://localhost:3000"

    def mock_component():
        return rx.text("Test")

    pages = [
        UnevaluatedPage(
            component=mock_component,
            route="features",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": {"loc": "https://override.com/features_page"}},
        ),
        UnevaluatedPage(
            component=mock_component,
            route="pricing",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": {"loc": "/custom_pricing"}},
        ),
    ]
    links = generate_links_for_sitemap(pages)
    assert len(links) == 2
    assert {"loc": "https://override.com/features_page"} in links
    assert {"loc": "http://localhost:3000/custom_pricing"} in links


@patch("reflex.config.get_config")
def test_generate_links_for_sitemap_priority_clamping(mock_get_config: MagicMock):
    """Test that priority is clamped between 0.0 and 1.0.

    Args:
        mock_get_config: Mock for the get_config function.
    """
    mock_get_config.return_value.deploy_url = "https://example.com"

    def mock_component():
        return rx.text("Test")

    pages = [
        UnevaluatedPage(
            component=mock_component,
            route="high_prio",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": {"priority": 1.5}},
        ),
        UnevaluatedPage(
            component=mock_component,
            route="low_prio",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": {"priority": -0.5}},
        ),
        UnevaluatedPage(
            component=mock_component,
            route="valid_prio",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": {"priority": 0.5}},
        ),
    ]
    links = generate_links_for_sitemap(pages)
    expected_links = [
        {"loc": "https://example.com/high_prio", "priority": 1.0},
        {"loc": "https://example.com/low_prio", "priority": 0.0},
        {"loc": "https://example.com/valid_prio", "priority": 0.5},
    ]
    for expected_link in expected_links:
        assert expected_link in links


@patch("reflex.config.get_config")
def test_generate_links_for_sitemap_no_deploy_url(mock_get_config: MagicMock):
    """Test generate_links_for_sitemap when deploy_url is not set.

    Args:
        mock_get_config: Mock for the get_config function.
    """
    mock_get_config.return_value.deploy_url = None

    def mock_component():
        return rx.text("Test")

    pages = [
        UnevaluatedPage(
            component=mock_component,
            route="home",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": {"loc": "/home"}},
        ),
        UnevaluatedPage(
            component=mock_component,
            route="about",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={},
        ),  # No loc, should use route
        UnevaluatedPage(
            component=mock_component,
            route="index",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={},
        ),  # Special case for index
    ]
    links = generate_links_for_sitemap(pages)
    assert len(links) == 3
    expected_links = [{"loc": "/home"}, {"loc": "/about"}, {"loc": "/"}]
    for expected_link in expected_links:
        assert expected_link in links


@patch("reflex.config.get_config")
def test_generate_links_for_sitemap_deploy_url_trailing_slash(
    mock_get_config: MagicMock,
):
    """Test generate_links_for_sitemap with deploy_url having a trailing slash.

    Args:
        mock_get_config: Mock for the get_config function.
    """
    mock_get_config.return_value.deploy_url = "https://example.com/"

    def mock_component():
        return rx.text("Test")

    pages = [
        UnevaluatedPage(
            component=mock_component,
            route="testpage",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={},
        ),
    ]
    links = generate_links_for_sitemap(pages)
    assert len(links) == 1
    assert {"loc": "https://example.com/testpage"} in links


@patch("reflex.config.get_config")
def test_generate_links_for_sitemap_loc_leading_slash(mock_get_config: MagicMock):
    """Test generate_links_for_sitemap with loc having a leading slash.

    Args:
        mock_get_config: Mock for the get_config function.
    """
    mock_get_config.return_value.deploy_url = "https://example.com"

    def mock_component():
        return rx.text("Test")

    pages = [
        UnevaluatedPage(
            component=mock_component,
            route="another",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": {"loc": "/another"}},
        ),
    ]
    links = generate_links_for_sitemap(pages)
    assert len(links) == 1
    assert {"loc": "https://example.com/another"} in links


@patch("reflex.config.get_config")
def test_generate_links_for_sitemap_loc_full_url(mock_get_config: MagicMock):
    """Test generate_links_for_sitemap with loc being a full URL.

    Args:
        mock_get_config: Mock for the get_config function.
    """
    mock_get_config.return_value.deploy_url = "https://example.com"

    def mock_component():
        return rx.text("Test")

    pages = [
        UnevaluatedPage(
            component=mock_component,
            route="external",
            title=None,
            description=None,
            image="favicon.ico",
            on_load=None,
            meta=[],
            context={"sitemap": {"loc": "http://othersite.com/page"}},
        ),
    ]
    links = generate_links_for_sitemap(pages)
    assert len(links) == 1
    assert {"loc": "http://othersite.com/page"} in links
