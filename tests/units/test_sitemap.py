import unittest.mock
from pathlib import Path

import pytest

import reflex as rx
from reflex import constants
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
    """Fixture to create an instance of the app.

    Returns:
        An instance of the App class.
    """
    app = App()
    return app


def page(text: str):
    """A simple page component for testing.

    Args:
        text: The text to display on the page.

    Returns:
        A Reflex component with the given text.
    """
    return rx.box(text)


@pytest.fixture
def index_page():
    """Fixture that returns an IndexPage instance.

    Returns:
        An instance of IndexPage.
    """
    return page(text="Index")


@pytest.fixture
def about_page():
    """Fixture that returns an AboutPage instance.

    Returns:
        An instance of AboutPage.
    """
    return page(text="About")


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
    """Test if the generated sitemap file is currently stored in static website or not.

    Args:
        app_instance: The app instance.
        index_page: The index page fixture.
        about_page: The about page fixture.
    """
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
    links = generate_links_for_sitemap(
        {
            "index": {"priority": 0.9, "changefreq": "weekly"},
            "about": {"priority": 0.9, "changefreq": "weekly"},
        }
    )

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
    with unittest.mock.patch("reflex.sitemap.get_config") as mock_get_config:
        mock_get_config().deploy_url = "http://www.google.com"

        links = generate_links_for_sitemap(
            {
                "index": {"priority": 0.9, "changefreq": "weekly"},
                "about": {"priority": 0.9, "changefreq": "weekly"},
            }
        )

        # Assert that the links are generated correctly
        assert links == [
            {"loc": "http://www.google.com/", "changefreq": "weekly", "priority": 0.9},
            {
                "loc": "http://www.google.com/about",
                "changefreq": "weekly",
                "priority": 0.9,
            },
        ]
