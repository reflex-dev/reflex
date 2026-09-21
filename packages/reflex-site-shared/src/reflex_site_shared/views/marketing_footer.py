"""Open, directory-style footer for the editorial homepage."""

from datetime import datetime
from typing import Literal

import reflex as rx
import reflex_components_internal as ui

from reflex_site_shared.backend.signup import IndexState
from reflex_site_shared.backend.status import StatusState
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.constants import (
    CHANGELOG_URL,
    DISCORD_URL,
    GITHUB_ORG_URL,
    LINKEDIN_URL,
    REFLEX_URL,
    STATUS_WEB_URL,
    TWITTER_URL,
    XY_GITHUB_URL,
)
from reflex_site_shared.views.footer import dark_mode_toggle

FooterLinks = list[tuple[str, str]]
FooterAppearance = Literal["dark", "light"]


def _external_marker() -> rx.Component:
    """A compact visual cue for a destination outside the marketing site.

    Returns:
        The footer component.
    """
    return ui.icon(
        "ArrowUpRight01Icon",
        aria_hidden=True,
        class_name="size-3 shrink-0",
    )


def _footer_link(
    text: str,
    href: str,
    *,
    compact: bool = False,
    appearance: FooterAppearance = "dark",
) -> rx.Component:
    """Render a quiet footer link, opening external destinations safely.

    Args:
        text: Visible link or status label.
        href: Destination URL or marketing path.
        compact: Whether to use smaller utility text.
        appearance: Semantic surface treatment for the footer.

    Returns:
        The footer component.
    """
    class_name = (
        "w-fit font-book leading-6 transition-colors "
        + (
            "text-xs text-primary-foreground/60 "
            if compact
            else "text-sm text-primary-foreground/90 "
        )
        + "duration-200 focus-visible:rounded-sm hover:text-primary-foreground "
        "focus-visible:outline-2 focus-visible:outline-offset-4 "
        "focus-visible:outline-primary-foreground"
    )
    if appearance == "light":
        class_name = (
            "w-fit font-book leading-6 transition-colors "
            + (
                "text-xs text-muted-foreground hover:text-foreground "
                if compact
                else "text-sm text-foreground hover:text-muted-foreground "
            )
            + "duration-200 focus-visible:rounded-sm "
            "focus-visible:outline-2 focus-visible:outline-offset-4 "
            "focus-visible:outline-foreground"
        )
    if href.startswith("/"):
        return rx.el.elements.a(
            text,
            href=f"{REFLEX_URL.rstrip('/')}{href}",
            class_name=class_name,
        )
    return rx.el.elements.a(
        text,
        _external_marker(),
        href=href,
        aria_label=f"{text} (opens in a new tab)",
        target="_blank",
        rel="noopener noreferrer",
        class_name=f"inline-flex items-center gap-1.5 {class_name}",
    )


def _link_section(
    heading: str, links: FooterLinks, *, appearance: FooterAppearance = "dark"
) -> rx.Component:
    """Render one labeled set of links inside a footer column.

    Args:
        heading: Section heading.
        links: Link labels and destinations.
        appearance: Semantic surface treatment for the footer.

    Returns:
        The footer component.
    """
    return rx.el.div(
        rx.el.h2(
            heading,
            class_name="text-xs font-book leading-5 "
            + (
                "text-muted-foreground"
                if appearance == "light"
                else "text-primary-foreground/60"
            ),
        ),
        rx.el.div(
            *[_footer_link(text, href, appearance=appearance) for text, href in links],
            class_name="mt-2 flex flex-col gap-2",
        ),
        class_name="break-inside-avoid",
    )


def _footer_column(
    label: str,
    *sections: tuple[str, FooterLinks],
    appearance: FooterAppearance = "dark",
) -> rx.Component:
    """Render a semantic footer navigation column.

    Args:
        label: Accessible name for this navigation column.
        appearance: Semantic surface treatment for the footer.
        sections: Headings paired with their link groups.

    Returns:
        The footer component.
    """
    return rx.el.nav(
        *[
            _link_section(heading, links, appearance=appearance)
            for heading, links in sections
        ],
        aria_label=f"{label} footer links",
        class_name="flex min-w-0 flex-col gap-10",
    )


def _socials(*, appearance: FooterAppearance = "dark") -> rx.Component:
    """Render community destinations with consistent icon-button styling.

    Args:
        appearance: Semantic surface treatment for the footer.

    Returns:
        The footer component.
    """
    return rx.el.div(
        *[
            rx.el.elements.a(
                get_icon(icon, class_name="size-4 shrink-0"),
                href=url,
                aria_label=f"{name} (opens in a new tab)",
                title=f"{name} (opens in a new tab)",
                target="_blank",
                rel="noopener noreferrer",
                class_name=(
                    "flex size-7 items-center justify-center rounded-md transition-colors "
                    "focus-visible:outline-2 focus-visible:outline-offset-2 "
                    "text-muted-foreground hover:bg-subtle hover:text-foreground focus-visible:outline-foreground"
                    if appearance == "light"
                    else "flex size-7 items-center justify-center rounded-md text-primary-foreground/60 transition-colors hover:bg-background/10 hover:text-primary-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-foreground"
                ),
            )
            for icon, url, name in [
                ("twitter_footer", TWITTER_URL, "Twitter"),
                ("github_navbar", GITHUB_ORG_URL, "GitHub"),
                ("linkedin_footer", LINKEDIN_URL, "LinkedIn"),
                ("discord_navbar", DISCORD_URL, "Discord"),
            ]
        ],
        class_name="flex flex-wrap items-center gap-3",
    )


def _server_status(*, appearance: FooterAppearance = "dark") -> rx.Component:
    """A compact status link without nested component style overrides.

    Args:
        appearance: Semantic surface treatment for the footer.

    Returns:
        The footer component.
    """

    def label(text: str, color: str) -> rx.Component:
        return rx.el.span(
            rx.el.span(aria_hidden="true", class_name="size-2 rounded-full bg-current"),
            text,
            rx.el.span(" (opens in a new tab)", class_name="sr-only"),
            class_name=f"inline-flex items-center gap-1.5 text-xs font-book {color}",
        )

    return rx.el.elements.a(
        rx.match(
            StatusState.status,
            (
                "Warning",
                label(
                    "Some servers are unavailable",
                    "text-warning-11",
                ),
            ),
            ("Critical", label("All servers are down", "text-destructive-11")),
            label(
                "All servers are operational",
                "text-success-11",
            ),
        ),
        href=STATUS_WEB_URL,
        target="_blank",
        rel="noopener noreferrer",
        class_name=(
            "block rounded-full px-3 py-2 transition-colors hover:bg-subtle "
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foreground"
            if appearance == "light"
            else "block rounded-full px-3 py-2 transition-colors hover:bg-background/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-foreground"
        ),
    )


def _newsletter(*, appearance: FooterAppearance = "dark") -> rx.Component:
    """Render the compact footer newsletter form using the existing signup state.

    Args:
        appearance: Semantic surface treatment for the footer.

    Returns:
        The footer component.
    """
    return rx.el.div(
        rx.el.h2(
            "Get Updates",
            class_name="text-xs font-book leading-5 "
            + (
                "text-muted-foreground"
                if appearance == "light"
                else "text-primary-foreground/60"
            ),
        ),
        rx.cond(
            IndexState.signed_up,
            rx.el.div(
                rx.el.div(
                    ui.icon(
                        "CheckmarkCircle02Icon",
                        size=18,
                        aria_hidden=True,
                        class_name="shrink-0",
                    ),
                    rx.el.span(
                        "Thanks for subscribing!",
                        class_name="text-sm font-medium",
                    ),
                    role="status",
                    class_name="flex items-center gap-2",
                ),
                button(
                    "Use another email address",
                    type="button",
                    variant="outline",
                    size="sm",
                    on_click=IndexState.signup_for_another_user,
                ),
                class_name="mt-3 flex flex-col items-start gap-3",
            ),
            rx.el.form(
                rx.el.label(
                    "Email address",
                    html_for="footer-newsletter-email",
                    class_name="sr-only",
                ),
                rx.el.div(
                    rx.el.input(
                        id="footer-newsletter-email",
                        name="input_email",
                        type="email",
                        required=True,
                        auto_complete="email",
                        placeholder="Email",
                        class_name=(
                            "h-full w-full min-w-0 flex-1 bg-transparent text-base md:text-sm "
                            "text-foreground outline-none placeholder:text-subtle-foreground"
                        ),
                    ),
                    button(
                        ui.icon("ArrowRight02Icon", size=16, aria_hidden=True),
                        type="submit",
                        aria_label="Subscribe to updates",
                        title="Subscribe to updates",
                        variant="primary",
                        size="icon-xs",
                        class_name="shrink-0",
                    ),
                    class_name="flex h-9 w-full items-center gap-2 rounded-full border border-border bg-background pl-3 pr-1 shadow-small focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-ring",
                ),
                on_submit=IndexState.signup,
                class_name="mt-3 w-full min-w-0 max-w-56",
            ),
        ),
        class_name="min-w-0",
    )


def _utility_row(
    *, appearance: FooterAppearance = "dark", show_color_mode_toggle: bool = False
) -> rx.Component:
    """Render social links, copyright, and server status.

    Args:
        appearance: Semantic surface treatment for the footer.
        show_color_mode_toggle: Whether to include the documentation theme controls.

    Returns:
        The footer component.
    """
    return rx.el.div(
        rx.el.div(
            _socials(appearance=appearance),
            class_name="flex flex-wrap items-center gap-4",
        ),
        rx.el.div(
            rx.el.span(
                f"Reflex © {datetime.now().year} Pynecone, Inc.",
                class_name="text-xs font-book "
                + (
                    "text-muted-foreground"
                    if appearance == "light"
                    else "text-primary-foreground/90"
                ),
            ),
            class_name=(
                "flex flex-row flex-wrap items-center justify-center gap-x-3 gap-y-2 "
            ),
        ),
        rx.el.div(
            _server_status(appearance=appearance),
            dark_mode_toggle() if show_color_mode_toggle else rx.fragment(),
            class_name="flex flex-row flex-wrap items-center justify-start gap-3 lg:justify-end",
        ),
        class_name=(
            "grid grid-cols-1 items-center gap-7 pb-8 pt-16 "
            "sm:pb-10 lg:grid-cols-[1fr_auto_1fr] lg:gap-10 lg:pt-20 "
            "[&>:nth-child(1)]:justify-self-start "
            "[&>:nth-child(2)]:justify-self-start lg:[&>:nth-child(2)]:justify-self-center "
            "[&>:nth-child(3)]:justify-self-start lg:[&>:nth-child(3)]:justify-self-end"
        ),
    )


def marketing_footer(
    *, appearance: FooterAppearance = "light", show_color_mode_toggle: bool = False
) -> rx.Component:
    """Render the shared five-column footer with an optional light appearance.

    Args:
        appearance: Semantic surface treatment for the footer.
        show_color_mode_toggle: Whether to include the documentation theme controls.

    Returns:
        The footer component.
    """
    return rx.el.footer(
        rx.el.div(
            rx.el.div(
                _footer_column(
                    "Platform",
                    (
                        "Platform",
                        [
                            ("Overview", "/platform/"),
                            ("AI Builder", "/ai-builder/"),
                            ("Integrations", "/integrations/"),
                            ("Enterprise", "/enterprise/"),
                            ("App Management", "/hosting/"),
                            ("Pricing", "/pricing/"),
                        ],
                    ),
                    (
                        "Open source",
                        [
                            ("Framework", "/open-source/"),
                            ("XY", XY_GITHUB_URL),
                            ("GitHub", GITHUB_ORG_URL),
                        ],
                    ),
                    appearance=appearance,
                ),
                _footer_column(
                    "Solutions",
                    (
                        "Solutions",
                        [
                            ("Overview", "/use-cases/"),
                            ("Internal tools", "/use-cases/internal-tools/"),
                            ("Analytics", "/use-cases/analytics/"),
                            ("Knowledge applications", "/use-cases/knowledge-apps/"),
                            ("Financial services", "/use-cases/finance/"),
                            ("Healthcare", "/use-cases/healthcare/"),
                            ("Consulting", "/use-cases/consulting/"),
                            ("Government", "/use-cases/government/"),
                            ("Manufacturing", "/use-cases/manufacturing/"),
                            ("Technology", "/use-cases/technology/"),
                        ],
                    ),
                    (
                        "Community",
                        [
                            ("Discord", DISCORD_URL),
                        ],
                    ),
                    appearance=appearance,
                ),
                _footer_column(
                    "Developers",
                    (
                        "Developers",
                        [
                            ("Documentation", "/docs/"),
                            (
                                "Agent Toolkit",
                                "https://reflex.dev/docs/ai/integrations/agent-toolkit/",
                            ),
                            ("Templates", "/templates/"),
                            ("Changelog", CHANGELOG_URL),
                        ],
                    ),
                    (
                        "Comparison",
                        [
                            ("From no/low-code", "/compare/no-code/"),
                            ("Frameworks", "/compare/frameworks/"),
                            ("From other AI tools", "/compare/other-ai-tools/"),
                        ],
                    ),
                    appearance=appearance,
                ),
                _footer_column(
                    "Company",
                    (
                        "Company",
                        [
                            ("About", "/about/"),
                            ("Press", "/press/"),
                            ("Customer stories", "/customers/"),
                            (
                                "Careers",
                                "https://www.ycombinator.com/companies/reflex/jobs",
                            ),
                        ],
                    ),
                    (
                        "Trust",
                        [
                            ("Security", "/security/"),
                            ("Security review", "/security/#security-review"),
                            ("System status", "https://status.reflex.dev"),
                        ],
                    ),
                    appearance=appearance,
                ),
                rx.el.div(
                    _footer_column(
                        "Resources",
                        (
                            "Resources",
                            [
                                ("Blog", "https://reflex.dev/blog/"),
                                (
                                    "Plan your first workflow",
                                    "/resources/first-workflow/",
                                ),
                                ("FAQ", "/faq/"),
                                ("Brand kit", "/brand/"),
                            ],
                        ),
                        (
                            "Terms & policies",
                            [
                                (
                                    "Privacy policy",
                                    "https://build.reflex.dev/privacy-policy",
                                ),
                                (
                                    "Terms of service",
                                    "https://build.reflex.dev/terms-of-use",
                                ),
                            ],
                        ),
                        appearance=appearance,
                    ),
                    _newsletter(appearance=appearance),
                    class_name="flex min-w-0 flex-col gap-10",
                ),
                class_name=(
                    "grid w-full grid-cols-2 gap-x-6 gap-y-10 pt-16 "
                    "sm:gap-x-10 sm:gap-y-14 sm:pt-24 md:grid-cols-3 "
                    "lg:grid-cols-5 lg:gap-x-12 lg:pt-28"
                ),
            ),
            _utility_row(
                appearance=appearance, show_color_mode_toggle=show_color_mode_toggle
            ),
            class_name=("mx-auto w-full max-w-[90rem] px-4 min-[55rem]:px-8 lg:px-12"),
        ),
        class_name=(
            "relative w-full overflow-x-clip "
            + (
                "bg-background text-foreground"
                if appearance == "light"
                else "bg-primary text-primary-foreground"
            )
        ),
    )
