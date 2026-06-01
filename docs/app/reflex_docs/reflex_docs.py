"""The main Reflex website."""

import os
import sys

import reflex as rx
import reflex_enterprise as rxe
from reflex_site_shared import styles
from reflex_site_shared.backend.status import monitor_checkly_status
from reflex_site_shared.constants import REFLEX_ASSETS_CDN
from reflex_site_shared.meta.meta import (
    ONE_LINE_DESCRIPTION,
    create_meta_tags,
    favicons_links,
    to_cdn_image_url,
)
from reflex_site_shared.telemetry import get_pixel_website_trackers
from reflex_site_shared.utils.url import public_url

from reflex_docs.pages import page404, routes
from reflex_docs.templates.docpage.docpage import DOCS_PROD_BASE
from reflex_docs.whitelist import _check_whitelisted_path


def _seo_meta_tags(
    title: str, description: str, image: str, canonical_url: str
) -> list:
    """Build the per-page SEO meta tag set, deduped against framework output.

    Reflex's ``add_page`` already emits ``<meta name="description">`` (from
    its ``description=`` arg) and ``<meta property="og:image">`` (from its
    ``image=`` arg). We strip those entries from ``create_meta_tags`` to
    avoid duplicate tags in the rendered ``<head>``.
    """
    tags = create_meta_tags(
        title=title, description=description, image=image, url=canonical_url
    )
    return [
        t
        for t in tags
        if not (
            isinstance(t, dict)
            and (t.get("name") == "description" or t.get("property") == "og:image")
        )
    ]


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

# Add the pages to the app.
_DEFAULT_PREVIEW = f"{REFLEX_ASSETS_CDN}previews/index_preview.webp"
for route in routes:
    # print(f"Adding route: {route}")
    if _check_whitelisted_path(route.path):
        image_url = (
            to_cdn_image_url(route.image) if route.image else None
        ) or _DEFAULT_PREVIEW
        page_description = route.description or ONE_LINE_DESCRIPTION

        meta_tags: list = [
            {"name": "theme-color", "content": route.background_color},
        ]
        if isinstance(route.title, str):
            meta_tags.extend(
                _seo_meta_tags(
                    title=route.title,
                    description=page_description,
                    image=image_url,
                    canonical_url=public_url(route.path, fallback_base=DOCS_PROD_BASE),
                )
            )
        if route.meta is not None:
            meta_tags.extend(route.meta)

        app.add_page(
            component=route.component,
            route=route.path,
            title=route.title,
            description=page_description,
            image=image_url,
            meta=meta_tags,
            on_load=route.on_load,
        )

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
