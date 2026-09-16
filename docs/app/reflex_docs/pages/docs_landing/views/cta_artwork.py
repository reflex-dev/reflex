"""Component reconstruction on the original illustration's 596 by 380 grid."""

import math
from itertools import pairwise

import reflex as rx


def _units(value: float) -> str:
    """Convert an original artwork coordinate to responsive container units.

    Args:
        value: Distance in the original 596-pixel-wide artwork.

    Returns:
        The proportional CSS distance.
    """
    return f"{value / 5.96:.5f}cqw"


def _box(
    *children: rx.Component,
    x: float,
    y: float,
    width: float,
    height: float,
    class_name: str = "",
    **style: object,
) -> rx.Component:
    """Place an element on the original illustration grid.

    Args:
        children: Contents of the element.
        x: Left coordinate relative to its parent.
        y: Top coordinate relative to its parent.
        width: Original width.
        height: Original height.
        class_name: Additional appearance classes.
        **style: Additional CSS declarations.

    Returns:
        A proportionally positioned element.
    """
    return rx.el.div(
        *children,
        class_name=f"absolute box-border {class_name}",
        style={
            "left": _units(x),
            "top": _units(y),
            "width": _units(width),
            "height": _units(height),
            **style,
        },
    )


def _account_row(y: float) -> rx.Component:
    """Draw a dashboard account card at its original coordinates.

    Args:
        y: Top coordinate of the row.

    Returns:
        An outlined account card.
    """
    outline = "border border-[var(--cta-border)]"
    return _box(
        _box(
            rx.icon(
                "user-round",
                stroke_width=1,
                style={"width": _units(12), "height": _units(12)},
            ),
            x=12,
            y=12,
            width=32,
            height=32,
            class_name=f"{outline} rounded-full flex items-center justify-center",
        ),
        _box(x=52, y=18, width=31, height=5, class_name=f"{outline} rounded-full"),
        _box(x=52, y=32, width=71, height=5, class_name=f"{outline} rounded-full"),
        _box(
            _box(x=19, y=2, width=9, height=9, class_name=f"{outline} rounded-full"),
            x=170,
            y=12,
            width=31,
            height=14,
            class_name=f"{outline} rounded-full",
        ),
        x=358,
        y=y,
        width=214,
        height=56,
        class_name=f"{outline} bg-[var(--cta-surface)]",
        border_radius=_units(8),
    )


def _chart_line(points: tuple[tuple[float, float], ...]) -> rx.Component:
    """Connect chart points with thin solid HTML line segments.

    Args:
        points: Chart coordinates on the original artwork grid.

    Returns:
        A group of connected line segments.
    """
    return rx.el.div(*[
        _box(
            x=x1,
            y=y1,
            width=math.hypot(x2 - x1, y2 - y1),
            height=0.6,
            class_name="bg-muted-foreground",
            transform_origin="left center",
            transform=f"rotate({math.degrees(math.atan2(y2 - y1, x2 - x1))}deg)",
        )
        for (x1, y1), (x2, y2) in pairwise(points)
    ])


def cta_artwork() -> rx.Component:
    """Recreate the original composition with HTML cards, text, and charts.

    Returns:
        A decorative, theme-aware illustration with solid outlines.
    """
    card_shadow = "0 1px 2px rgb(0 0 0 / 5%), 0 8px 12px -8px rgb(0 0 0 / 12%)"
    outline = "border border-[var(--cta-border)]"
    return rx.el.div(
        _box(x=56, y=0, width=0.5, height=380, class_name="bg-[var(--cta-border)]"),
        _box(
            x=32,
            y=108,
            width=320,
            height=32,
            class_name="bg-[var(--cta-surface)] border border-[var(--cta-border)]",
            border_radius=_units(10),
            box_shadow=card_shadow,
        ),
        *[
            _box(
                rx.el.span(label),
                x=80,
                y=y - 8,
                width=230,
                height=16,
                class_name="font-mono flex items-center whitespace-nowrap",
                font_size=_units(12),
                line_height="1",
                color="var(--foreground)" if index == 1 else "var(--muted-foreground)",
            )
            for index, (label, y) in enumerate((
                ("VER 0.0 · 4A57CB6", 80),
                ("VER 1.0 · 2C873K2", 124),
                ("VER 2.0 · X82AKS2", 168),
            ))
        ],
        *[
            _box(x=56, y=y - 5.5, width=1, height=11, class_name="bg-muted-foreground")
            for y in (80, 168)
        ],
        *[
            _box(
                x=56.5 - size / 2,
                y=y - size / 2,
                width=size,
                height=size,
                class_name="rounded-full bg-muted-foreground",
            )
            for y, size in ((80, 3), (124, 5), (168, 3))
        ],
        _box(
            _box(
                rx.el.span("Connect my dashboard with database"),
                x=16,
                y=15,
                width=288,
                height=20,
                class_name="flex items-center whitespace-nowrap",
                font_size=_units(14),
                line_height="1",
            ),
            _box(
                rx.icon(
                    "brain",
                    stroke_width=1,
                    style={"width": _units(12), "height": _units(12)},
                ),
                rx.el.span("Deep Thinking"),
                x=16,
                y=56,
                width=115,
                height=23,
                class_name=f"{outline} flex items-center justify-center rounded-full whitespace-nowrap",
                gap=_units(6),
                font_size=_units(12),
                line_height="1",
            ),
            x=32,
            y=220,
            width=320,
            height=96,
            class_name="bg-[var(--cta-surface)] border border-[var(--cta-border)]",
            border_radius=_units(10),
            box_shadow=card_shadow,
        ),
        _box(
            x=334,
            y=0,
            width=262,
            height=380,
            class_name="bg-[var(--cta-surface)] border-l border-[var(--cta-border)]",
        ),
        _box(
            x=334,
            y=0,
            width=262,
            height=96,
            class_name="bg-[var(--cta-surface)] border-b border-[var(--cta-border)]",
            box_shadow=card_shadow,
        ),
        _box(
            rx.icon(
                "refresh-cw", stroke_width=1, style={"width": "100%", "height": "100%"}
            ),
            x=358,
            y=74,
            width=12,
            height=12,
        ),
        _box(
            rx.el.span("/dashboard"),
            x=430,
            y=72,
            width=90,
            height=16,
            class_name="flex items-center",
            font_size=_units(12),
            line_height="1",
        ),
        _box(
            rx.icon(
                "external-link",
                stroke_width=1,
                style={"width": "100%", "height": "100%"},
            ),
            x=560,
            y=74,
            width=12,
            height=12,
        ),
        _box(
            x=358,
            y=120,
            width=64,
            height=64,
            class_name=f"{outline} bg-[var(--cta-surface)]",
            border_radius=_units(8),
        ),
        *[
            _box(
                x=x,
                y=172 - height,
                width=6,
                height=height,
                class_name=f"{outline}",
                border_radius=_units(1),
            )
            for x, height in ((370, 23), (380, 33), (390, 17), (402, 40))
        ],
        _box(
            x=438,
            y=120,
            width=134,
            height=64,
            class_name=f"{outline} bg-[var(--cta-surface)]",
            border_radius=_units(8),
        ),
        *[
            _box(x=450, y=y, width=110, height=0.5, class_name="bg-[var(--cta-border)]")
            for y in (136, 152, 168)
        ],
        _chart_line((
            (450, 167),
            (466, 159),
            (478, 156),
            (493, 160),
            (510, 149),
            (521, 153),
            (535, 148),
            (545, 151),
            (560, 136),
        )),
        _chart_line((
            (450, 166),
            (464, 168),
            (478, 155),
            (489, 159),
            (499, 165),
            (509, 150),
            (520, 156),
            (535, 155),
            (545, 146),
            (560, 136),
        )),
        *[_account_row(y) for y in (200, 272, 344)],
        aria_hidden=True,
        class_name="docs-cta-art pointer-events-none relative aspect-[596/380] w-full self-center overflow-hidden text-muted-foreground max-lg:hidden",
        style={
            "container_type": "inline-size",
            "--cta-surface": "color-mix(in srgb, var(--muted) 80%, var(--background))",
            "--cta-border": "var(--border-strong)",
            "mask_image": "linear-gradient(to bottom, transparent, black 14%, black 85%, transparent), linear-gradient(to right, black 92%, transparent)",
            "mask_composite": "intersect",
        },
    )
