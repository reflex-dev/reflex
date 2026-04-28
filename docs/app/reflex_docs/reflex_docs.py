"""The main Reflex website."""

import os
import sys

import reflex as rx
import reflex_enterprise as rxe
from reflex_site_shared import styles
from reflex_site_shared.backend.status import monitor_checkly_status
from reflex_site_shared.constants import REFLEX_ASSETS_CDN
from reflex_site_shared.meta.meta import favicons_links, to_cdn_image_url
from reflex_site_shared.telemetry import get_pixel_website_trackers

from reflex_docs.pages import page404, routes
from reflex_docs.whitelist import _check_whitelisted_path

# This number discovered by trial and error on Windows 11 w/ Node 18, any
# higher and the prod build fails with EMFILE error.
WINDOWS_MAX_ROUTES = int(os.environ.get("REFLEX_WEB_WINDOWS_MAX_ROUTES", "100"))

# Create the app.
app = rxe.App(
    style=styles.BASE_STYLE,
    stylesheets=styles.STYLESHEETS,
    app_wraps={},
    theme=rx.theme(
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

        page_args = {
            "component": route.component,
            "route": route.path,
            "title": route.title,
            "image": image_url,
            "meta": [
                {"name": "theme-color", "content": route.background_color},
            ],
            "on_load": route.on_load,
        }

        # Add the description only if it is not None
        if route.description is not None:
            page_args["description"] = route.description
        # Add the extra meta data only if it is not None
        if route.meta is not None:
            page_args["meta"].extend(route.meta)

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
