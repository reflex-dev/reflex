import unittest.mock
from pathlib import Path

import pytest

import reflex as rx
from reflex import Component, constants
from reflex.app import App
from reflex.sitemap import (
    generate_links_for_sitemap,
    generate_static_sitemap,
    generate_xml,
)
from reflex.utils import prerequisites

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


class Page(Component):
    """A simple Page component."""

    def __init__(self, text, **kwargs):
        """Initialize the Page component."""
        super().__init__(**kwargs)
        self.text = text

    def render(self):
        """Render the Page component."""
        return rx.box(self.text)


@pytest.fixture
def index_page() -> Page:
    """Fixture that returns an IndexPage instance.

    Returns:
        An instance of IndexPage.
    """
    return Page(text="Index")


@pytest.fixture
def about_page() -> Page:
    """Fixture that returns an AboutPage instance.

    Returns:
        An instance of AboutPage.
    """
    return Page(text="About")


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
    """Test if the generated sitemap file is currently stored in static website or not."""
    pages = {"index": index_page, "about": about_page}
    # remove the sitemap.xml file if it exists.
    sitemap_file_path.unlink(missing_ok=True)
    assert (
        not sitemap_file_path.exists()
    )  # check if the sitemap.xml file does not exist.

    with unittest.mock.patch.object(app_instance, "_pages", pages):
        generate_static_sitemap(mock_links)

        assert sitemap_file_path.exists()  # check if the sitemap.xml file exists.


def test_generate_links_for_sitemap():
    """Test if the links are generated correctly for the sitemap from the sitemap config file when no deploy url is
    given.
    """
    sitemap_properties = {
        "index": {"priority": 0.9, "changefreq": "weekly"},
        "about": {"priority": 0.9, "changefreq": "weekly"},
    }

    links = generate_links_for_sitemap(sitemap_properties)

    # Assert that the links are generated correctly
    assert links == [
        {"loc": "http://localhost:3000/", "changefreq": "weekly", "priority": 0.9},
        {
            "loc": "http://localhost:3000/about",
            "changefreq": "weekly",
            "priority": 0.9,
        },
    ]


def test_generate_links_for_sitemap_deploy_url():
    """Test if the links are generated correctly for the sitemap from the sitemap config file when a deploy url is
    given.
    """
    sitemap_properties = {
        "index": {"priority": 0.9, "changefreq": "weekly"},
        "about": {"priority": 0.9, "changefreq": "weekly"},
    }

    with unittest.mock.patch("reflex.sitemap.get_config") as mock_get_config:
        mock_get_config().deploy_url = "http://www.google.com"

        links = generate_links_for_sitemap(sitemap_properties)

        # Assert that the links are generated correctly
        assert links == [
            {"loc": "http://www.google.com/", "changefreq": "weekly", "priority": 0.9},
            {
                "loc": "http://www.google.com/about",
                "changefreq": "weekly",
                "priority": 0.9,
            },
        ]
