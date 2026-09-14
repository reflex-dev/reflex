"""Open footer layout for the documentation landing page."""

from datetime import datetime
from typing import Literal

import reflex as rx
from reflex.style import color_mode, set_color_mode
from reflex_site_shared.backend.signup import IndexState
from reflex_site_shared.backend.status import StatusState
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.components.server_status import server_status
from reflex_site_shared.constants import (
    CHANGELOG_URL,
    DISCORD_URL,
    GITHUB_ORG_URL,
    LINKEDIN_URL,
    REFLEX_ASSETS_CDN,
    REFLEX_BUILD_URL,
    REFLEX_URL,
    TWITTER_URL,
)

_FOOTER_LINKS = (
    (
        "Product",
        (
            ("AI Builder", REFLEX_BUILD_URL),
            ("Agent Toolkit", "/docs/ai/integrations/agent-toolkit/"),
            ("Enterprise", "/docs/enterprise/overview/"),
            ("App Management", "/hosting/"),
            ("Pricing", "/pricing/"),
        ),
    ),
    (
        "Solutions",
        (
            ("Enterprise", "/use-cases/"),
            ("Finance", "/use-cases/finance/"),
            ("Healthcare", "/use-cases/healthcare/"),
            ("Consulting", "/use-cases/consulting/"),
            ("Government", "/use-cases/government/"),
        ),
    ),
    (
        "Resources",
        (
            ("Blog", "/blog/"),
            ("Templates", "/templates/"),
            ("Integrations", "/docs/ai/integrations/overview/"),
            ("FAQ", "/faq/"),
        ),
    ),
    (
        "Developers",
        (
            ("Documentation", "/docs/"),
            ("Changelog", CHANGELOG_URL),
            ("Common Errors", "/errors/"),
        ),
    ),
    (
        "Migration",
        (
            ("From No-Code", "/migration/no-code/"),
            ("From Low-Code", "/migration/low-code/"),
            ("From Other Frameworks", "/migration/other-frameworks/"),
            ("From Other AI Tools", "/migration/other-ai-tools/"),
        ),
    ),
    (
        "Company",
        (
            ("About", "/about/"),
            ("Careers", "https://www.ycombinator.com/companies/reflex/jobs"),
            ("Privacy Policy", "https://build.reflex.dev/privacy-policy"),
            ("Terms of Service", "https://build.reflex.dev/terms-of-use"),
        ),
    ),
)

_FOCUS = (
    "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
)


def _newsletter() -> rx.Component:
    """Keep the existing signup handler behind a labeled, compact email form."""
    return rx.el.div(
        rx.cond(
            IndexState.signed_up,
            rx.el.div(
                rx.el.p("Thanks for subscribing!", role="status"),
                button(
                    "Sign up for another email",
                    variant="outline",
                    size="sm",
                    on_click=IndexState.signup_for_another_user,
                ),
                class_name="flex flex-col items-start gap-3 text-sm text-foreground",
            ),
            rx.el.div(
                rx.el.label(
                    "Stay up to date with Reflex",
                    html_for="docs-newsletter-email",
                    class_name="text-sm font-book text-foreground",
                ),
                rx.el.form(
                    rx.el.input(
                        id="docs-newsletter-email",
                        name="input_email",
                        type="email",
                        auto_complete="email",
                        placeholder="Your email address",
                        required=True,
                        class_name=f"h-11 min-w-0 flex-1 rounded-full border border-border bg-background px-4 text-sm text-foreground placeholder:text-subtle-foreground {_FOCUS}",
                    ),
                    button("Get Updates", type="submit", variant="primary", size="md"),
                    on_submit=IndexState.signup,
                    class_name="mt-3 flex flex-wrap items-center gap-2",
                ),
            ),
        ),
        class_name="w-full max-w-md",
    )


def _theme_toggle() -> rx.Component:
    """Offer the three existing color modes in a flat segmented control."""
    modes: tuple[tuple[Literal["system", "light", "dark"], str], ...] = (
        ("system", "computer_footer"),
        ("light", "sun_footer"),
        ("dark", "moon_footer"),
    )
    return rx.el.div(
        *[
            rx.el.button(
                get_icon(icon, class_name="size-4"),
                on_click=set_color_mode(mode),
                type="button",
                aria_label=f"Toggle {mode} color mode",
                aria_pressed=color_mode == mode,
                class_name=rx.cond(
                    color_mode == mode,
                    "bg-foreground text-background",
                    "text-muted-foreground hover:bg-accent hover:text-foreground",
                )
                + f" flex size-8 items-center justify-center rounded-full transition-colors {_FOCUS}",
            )
            for mode, icon in modes
        ],
        role="group",
        aria_label="Color mode",
        class_name="flex w-fit items-center gap-0.5 rounded-full border border-border p-0.5",
    )


def _link_column(heading: str, links: tuple[tuple[str, str], ...]) -> rx.Component:
    """Keep root-site destinations outside the docs router basename."""
    return rx.el.nav(
        rx.el.h2(heading, class_name="mb-3 text-xs font-book text-muted-foreground"),
        *[
            rx.el.elements.a(
                text,
                href=href,
                target="_blank" if not href.startswith("/") else None,
                rel="noopener noreferrer" if not href.startswith("/") else None,
                class_name=f"w-fit rounded-sm text-sm font-book leading-6 text-foreground transition-colors hover:text-muted-foreground {_FOCUS}",
            )
            for text, href in links
        ],
        aria_label=f"{heading} footer links",
        class_name="flex min-w-0 flex-col gap-2",
    )


def editorial_footer() -> rx.Component:
    """Render the newsletter, open link directory, and compact utility row."""
    return rx.el.footer(
        rx.el.div(
            rx.el.elements.a(
                rx.image(
                    src=f"{REFLEX_ASSETS_CDN}logos/light/reflex.svg",
                    alt="Reflex home",
                    class_name="block h-5 w-auto dark:hidden",
                ),
                rx.image(
                    src=f"{REFLEX_ASSETS_CDN}logos/dark/reflex.svg",
                    alt="Reflex home",
                    class_name="hidden h-5 w-auto dark:block",
                ),
                href=REFLEX_URL,
                class_name=f"w-fit rounded-sm {_FOCUS}",
            ),
            _newsletter(),
            class_name="flex flex-col items-start justify-between gap-10 pb-14 sm:flex-row sm:gap-16",
        ),
        rx.el.div(
            *[_link_column(heading, links) for heading, links in _FOOTER_LINKS],
            class_name="grid grid-cols-2 gap-x-8 gap-y-10 md:grid-cols-3 lg:grid-cols-6",
        ),
        rx.el.div(
            rx.el.div(
                *[
                    rx.el.elements.a(
                        get_icon(icon, class_name="size-4 shrink-0"),
                        href=url,
                        aria_label=f"Social link for {name}",
                        title=f"{name} (opens in a new tab)",
                        target="_blank",
                        rel="noopener noreferrer",
                        class_name="docs-footer-social-link flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-subtle dark:hover:bg-accent hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foreground",
                    )
                    for icon, url, name in (
                        ("twitter_footer", TWITTER_URL, "Twitter"),
                        ("github_navbar", GITHUB_ORG_URL, "GitHub"),
                        ("linkedin_footer", LINKEDIN_URL, "LinkedIn"),
                        ("discord_navbar", DISCORD_URL, "Discord"),
                    )
                ],
                class_name="flex flex-wrap items-center gap-3",
            ),
            rx.el.span(
                f"Reflex © {datetime.now().year} Pynecone, Inc.",
                class_name="text-xs font-normal text-muted-foreground",
            ),
            rx.el.div(
                server_status(StatusState.status),
                _theme_toggle(),
                class_name="flex flex-wrap items-center gap-4 [&>a]:rounded-full [&>a]:focus-visible:outline-2 [&>a]:focus-visible:outline-ring [&>a>div]:text-xs [&>a>div]:font-normal",
            ),
            class_name="flex flex-col items-start justify-between gap-6 pt-16 lg:flex-row lg:flex-wrap lg:items-center",
        ),
        class_name="docs-footer mx-auto w-full max-w-(--landing-layout-max-width) border-t border-border-subtle px-6 pb-10 pt-12 text-foreground sm:pt-16 xl:px-0",
    )
