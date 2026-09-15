"""Validate URL metadata in the actual production build, not only its inputs."""

import runpy
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
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
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        """Collect URL-bearing metadata tags."""
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical.append(attrs.get("href"))
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
    config = runpy.run_path(str(APP / "rxconfig.py"))["config"]
    base = config.deploy_url.rstrip("/") + config.frontend_path.rstrip("/")
    urls = [
        element.text
        for element in ElementTree.parse(SITEMAP).iter()
        if element.tag.endswith("loc")
    ]
    assert urls
    assert len(urls) == len(set(urls))
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
