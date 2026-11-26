"""Sitemap plugin for Reflex."""

import datetime
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import SimpleNamespace
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict
from xml.etree.ElementTree import Element, SubElement, indent, tostring

from reflex_base import constants

from .base import Plugin as PluginBase

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from reflex.app import UnevaluatedPage

TrailingSlashOption = Literal["always", "never", "preserve"]

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
    *,
    config: SitemapLinkConfiguration,
    deploy_url: str | None,
    loc: Location,
    trailing_slash: TrailingSlashOption,
) -> SitemapLink:
    """Set the 'loc' field of the configuration.

    Args:
        config: The configuration dictionary.
        deploy_url: The deployment URL, if any.
        loc: The location to set.
        trailing_slash: Option for handling trailing slashes in URLs.

    Returns:
        A SitemapLink dictionary with the 'loc' field set.
    """
    if deploy_url and not loc.startswith("http://") and not loc.startswith("https://"):
        loc = f"{deploy_url.rstrip('/')}/{loc.lstrip('/')}"
    if trailing_slash == "always" and not loc.endswith("/"):
        loc += "/"
    elif trailing_slash == "never":
        stripped = loc.rstrip("/")
        loc = stripped or loc
    link: SitemapLink = {"loc": loc}
    if (lastmod := config.get("lastmod")) is not None:
        link["lastmod"] = lastmod
    if (changefreq := config.get("changefreq")) is not None:
        link["changefreq"] = changefreq
    if (priority := config.get("priority")) is not None:
        link["priority"] = min(1.0, max(0.0, priority))
    return link


def generate_index_xml(locs: Sequence[Location]) -> str:
    """Generate an XML sitemap index from the URLs of sitemaps.

    Args:
        locs: The absolute URLs of the sitemaps the index lists.

    Returns:
        A pretty-printed XML string representing the sitemap index.
    """
    sitemapindex = Element(
        "sitemapindex", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
    )
    for loc in locs:
        SubElement(SubElement(sitemapindex, "sitemap"), "loc").text = loc
    indent(sitemapindex, "  ")
    return tostring(sitemapindex, encoding="utf-8", xml_declaration=True).decode(
        "utf-8"
    )


def generate_xml(links: Sequence[SitemapLink]) -> str:
    """Generate an XML sitemap from a list of links.

    Args:
        links: A sequence of SitemapLink dictionaries.

    Returns:
        A pretty-printed XML string representing the sitemap.
    """
    urlset = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

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
    indent(urlset, "  ")
    return tostring(urlset, encoding="utf-8", xml_declaration=True).decode("utf-8")


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
    trailing_slash: TrailingSlashOption,
) -> list[SitemapLink]:
    """Generate sitemap links from unevaluated pages.

    Args:
        unevaluated_pages: Sequence of unevaluated pages.
        trailing_slash: Option for handling trailing slashes in URLs.

    Returns:
        A list of SitemapLink dictionaries.
    """
    from reflex_base.config import get_config

    app_config = get_config()
    deploy_url = app_config.frontend_url

    links: list[SitemapLink] = []

    for page in unevaluated_pages:
        sitemap_config: SitemapLinkConfiguration | None = page.context.get(
            "sitemap", {}
        )
        if sitemap_config is None:
            continue

        if is_route_dynamic(page.route) or page.route == "404":
            if not sitemap_config:
                continue

            if (loc := sitemap_config.get("loc")) is None:
                route_message = (
                    "Dynamic route" if is_route_dynamic(page.route) else "Route 404"
                )
                logger.warning(
                    f"{route_message} '{page.route}' does not have a 'loc' in sitemap configuration. Skipping."
                )
                continue

            sitemap_link = configuration_with_loc(
                config=sitemap_config,
                deploy_url=deploy_url,
                loc=loc,
                trailing_slash=trailing_slash,
            )

        elif (loc := sitemap_config.get("loc")) is not None:
            sitemap_link = configuration_with_loc(
                config=sitemap_config,
                deploy_url=deploy_url,
                loc=loc,
                trailing_slash=trailing_slash,
            )

        else:
            loc = page.route if page.route != "index" else "/"
            loc = (
                f"/{app_config.frontend_path.strip('/')}/{loc.lstrip('/')}"
                if app_config.frontend_path
                else f"/{loc.lstrip('/')}"
            )
            sitemap_link = configuration_with_loc(
                config=sitemap_config,
                deploy_url=deploy_url,
                loc=loc,
                trailing_slash=trailing_slash,
            )

        links.append(sitemap_link)
    return links


def sitemap_task(
    unevaluated_pages: Sequence["UnevaluatedPage"],
    trailing_slash: TrailingSlashOption,
    file_path: Path = Constants.FILE_PATH,
) -> tuple[str, str]:
    """Task to generate the sitemap XML file.

    Args:
        unevaluated_pages: Sequence of unevaluated pages.
        trailing_slash: Option for handling trailing slashes in URLs.
        file_path: Where to write the sitemap, relative to the frontend directory.

    Returns:
        A tuple containing the file path and the generated XML content.
    """
    return (
        str(file_path),
        generate_xml(generate_links_for_sitemap(unevaluated_pages, trailing_slash)),
    )


def sitemap_index_task(
    file_path: Path, sitemap_path: str, other_sitemaps: Sequence[Location]
) -> tuple[str, str]:
    """Task to generate a sitemap index listing the app's sitemap and others.

    Args:
        file_path: Where to write the index, relative to the frontend directory.
        sitemap_path: The app's sitemap's path below the frontend's root URL.
        other_sitemaps: More sitemaps, as absolute URLs or paths below deploy_url.

    Returns:
        A tuple containing the file path and the generated XML content.
    """
    from reflex_base.config import get_config

    app_config = get_config()
    sitemap_loc = (
        f"/{app_config.frontend_path.strip('/')}/{sitemap_path}"
        if app_config.frontend_path.strip("/")
        else f"/{sitemap_path}"
    )
    return (
        str(file_path),
        generate_index_xml([
            configuration_with_loc(
                config={},
                deploy_url=app_config.frontend_url,
                loc=loc,
                trailing_slash="preserve",
            )["loc"]
            for loc in (sitemap_loc, *other_sitemaps)
        ]),
    )


def _public_file_path(option: str, path: str) -> str:
    """Normalize a path below the frontend's root URL that names a file in public.

    Args:
        option: The SitemapPlugin option the path comes from, for the error.
        path: The configured path.

    Returns:
        The path without leading, trailing or repeated slashes and dot segments.

    Raises:
        ValueError: If the path names no file or leaves the public directory.
    """
    normalized = PurePosixPath(path.strip("/"))
    # Path honors backslashes and drives on Windows, which PurePosixPath does not see.
    if ".." in normalized.parts or "\\" in path or PureWindowsPath(normalized).drive:
        msg = f"SitemapPlugin {option} must stay in the public directory, got {path!r}."
        raise ValueError(msg)
    if not normalized.name:
        msg = f"SitemapPlugin {option} must name a file."
        raise ValueError(msg)
    return str(normalized)


@dataclass(kw_only=True, frozen=True)
class SitemapPlugin(PluginBase):
    """Sitemap plugin for Reflex.

    Attributes:
        trailing_slash: Option for handling trailing slashes in the sitemap's URLs.
        path: The sitemap's path below the frontend's root URL, where it is written in the build.
        index_path: If set, the path of a sitemap index listing the sitemap followed by index_sitemaps.
        index_sitemaps: More sitemaps for the index, as absolute URLs or paths below deploy_url.
    """

    trailing_slash: TrailingSlashOption = "preserve"

    path: str = Constants.FILE_PATH.name

    index_path: str | None = None

    index_sitemaps: Sequence[Location] = ()

    def __post_init__(self):
        """Normalize the paths, which must name different files.

        Raises:
            ValueError: If index_sitemaps come without index_path, or both paths name the same file.
        """
        object.__setattr__(self, "path", _public_file_path("path", self.path))
        if self.index_path is None:
            if self.index_sitemaps:
                msg = "SitemapPlugin index_sitemaps requires index_path."
                raise ValueError(msg)
            return
        object.__setattr__(
            self, "index_path", _public_file_path("index_path", self.index_path)
        )
        if self.index_path == self.path:
            msg = (
                "SitemapPlugin index_path must name a file other than the sitemap "
                f"{self.path!r}, got {self.index_path!r}."
            )
            raise ValueError(msg)

    @property
    def file_path(self) -> Path:
        """Where the sitemap is written, relative to the frontend directory.

        Returns:
            The sitemap's path in the frontend's public directory.
        """
        return Path(constants.Dirs.PUBLIC) / self.path

    def pre_compile(self, **context):
        """Generate the sitemap XML file, and the index if configured, before compilation.

        Args:
            context: The context for the plugin.
        """
        unevaluated_pages = context.get("unevaluated_pages", [])
        context["add_save_task"](
            sitemap_task, unevaluated_pages, self.trailing_slash, self.file_path
        )
        if self.index_path is not None:
            context["add_save_task"](
                sitemap_index_task,
                Path(constants.Dirs.PUBLIC) / self.index_path,
                self.path,
                self.index_sitemaps,
            )


Plugin = SitemapPlugin
