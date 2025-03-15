import unittest.mock
from pathlib import Path

import fastapi
import pytest
import reflex as rx
from reflex import constants
from reflex.utils import prerequisites

from reflex.app import App, ComponentCallable
from reflex.sitemap import (
    generate_xml,
    generate_links_for_sitemap,
    generate_static_sitemap,
    remove_sitemap_file,
)

sitemap_folder_path: Path = (
    Path.cwd() / prerequisites.get_web_dir() / constants.Dirs.STATIC
)

# sitemap file path
sitemap_file_path: Path = sitemap_folder_path / "sitemap.xml"


@pytest.fixture
def app_instance():
    """Fixture to create an instance of the app."""
    app = App()
    return app


@pytest.fixture
def index_page() -> ComponentCallable:
    """An index page.

    Returns:
        The index page.
    """

    def index():
        return rx.box("Index")

    return index


@pytest.fixture
def about_page() -> ComponentCallable:
    """An about page.

    Returns:
        The about page.
    """

    def about():
        return rx.box("About")

    return about


mock_xml = """<?xml version="1.0" ?>
<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>http://localhost:3000/</loc>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>http://localhost:3000/about</loc>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>
</urlset>
"""

mock_links = [
    {"loc": "http://localhost:3000/", "changefreq": "weekly", "priority": 0.9},
    {"loc": "http://localhost:3000/about", "changefreq": "weekly", "priority": 0.9},
]


def test_generate_xml():
    """Test the generate_xml function."""
    result = generate_xml(mock_links)
    assert result.strip() == mock_xml.strip()


def test_generate_static_sitemaps(app_instance, index_page, about_page):
    """Test the creation of sitemap.xml through generate_static_sitemaps function."""
    pages = {"index": index_page, "about": about_page}
    # remove the sitemap.xml file if it exists.
    sitemap_file_path.unlink(missing_ok=True)
    assert (
        not sitemap_file_path.exists()
    )  # check if the sitemap.xml file does not exist.

    with unittest.mock.patch.object(app_instance, "_pages", pages):
        generate_static_sitemap(mock_links)

        assert sitemap_file_path.exists()  # check if the sitemap.xml file exists.


# Unit test for `serve_sitemap`
@pytest.mark.asyncio
async def test_serve_sitemap(app_instance, index_page, about_page):
    """Test if the correct response is returned when the `serve_sitemap` method is called."""
    pages = {"index": index_page, "about": about_page}

    # because app_instance automatically generates sitemap.xml from empty _pages dictionary, we need to remove this file.
    remove_sitemap_file()

    # mock self._pages to return the dictionary pages.
    with unittest.mock.patch.object(app_instance, "_pages", pages):
        # Call the `serve_sitemap` method
        response: fastapi.Response = await app_instance.serve_sitemap()

        # Assert that the response is of type `Response`
        assert isinstance(response, fastapi.Response)
        # Assert the content type is 'application/xml'
        assert response.media_type == "application/xml"

        # Convert memoryview to bytes explicitly (if it's a memoryview)
        if isinstance(response.body, memoryview):
            response_body = response.body.tobytes().decode("utf-8")
        else:
            # If it's already bytes, decode directly
            response_body = response.body.decode("utf-8")

        # Assert that the XML content is correct (mocked value)
        assert response_body == mock_xml


def test_generate_links_for_sitemap(app_instance, index_page, about_page):
    # Add pages to the app
    pages = {"index": index_page, "about": about_page}

    # mock self._pages to return the dictionary pages.
    with unittest.mock.patch.object(app_instance, "_pages", pages):
        links = generate_links_for_sitemap(app_instance)

        # Assert that the links are generated correctly
        assert links == [
            {"loc": "http://localhost:3000/", "changefreq": "weekly", "priority": 0.9},
            {
                "loc": "http://localhost:3000/about",
                "changefreq": "weekly",
                "priority": 0.9,
            },
        ]
