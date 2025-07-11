"""Sitemap plugin for Reflex."""

import datetime
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Literal, TypedDict
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from typing_extensions import NotRequired

from reflex import constants

from .base import Plugin as PluginBase

if TYPE_CHECKING:
    from reflex.app import UnevaluatedPage

Location = str
LastModified = datetime.datetime
ChangeFrequency = Literal[
    "always", "hourly", "daily", "weekly", "monthly", "yearly", "never"
]
Priority = float


class SitemapLink(TypedDict):
    """A link in the sitemap."""

    loc: Location
    lastmod: NotRequired[LastModified]
    changefreq: NotRequired[ChangeFrequency]
    priority: NotRequired[Priority]


class SitemapLinkConfiguration(TypedDict):
    """Configuration for a sitemap link."""

    loc: NotRequired[Location]
    lastmod: NotRequired[LastModified]
    changefreq: NotRequired[ChangeFrequency]
    priority: NotRequired[Priority]


class Constants(SimpleNamespace):
    """Sitemap constants."""

    FILE_PATH: Path = Path(constants.Dirs.PUBLIC) / "sitemap.xml"


def configuration_with_loc(
    *, config: SitemapLinkConfiguration, deploy_url: str | None, loc: Location
) -> SitemapLink:
    """Set the 'loc' field of the configuration.

    Args:
        config: The configuration dictionary.
        deploy_url: The deployment URL, if any.
        loc: The location to set.

    Returns:
        A SitemapLink dictionary with the 'loc' field set.
    """
    if deploy_url and not loc.startswith("http://") and not loc.startswith("https://"):
        loc = f"{deploy_url.rstrip('/')}/{loc.lstrip('/')}"
    link: SitemapLink = {"loc": loc}
    if (lastmod := config.get("lastmod")) is not None:
        link["lastmod"] = lastmod
    if (changefreq := config.get("changefreq")) is not None:
        link["changefreq"] = changefreq
    if (priority := config.get("priority")) is not None:
        link["priority"] = min(1.0, max(0.0, priority))
    return link


def generate_xml(links: Sequence[SitemapLink]) -> str:
    """Generate an XML sitemap from a list of links.

    Args:
        links: A sequence of SitemapLink dictionaries.

    Returns:
        A pretty-printed XML string representing the sitemap.
    """
    urlset = Element("urlset", xmlns="https://www.sitemaps.org/schemas/sitemap/0.9")

    for link in links:
        url = SubElement(urlset, "url")

        loc_element = SubElement(url, "loc")
        loc_element.text = link["loc"]

        if (changefreq := link.get("changefreq")) is not None:
            changefreq_element = SubElement(url, "changefreq")
            changefreq_element.text = changefreq

        if (lastmod := link.get("lastmod")) is not None:
            lastmod_element = SubElement(url, "lastmod")
            if isinstance(lastmod, datetime.datetime):
                lastmod = lastmod.isoformat()
            lastmod_element.text = lastmod

        if (priority := link.get("priority")) is not None:
            priority_element = SubElement(url, "priority")
            priority_element.text = str(priority)

    rough_string = tostring(urlset, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def is_route_dynamic(route: str) -> bool:
    """Check if a route is dynamic.

    Args:
        route: The route to check.

    Returns:
        True if the route is dynamic, False otherwise.
    """
    return "[" in route and "]" in route


def generate_links_for_sitemap(
    unevaluated_pages: Sequence["UnevaluatedPage"],
) -> list[SitemapLink]:
    """Generate sitemap links from unevaluated pages.

    Args:
        unevaluated_pages: Sequence of unevaluated pages.

    Returns:
        A list of SitemapLink dictionaries.
    """
    from reflex.config import get_config
    from reflex.utils import console

    deploy_url = get_config().deploy_url

    links: list[SitemapLink] = []

    for page in unevaluated_pages:
        sitemap_config: SitemapLinkConfiguration = page.context.get("sitemap", {})

        if is_route_dynamic(page.route) or page.route == "404":
            if not sitemap_config:
                continue

            if (loc := sitemap_config.get("loc")) is None:
                route_message = (
                    "Dynamic route" if is_route_dynamic(page.route) else "Route 404"
                )
                console.warn(
                    route_message
                    + f" '{page.route}' does not have a 'loc' in sitemap configuration. Skipping."
                )
                continue

            sitemap_link = configuration_with_loc(
                config=sitemap_config, deploy_url=deploy_url, loc=loc
            )

        elif (loc := sitemap_config.get("loc")) is not None:
            sitemap_link = configuration_with_loc(
                config=sitemap_config, deploy_url=deploy_url, loc=loc
            )

        else:
            loc = page.route if page.route != "index" else "/"
            if not loc.startswith("/"):
                loc = "/" + loc
            sitemap_link = configuration_with_loc(
                config=sitemap_config, deploy_url=deploy_url, loc=loc
            )

        links.append(sitemap_link)
    return links


def sitemap_task(unevaluated_pages: Sequence["UnevaluatedPage"]) -> tuple[str, str]:
    """Task to generate the sitemap XML file.

    Args:
        unevaluated_pages: Sequence of unevaluated pages.

    Returns:
        A tuple containing the file path and the generated XML content.
    """
    return (
        str(Constants.FILE_PATH),
        generate_xml(generate_links_for_sitemap(unevaluated_pages)),
    )


class SitemapPlugin(PluginBase):
    """Sitemap plugin for Reflex."""

    def pre_compile(self, **context):
        """Generate the sitemap XML file before compilation.

        Args:
            context: The context for the plugin.
        """
        unevaluated_pages = context.get("unevaluated_pages", [])
        context["add_save_task"](sitemap_task, unevaluated_pages)


Plugin = SitemapPlugin
