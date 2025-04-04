"""This module contains functions to generate and manage the sitemap.xml file."""

from pathlib import Path
from typing import Dict, List
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from reflex import constants
from reflex.config import get_config
from reflex.utils import prerequisites

# _static folder in the .web directory containing the sitemap.xml file.
_sitemap_folder_path: Path = (
    Path.cwd() / prerequisites.get_web_dir() / constants.Dirs.STATIC
)

# sitemap file path
_sitemap_file_path: Path = _sitemap_folder_path / "sitemap.xml"


def check_sitemap_file_exists() -> bool:
    """Check if the sitemap file exists.

    Returns:
        bool: True if the sitemap file exists in the .web/_static folder.
    """
    return _sitemap_folder_path.exists() & _sitemap_file_path.exists()


def read_sitemap_file() -> str:
    """Read the sitemap file.

    Returns:
        str: The contents of the sitemap file.
    """
    with _sitemap_file_path.open("r") as f:
        return f.read()


def generate_xml(links: List[Dict[str, str]]) -> str:
    """Generate an XML sitemap from a list of links.

    Args:
        links (List[Dict[str, Any]]): A list of dictionaries where each dictionary contains
            'loc' (URL of the page), 'changefreq' (frequency of changes), and 'priority' (priority of the page).

    Returns:
        str: A pretty-printed XML string representing the sitemap.
    """
    urlset = Element("urlset", xmlns="https://www.sitemaps.org/schemas/sitemap/0.9")
    for link in links:
        url = SubElement(urlset, "url")
        loc = SubElement(url, "loc")
        loc.text = link["loc"]
        changefreq = SubElement(url, "changefreq")
        changefreq.text = link["changefreq"]
        priority = SubElement(url, "priority")
        priority.text = str(link["priority"])
    rough_string = tostring(urlset, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def generate_sitemaps(sitemap_config: Dict[str, Dict[str, str]]) -> None:
    """Generate the sitemap.xml file.

    This function generates the sitemap.xml file by crawling through the available pages in the app and generating a list
    of links with their respective sitemap properties such as location (URL), change frequency, and priority. Dynamic
    routes and the 404 page are excluded from the sitemap.

    Args:
        sitemap_config: A dictionary containing the sitemap properties for each route.
    """
    links = generate_links_for_sitemap(sitemap_config)
    generate_static_sitemap(links)


def generate_links_for_sitemap(
    sitemap_config: Dict[str, Dict[str, str]],
) -> List[dict[str, str]]:
    """Generate a list of links for which sitemaps are generated.

    This function loops through sitemap_config and generates a list of links with their respective sitemap properties
    such as location (URL), change frequency, and priority. Dynamic routes and the 404 page are excluded from the
    sitemap.

    Args:
        sitemap_config: A dictionary containing the sitemap properties for each route.

    Returns:
        List: A list of dictionaries where each dictionary contains the 'loc' (URL of the page), 'priority' and
        'changefreq' of each route.
    """
    links = []

    # find link of pages that are not dynamically created.
    for route in sitemap_config:
        # Ignore dynamic routes and 404
        if ("[" in route and "]" in route) or route == "404":
            continue

        sitemap_changefreq = sitemap_config[route]["changefreq"]
        sitemap_priority = sitemap_config[route]["priority"]

        # Handle the index route
        if route == "index":
            route = "/"

        if not route.startswith("/"):
            route = f"/{route}"

        if (
            sitemap_priority == constants.DefaultPage.SITEMAP_PRIORITY
        ):  # indicates that user didn't set priority
            depth = route.count("/")
            sitemap_priority = max(0.5, 1.0 - (depth * 0.1))

        deploy_url = get_config().deploy_url  # pick domain url from the config file.

        links.append(
            {
                "loc": f"{deploy_url}{route}",
                "changefreq": sitemap_changefreq,
                "priority": sitemap_priority,
            }
        )
    return links


def generate_static_sitemap(links: List[Dict[str, str]]) -> None:
    """Generates the sitemaps for the pages stored in _pages. Store it in sitemap.xml.

    This method is called from two methods:
     1. Every time the web app is deployed onto the server.
     2. When the user (or crawler) requests for the sitemap.xml file.

    Args:
        links: The list of urls for which the sitemap is to be generated.
    """
    sitemap = generate_xml(links)
    Path(_sitemap_folder_path).mkdir(parents=True, exist_ok=True)

    # this method is only called when old sitemap.xml is not retrieved. So we can safely replace an already existing xml
    # file.
    with _sitemap_file_path.open("w") as f:
        f.write(sitemap)
