"""The main Reflex website."""

import os
import sys

import reflex as rx
import reflex_enterprise as rxe
from reflex_site_shared import styles
from reflex_site_shared.backend.status import monitor_checkly_status
from reflex_site_shared.constants import REFLEX_ASSETS_CDN, REFLEX_DOMAIN_URL
from reflex_site_shared.meta.meta import (
    ONE_LINE_DESCRIPTION,
    create_meta_tags,
    favicons_links,
    to_cdn_image_url,
)
from reflex_site_shared.telemetry import get_pixel_website_trackers

from reflex_docs.pages import page404, routes
from reflex_docs.whitelist import _check_whitelisted_path

# This number discovered by trial and error on Windows 11 w/ Node 18, any
# higher and the prod build fails with EMFILE error.
WINDOWS_MAX_ROUTES = int(os.environ.get("REFLEX_WEB_WINDOWS_MAX_ROUTES", "100"))
LLMS_TXT_PATH = "/llms.txt"


def _llms_txt_directive() -> rx.Component:
    """Return the agent-facing docs index directive."""
    return rx.el.blockquote(
        rx.el.span("For AI agents: the complete documentation index is at "),
        rx.el.a("llms.txt", href=LLMS_TXT_PATH),
        rx.el.span(
            ". Markdown versions are available by appending .md or sending "
            "Accept: text/markdown."
        ),
        class_name="sr-only",
    )


# Create the app.
app = rxe.App(
    style=styles.BASE_STYLE,
    stylesheets=styles.STYLESHEETS,
    app_wraps={},
    theme=rx.theme(
        _llms_txt_directive(),
        has_background=True,
        radius="large",
        accent_color="violet",
    ),
    head_components=get_pixel_website_trackers()
    + favicons_links()
    + [
        rx.el.link(
            rel="preload",
            href=rx.asset("fonts/instrument-sans.woff2"),
            custom_attrs={"as": "font"},
            type="font/woff2",
            cross_origin="anonymous",
        ),
        rx.el.link(
            rel="preload",
            href=rx.asset("fonts/jetbrains-mono.woff2"),
            custom_attrs={"as": "font"},
            type="font/woff2",
            cross_origin="anonymous",
        ),
    ],
)

app.register_lifespan_task(monitor_checkly_status)

# XXX: The app is TOO BIG to build on Windows, so explicitly disallow it except for testing
if sys.platform == "win32":
    if not os.environ.get("REFLEX_WEB_WINDOWS_OVERRIDE"):
        raise RuntimeError(
            "reflex-web cannot be built on Windows due to EMFILE error. To build a "
            "subset of pages for testing, set environment variable REFLEX_WEB_WINDOWS_OVERRIDE."
        )
    routes = routes[:WINDOWS_MAX_ROUTES]

# Routes are registered without the frontend path prefix; it is mounted at
# runtime (frontend_path="/docs"), so the public URL needs it prepended.
_FRONTEND_PATH = (rx.config.get_config().frontend_path or "").rstrip("/")


def _canonical_url(path: str) -> str:
    """Build the absolute, trailing-slash canonical URL for a route path.

    Args:
        path: The route path (e.g. ``/state/overview/``), without the
            frontend path prefix.

    Returns:
        The absolute canonical URL (e.g. ``https://reflex.dev/docs/state/overview/``).
    """
    # Some routes are registered with a leading-slash-less path (e.g.
    # docpage("overview/", ...)); normalize so the prefix join can't produce
    # "/docsoverview/" instead of "/docs/overview/".
    if not path.startswith("/"):
        path = "/" + path
    url = REFLEX_DOMAIN_URL.rstrip("/") + _FRONTEND_PATH + path
    return url if url.endswith("/") else url + "/"


# Add the pages to the app.
for route in routes:
    # print(f"Adding route: {route}")
    if _check_whitelisted_path(route.path):
        # Normalize image to CDN URL when it's a relative path
        image_url = (
            f"{REFLEX_ASSETS_CDN}previews/index_preview.webp"
            if route.image is None
            else to_cdn_image_url(route.image)
            or f"{REFLEX_ASSETS_CDN}previews/index_preview.webp"
        )

        # Build a complete, page-specific set of SEO meta tags (description,
        # Open Graph, Twitter card, canonical) from the route's own title and
        # description. Emitting these via `meta` — rather than add_page's
        # `description`/`image` kwargs — prevents Reflex from emitting a second
        # `description`/`og:image` tag (the "multiple meta description tags"
        # issue), makes OG/Twitter values page-specific (docs pages previously
        # had no description/og/twitter/canonical at all), and adds the missing
        # canonical link.
        # Prefer an explicit SEO title for the HTML <title>/meta; the sidebar
        # and nav keep using the shorter `route.title`. This lets API-reference
        # and CLI-reference pages emit a descriptive, >=30 char <title> while
        # their sidebar label stays short (e.g. "App", "Deploy").
        head_title = route.seo_title or route.title
        if isinstance(head_title, str) and "[" not in route.path:
            canonical = _canonical_url(route.path)
            meta = create_meta_tags(
                title=head_title,
                description=route.description or ONE_LINE_DESCRIPTION,
                image=image_url,
                url=canonical,
            )
            # Preserve any extra page-declared tags (e.g. robots) not already
            # covered, without re-introducing duplicate description/OG/Twitter.
            if route.meta:
                seen = {
                    m.get("name") or m.get("property")
                    for m in meta
                    if isinstance(m, dict)
                }
                meta.extend(
                    m
                    for m in route.meta
                    if isinstance(m, dict)
                    and (m.get("name") or m.get("property")) not in seen
                )
        else:
            # Dynamic ([...]) or Var-titled routes: a static canonical/title
            # can't be emitted, so keep any page-provided meta as-is.
            canonical = None
            meta = list(route.meta) if route.meta is not None else []
        meta.append({"name": "theme-color", "content": route.background_color})

        # Reflex's compiler always renders exactly one og:image from add_page's
        # `image` kwarg (defaulting to the favicon). Pass the real preview as
        # `image` and drop og:image from the meta list, so the page has a single
        # og:image (the preview) rather than the favicon default + the preview.
        meta = [
            m
            for m in meta
            if not (isinstance(m, dict) and m.get("property") == "og:image")
        ]

        page_args = {
            "component": route.component,
            "route": route.path,
            "title": head_title,
            "image": image_url,
            "meta": meta,
            "on_load": route.on_load,
        }

        # Emit the trailing-slash canonical URL as the sitemap <loc> so the
        # sitemap entry matches the canonical link (and the 200 page). The
        # default would use the route without a trailing slash, which
        # 301-redirects — surfacing as "3XX redirect in sitemap" /
        # "non-canonical page in sitemap".
        if canonical is not None:
            page_args["context"] = {"sitemap": {"loc": canonical}}

        # Call add_page with the dynamically constructed arguments
        app.add_page(**page_args)

# Add redirects.
redirects = [
    (route.path.replace("/ai/", "/ai-builder/", 1), route.path)
    for route in routes
    if route.path.startswith("/ai/")
]


def _redirect_page():
    return rx.fragment(
        rx.el.h1("Redirecting", class_name="sr-only"),
    )


for source, target in redirects:
    if _check_whitelisted_path(target):
        app.add_page(
            _redirect_page,
            route=source,
            title="Redirecting - Reflex Web Framework",
            description="You are being redirected to the requested page.",
            on_load=rx.redirect(target),
            context={"sitemap": None},
        )

app.add_page(page404.component, route=page404.path)
