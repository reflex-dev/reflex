"""Validate URL metadata in the actual production build, not only its inputs."""

import json
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
    """Collect canonical, social and structured metadata from generated HTML."""

    def __init__(self, html: str):
        super().__init__()
        self.canonical = []
        self.social = []
        self.markdown = []
        self.links = []
        self.structured_data = []
        self._json_ld = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        """Collect URL-bearing metadata tags."""
        attrs = dict(attrs)
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self._json_ld = []
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

    def handle_data(self, data):
        """Collect script text without decoding JSON until the closing tag."""
        if self._json_ld is not None:
            self._json_ld.append(data)

    def handle_endtag(self, tag):
        """Parse complete structured-data scripts."""
        if tag == "script" and self._json_ld is not None:
            self.structured_data.append(json.loads("".join(self._json_ld)))
            self._json_ld = None


def check_breadcrumbs(metadata, url, canonical_urls):
    """Validate ordered breadcrumbs against the exported public page inventory."""
    breadcrumbs = [
        data
        for data in metadata.structured_data
        if data.get("@type") == "BreadcrumbList"
    ]
    assert len(breadcrumbs) == 1, (url, breadcrumbs)
    items = breadcrumbs[0]["itemListElement"]
    assert items, url
    assert [item["position"] for item in items] == list(range(1, len(items) + 1))
    assert items[-1]["item"] == url
    for item in items:
        assert item["@type"] == "ListItem" and item["name"], (url, item)
        assert item["item"] in canonical_urls, (url, item)


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
    canonical_urls = set(urls)
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
        check_breadcrumbs(metadata, url, canonical_urls)
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
