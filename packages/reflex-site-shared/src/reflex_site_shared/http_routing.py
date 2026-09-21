"""Export app-owned Caddy rules for permanent redirects and real missing-page 404s."""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from reflex_base.config import get_config
from reflex_base.constants import Dirs
from reflex_base.plugins import Plugin

if TYPE_CHECKING:
    from reflex.app import UnevaluatedPage


EXPORT_DIRECTORY = "__http_routing__"


def _path(value: str) -> str:
    """Validate a literal public path and remove its trailing slash.

    Args:
        value: An absolute path without query or fragment.

    Returns:
        The normalized path.

    Raises:
        ValueError: The path is not safe to embed as a literal Caddy matcher.
    """
    if (
        not re.fullmatch(r"/[a-zA-Z0-9_./%~-]*", value)
        or "//" in value
        or ".." in value.split("/")
    ):
        message = f"Expected a literal absolute route: {value!r}"
        raise ValueError(message)
    return value.rstrip("/") or "/"


def render_routing(
    pages: Sequence["UnevaluatedPage"],
    redirects: Mapping[str, str],
    *,
    frontend_path: str = "",
    excluded_dynamic_routes: Sequence[str] = (),
) -> tuple[str, str]:
    """Render permanent redirects and an exact inventory from registered pages.

    Dynamic catalog routes must be explicitly excluded and registered as concrete
    pages by the app (for example, its fetched template catalog). Never translate
    a dynamic parameter into a wildcard that silently accepts missing objects.

    Args:
        pages: The pages supplied by Reflex's pre-compile hook, including noindex pages.
        redirects: App-owned public source URLs mapped to public destinations.
        frontend_path: Public mount prepended to registered page routes.
        excluded_dynamic_routes: App-local dynamic routes replaced by concrete pages.

    Returns:
        Caddy redirect rules and the page-inventory guard.

    Raises:
        ValueError: Routes are unsafe, an inventory is empty, or redirects cycle or
            point to unregistered local destinations.
    """
    prefix = frontend_path.strip("/")
    valid = set()
    for page in pages:
        route = page.route.strip("/")
        if "[" in route:
            if route not in excluded_dynamic_routes:
                message = f"Uninventoried dynamic route: {route}"
                raise ValueError(message)
            continue
        if route == "404":
            continue
        if route == "index":
            route = ""
        valid.add(_path("/" + "/".join(part for part in (prefix, route) if part)))
    if not valid:
        message = "Refusing to export an empty route inventory"
        raise ValueError(message)
    aliases = {_path(source): target for source, target in redirects.items()}
    rules = ["# Generated from app redirects; do not edit."]
    for number, (source, target) in enumerate(sorted(aliases.items())):
        visited = {source}
        fragment = ""
        while True:
            parsed = urlsplit(target)
            if parsed.query or any(char in target for char in '{}"\\\n\r\t '):
                message = f"Unsupported redirect destination: {target!r}"
                raise ValueError(message)
            # A later explicit fragment replaces an earlier one in a chain.
            fragment = parsed.fragment or fragment
            if parsed.scheme or parsed.netloc:
                if parsed.scheme not in ("http", "https") or not parsed.netloc:
                    message = f"Invalid external redirect: {target!r}"
                    raise ValueError(message)
                destination = target.split("#", 1)[0]
                break
            path = _path(parsed.path)
            if path in visited:
                message = f"Redirect cycle at {path}"
                raise ValueError(message)
            visited.add(path)
            if path in aliases:
                target = aliases[path]
                continue
            if path not in valid:
                message = f"Redirect target is not a registered page: {path}"
                raise ValueError(message)
            destination = path.rstrip("/") + "/"
            break
        location = destination + "{querySuffix}" + ("#" + fragment if fragment else "")
        sources = [source] if source == "/" else [source, source + "/"]
        rules.extend([
            f"@legacy{number} {{",
            "    method GET HEAD",
            "    path " + " ".join(json.dumps(path) for path in sources),
            "}",
            f"redir @legacy{number} {json.dumps(location)} 301",
        ])
    # App redirects need no HTML export: they are answered before page serving.
    inventory = "\n".join([
        "# Generated from registered pages; no sitemap filtering or wildcard inference.",
        "@unknownPage {",
        "    not path " + " ".join(json.dumps(path) for path in sorted(valid)),
        "}",
        "error @unknownPage 404",
        "",
    ])
    return "\n".join(rules) + "\n", inventory


def _routing_task(
    pages: Sequence["UnevaluatedPage"],
    redirects: Mapping[str, str],
    excluded_dynamic_routes: Sequence[str],
) -> list[tuple[str, str]]:
    """Generate build assets from the current registration snapshot.

    Args:
        pages: Registered pages.
        redirects: Public redirect mappings.
        excluded_dynamic_routes: Dynamic routes covered by concrete registrations.

    Returns:
        Files written by the compiler before the frontend build.
    """
    redirects_text, inventory = render_routing(
        pages,
        redirects,
        frontend_path=get_config().frontend_path or "",
        excluded_dynamic_routes=excluded_dynamic_routes,
    )
    directory = Path(Dirs.PUBLIC) / EXPORT_DIRECTORY
    return [
        (str(directory / "app-redirects.caddy"), redirects_text),
        (str(directory / "app-pages.caddy"), inventory),
    ]


@dataclass(kw_only=True)
class HttpRoutingPlugin(Plugin):
    """Generate Caddy routing assets; the image must move them outside its web root."""

    redirects: Mapping[str, str] = field(default_factory=dict)
    excluded_dynamic_routes: Sequence[str] = ()

    def pre_compile(self, **context) -> None:
        """Export exact routes, including pages intentionally omitted from sitemaps.

        Args:
            context: Reflex's pre-compile context.
        """
        context["add_save_task"](
            _routing_task,
            context["unevaluated_pages"],
            self.redirects,
            self.excluded_dynamic_routes,
        )
