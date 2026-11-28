"""Components for displaying the Reflex sticky logo."""

import urllib.parse

from reflex_base.breakpoints import breakpoints_values
from reflex_base.components.component import ComponentNamespace
from reflex_base.environment import environment

from reflex_components_core.base.static_style import static_style
from reflex_components_core.core.colors import color
from reflex_components_core.el.elements.inline import A, Span
from reflex_components_core.el.elements.media import Path, Rect, Svg
from reflex_components_core.el.elements.typography import Div

# What tells the stylesheet of the badge from any other in the document.
_STYLESHEET = "rx-sticky-badge"


def _badge_css() -> str:
    """Write the look of the badge.

    Plain rules, not ``css`` props: the badge is added to apps that may
    otherwise not need Emotion. The colors follow the color mode through the
    class the theme provider keeps on the document element, and the label
    shows from the desktop breakpoint of the app.

    Returns:
        The rules.
    """
    return (
        ".rx-sticky-badge{position:fixed;bottom:1rem;right:1rem;display:flex;"
        "flex-direction:row;gap:0.375rem;align-items:center;width:auto;"
        "border-radius:0.5rem;color:#E5E7EB;border:1px solid #27282B;"
        "background-color:#151618;padding:0.375rem;"
        "transition:background-color 0.2s ease-in-out;"
        "box-shadow:0 1px 2px 0 rgba(0, 0, 0, 0.05);z-index:9998;cursor:pointer;"
        "text-align:center}"
        ".dark .rx-sticky-badge{color:#27282B;border:1px solid #E5E7EB;"
        "background-color:#FCFCFD}"
        ".rx-sticky-logo{fill:white}"
        ".rx-sticky-logo-square{fill:#6E56CF}"
        ".rx-sticky-logo-letter{fill:white}"
        "@media screen and (min-width: 0){.rx-sticky-desktop-only{display:none}}"
        f"@media screen and (min-width: {breakpoints_values[2]})"
        "{.rx-sticky-desktop-only{display:block}}"
        f".rx-sticky-label{{color:{color('slate', 1)};font-weight:600;"
        "font-family:'Instrument Sans', sans-serif;"
        "--default-font-family:'Instrument Sans', sans-serif;font-size:0.875rem;"
        "line-height:1rem;letter-spacing:-0.00656rem}"
    )


class StickyLogo(Svg):
    """A simple Reflex logo SVG with only the letter R."""

    @classmethod
    def create(cls):
        """Create the simple Reflex logo SVG.

        Returns:
            The simple Reflex logo SVG.
        """
        return super().create(
            # Filled by attribute as well as by the stylesheet of the badge:
            # the logo is drawn right where it is used without the badge. An
            # attribute, as a `fill` prop is a style only Emotion applies.
            Rect.create(
                width="16",
                height="16",
                rx="2",
                custom_attrs={"fill": "#6E56CF"},
                class_name="rx-sticky-logo-square",
            ),
            Path.create(
                d="M10 9V13H12V9H10Z",
                custom_attrs={"fill": "white"},
                class_name="rx-sticky-logo-letter",
            ),
            Path.create(
                d="M4 3V13H6V9H10V7H6V5H10V7H12V3H4Z",
                custom_attrs={"fill": "white"},
                class_name="rx-sticky-logo-letter",
            ),
            width="16",
            height="16",
            view_box="0 0 16 16",
            xmlns="http://www.w3.org/2000/svg",
            class_name="rx-sticky-logo",
        )


class StickyLabel(Span):
    """A label that displays the Reflex sticky."""

    @classmethod
    def create(cls):
        """Create the sticky label.

        Returns:
            The sticky label.
        """
        return super().create(
            # Its own copy of the stylesheet, for a label outside the badge:
            # React keeps one per name in the document.
            static_style(_STYLESHEET, _badge_css()),
            "Built with Reflex",
            class_name="rx-sticky-label",
        )


def _badge_href() -> str:
    """Compute the badge link, appending the referrer param when set.

    Returns:
        The badge destination URL.
    """
    referrer = environment.REFLEX_REFERRER_PARAM.get()
    if referrer:
        return f"https://reflex.dev/?ref={urllib.parse.quote(referrer, safe='')}"
    return "https://reflex.dev"


class StickyBadge(A):
    """A badge that displays the Reflex sticky logo."""

    @classmethod
    def create(cls):
        """Create the sticky badge.

        Returns:
            The sticky badge.
        """
        return super().create(
            static_style(_STYLESHEET, _badge_css()),
            StickyLogo.create(),
            Div.create(
                Span.create("Built with Reflex", class_name="rx-sticky-label"),
                class_name="rx-sticky-desktop-only",
            ),
            href=_badge_href(),
            aria_label="Built with Reflex",
            target="_blank",
            class_name="rx-sticky-badge",
        )


class StickyNamespace(ComponentNamespace):
    """Sticky components namespace."""

    __call__ = staticmethod(StickyBadge.create)
    label = staticmethod(StickyLabel.create)
    logo = staticmethod(StickyLogo.create)


sticky = StickyNamespace()
