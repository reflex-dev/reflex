"""Validate URL metadata in the actual production build, not only its inputs."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import pytest
from reflex_base.environment import environment

APP = Path(__file__).parents[1]
WEB = APP / environment.REFLEX_WEB_WORKDIR.get()
SITEMAP = WEB / "public/sitemap.xml"


class PageURLs(HTMLParser):
    """Collect canonical and social URLs from generated HTML."""

    def __init__(self, html: str):
        super().__init__()
        self.canonical = []
        self.social = []
        self.markdown = []
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        """Collect URL-bearing metadata tags."""
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical.append(attrs.get("href"))
        if (
            tag == "link"
            and attrs.get("rel") == "alternate"
            and attrs.get("type") == "text/markdown"
        ):
            self.markdown.append(attrs.get("href"))
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "meta" and (
            attrs.get("property") in {"og:url", "twitter:url"}
            or attrs.get("name") == "twitter:url"
        ):
            self.social.append(attrs.get("content"))


@pytest.mark.xfail(
    not SITEMAP.is_file(),
    reason="Build the docs before validating published SEO metadata.",
    run=False,
)
def test_generated_sitemap_and_page_urls_share_public_origin():
    """Every sitemap location and generated canonical uses one public docs prefix."""
    base = "https://reflex.dev/docs"
    urls = [
        element.text
        for element in ElementTree.parse(SITEMAP).iter()
        if element.tag.endswith("loc")
    ]
    assert urls
    assert len(urls) == len(set(urls))
    canonical_paths = {urlsplit(url).path for url in urls}
    redirected = set()
    for url in urls:
        assert url.startswith(base + "/"), url
        assert url.endswith("/"), url
        path = urlsplit(url).path
        assert "/docs/docs/" not in path, url
        page = WEB / "build/client" / path.lstrip("/") / "index.html"
        assert page.is_file(), page
        metadata = PageURLs(page.read_text())
        assert metadata.canonical == [url], (url, metadata.canonical)
        assert len(metadata.social) == 2, (url, metadata.social)
        assert all(value == url for value in metadata.social), (url, metadata.social)
        markdown_url = (
            url + "index.md" if url == base + "/" else url.rstrip("/") + ".md"
        )
        assert metadata.markdown == [markdown_url], (url, metadata.markdown)
        markdown = WEB / "build/client" / urlsplit(markdown_url).path.lstrip("/")
        assert markdown.is_file(), markdown
        assert len(markdown.read_text().split()) > 20, markdown
        for href in metadata.links:
            target = urlsplit(urljoin(url, href))
            if (
                target.netloc == urlsplit(base).netloc
                and target.path + "/" in canonical_paths
            ):
                redirected.add((path, href))
    assert not redirected, sorted(redirected)


@pytest.mark.xfail(
    not SITEMAP.is_file(),
    reason="Build the docs before checking reference payloads.",
    run=False,
)
@pytest.mark.parametrize(
    ("route", "budget"),
    [
        ("library/html/layout", 350_000),
        ("library/html/text", 300_000),
        ("library/html/media", 350_000),
        ("library/tables-and-data-grids/table", 500_000),
    ],
)
def test_reference_html_stays_within_payload_budget(route, budget):
    """Catch accidental reintroduction of repeated inherited API tables."""
    page = WEB / "build/client/docs" / route / "index.html"
    assert page.stat().st_size < budget, (route, page.stat().st_size, budget)


def test_introduction_counter_uses_high_contrast_buttons():
    """The introductory live demo keeps readable labels on its colored buttons."""
    page = WEB / "build/client/docs/getting-started/introduction/index.html"
    if not page.is_file():
        pytest.skip("Build the docs before checking exported counter buttons.")

    class Buttons(HTMLParser):
        def __init__(self):
            super().__init__()
            self.colors = set()

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            accent = attrs.get("data-accent-color")
            if tag == "button" and accent in {"ruby", "grass"}:
                assert "rt-high-contrast" in attrs.get("class", "").split()
                self.colors.add(accent)

    buttons = Buttons()
    buttons.feed(page.read_text())
    assert buttons.colors == {"ruby", "grass"}
