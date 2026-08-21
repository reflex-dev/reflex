"""Design tokens and theming for the Reflex UI component library.

The theme is a set of CSS custom properties (design tokens) with light and
dark values, mapped into Tailwind utility names via ``@theme inline`` so
classes like ``bg-primary`` or ``text-muted-foreground`` work in components
and user code alike.

Tokens follow the naming convention popularized by shadcn/ui, so existing
Tailwind theme generators and copy-pasted CSS themes work unchanged. Every
token can be overridden from Python via :class:`Theme`, from CSS by
redefining the variable (globally or per subtree), or with Tailwind classes
on individual components.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

# Default token values, adapted from the shadcn/ui zinc palette.
LIGHT_TOKENS: Mapping[str, str] = {
    "background": "oklch(1 0 0)",
    "foreground": "oklch(0.141 0.005 285.823)",
    "card": "oklch(1 0 0)",
    "card-foreground": "oklch(0.141 0.005 285.823)",
    "popover": "oklch(1 0 0)",
    "popover-foreground": "oklch(0.141 0.005 285.823)",
    "primary": "oklch(0.21 0.006 285.885)",
    "primary-foreground": "oklch(0.985 0 0)",
    "secondary": "oklch(0.967 0.001 286.375)",
    "secondary-foreground": "oklch(0.21 0.006 285.885)",
    "muted": "oklch(0.967 0.001 286.375)",
    "muted-foreground": "oklch(0.552 0.016 285.938)",
    "accent": "oklch(0.967 0.001 286.375)",
    "accent-foreground": "oklch(0.21 0.006 285.885)",
    "destructive": "oklch(0.577 0.245 27.325)",
    "destructive-foreground": "oklch(0.985 0 0)",
    "border": "oklch(0.92 0.004 286.32)",
    "input": "oklch(0.92 0.004 286.32)",
    "ring": "oklch(0.705 0.015 286.067)",
}

DARK_TOKENS: Mapping[str, str] = {
    "background": "oklch(0.141 0.005 285.823)",
    "foreground": "oklch(0.985 0 0)",
    "card": "oklch(0.21 0.006 285.885)",
    "card-foreground": "oklch(0.985 0 0)",
    "popover": "oklch(0.21 0.006 285.885)",
    "popover-foreground": "oklch(0.985 0 0)",
    "primary": "oklch(0.92 0.004 286.32)",
    "primary-foreground": "oklch(0.21 0.006 285.885)",
    "secondary": "oklch(0.274 0.006 286.033)",
    "secondary-foreground": "oklch(0.985 0 0)",
    "muted": "oklch(0.274 0.006 286.033)",
    "muted-foreground": "oklch(0.705 0.015 286.067)",
    "accent": "oklch(0.274 0.006 286.033)",
    "accent-foreground": "oklch(0.985 0 0)",
    "destructive": "oklch(0.704 0.191 22.216)",
    "destructive-foreground": "oklch(0.985 0 0)",
    "border": "oklch(1 0 0 / 10%)",
    "input": "oklch(1 0 0 / 15%)",
    "ring": "oklch(0.552 0.016 285.938)",
}


def _normalize_tokens(tokens: Mapping[str, str]) -> dict[str, str]:
    """Normalize user token names to CSS custom property form.

    Args:
        tokens: Token overrides keyed by name, using ``_`` or ``-`` separators.

    Returns:
        The tokens keyed by hyphenated names.
    """
    return {name.replace("_", "-"): value for name, value in tokens.items()}


def _variables_block(selector: str, tokens: Mapping[str, str]) -> str:
    """Render a CSS rule assigning custom properties.

    Args:
        selector: The CSS selector for the rule.
        tokens: Token names (without leading ``--``) mapped to values.

    Returns:
        The CSS rule text.
    """
    lines = "\n".join(f"  --{name}: {value};" for name, value in tokens.items())
    return f"{selector} {{\n{lines}\n}}"


@dataclasses.dataclass(frozen=True)
class Theme:
    """Theme configuration for Reflex UI components.

    Token overrides accept any known token name (e.g. ``primary``,
    ``primary_foreground``) as well as custom names, which become new CSS
    variables with matching ``--color-*`` Tailwind mappings (so a custom
    ``brand`` token makes ``bg-brand``, ``text-brand``, etc. available).
    """

    # The base border radius applied through the rounded-* utilities.
    radius: str = "0.625rem"

    # Token value overrides for light mode.
    light: Mapping[str, str] = dataclasses.field(default_factory=dict)

    # Token value overrides for dark mode.
    dark: Mapping[str, str] = dataclasses.field(default_factory=dict)

    def stylesheet(self) -> str:
        """Generate the theme stylesheet compiled into the app's Tailwind CSS.

        Returns:
            The CSS text defining token values, dark mode overrides, and the
            ``@theme inline`` mapping that exposes tokens as Tailwind utilities.
        """
        light = {**LIGHT_TOKENS, **_normalize_tokens(self.light)}
        dark = {**DARK_TOKENS, **_normalize_tokens(self.dark)}
        color_tokens = dict.fromkeys((*light, *dark))
        theme_mapping = {f"color-{name}": f"var(--{name})" for name in color_tokens} | {
            "radius-sm": "calc(var(--radius) - 4px)",
            "radius-md": "calc(var(--radius) - 2px)",
            "radius-lg": "var(--radius)",
            "radius-xl": "calc(var(--radius) + 4px)",
        }
        body_rule = (
            "@layer base {\n"
            "  body {\n"
            "    background-color: var(--background);\n"
            "    color: var(--foreground);\n"
            "  }\n"
            "}"
        )
        return "\n\n".join([
            "/* Generated by Reflex from rx.ui.Theme -- do not edit. */",
            _variables_block(":root", {"radius": self.radius, **light}),
            _variables_block(".dark", dark),
            _variables_block("@theme inline", theme_mapping),
            body_rule,
            "",
        ])
