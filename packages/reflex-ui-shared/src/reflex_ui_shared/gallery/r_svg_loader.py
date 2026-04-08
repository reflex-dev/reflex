"""R Svg Loader module."""

import reflex as rx

loading_style = {
    "rect": {
        "opacity": "0",
        "animation": "fadeInStayOut 6s linear infinite",
    },
    "@keyframes fadeInStayOut": {
        "0%": {"opacity": "0"},
        "5%": {"opacity": "1"},
        "50%": {"opacity": "1"},
        "55%": {"opacity": "0"},
        "100%": {"opacity": "0"},
    },
}

for i in range(1, 14):
    loading_style[f"rect:nth-child({i})"] = {"animation_delay": f"{(i - 1) * 0.2}s"}


def svg_loading():
    """Svg loading.

    Returns:
        The component.
    """
    return rx.box(
        rx.html(
            """<svg width="88" height="88" viewBox="0 0 88 88" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="32" y="41" width="6" height="6" fill="#6E56CF"/>
                <rect x="38" y="29" width="6" height="6" fill="#6E56CF"/>
                <rect x="50" y="47" width="6" height="6" fill="#6E56CF"/>
                <rect x="32" y="53" width="6" height="6" fill="#6E56CF"/>
                <rect x="44" y="41" width="6" height="6" fill="#6E56CF"/>
                <rect x="50" y="35" width="6" height="6" fill="#6E56CF"/>
                <rect x="50" y="53" width="6" height="6" fill="#6E56CF"/>
                <rect x="44" y="29" width="6" height="6" fill="#6E56CF"/>
                <rect x="32" y="29" width="6" height="6" fill="#6E56CF"/>
                <rect x="32" y="47" width="6" height="6" fill="#6E56CF"/>
                <rect x="50" y="29" width="6" height="6" fill="#6E56CF"/>
                <rect x="38" y="41" width="6" height="6" fill="#6E56CF"/>
                <rect x="32" y="35" width="6" height="6" fill="#6E56CF"/>
            </svg>"""
        ),
        style=loading_style,
        position="absolute",
    )


spinner_style = {
    "g rect": {
        "transform-origin": "0 0",
    },
    "g rect:nth-of-type(1)": {
        "animation": "growShrinkWidth 3s linear infinite",
        "width": "0",
    },
    "g rect:nth-of-type(2)": {
        "animation": "growShrinkHeight 3s linear infinite 0.35s",
        "height": "0",
    },
    "g rect:nth-of-type(3)": {
        "animation": "growShrinkWidthReverse 3s linear infinite 0.7s",
        "width": "0",
    },
    "g rect:nth-of-type(4)": {
        "animation": "growShrinkHeightReverse 3s linear infinite 1.05s",
        "height": "0",
    },
    "@keyframes growShrinkWidth": {
        "0%": {"width": "0", "transform": "translateX(0)"},
        "12.5%": {"width": "40px", "transform": "translateX(0)"},
        "37.5%": {"width": "40px", "transform": "translateX(0)"},
        "50%": {"width": "40px", "transform": "translateX(0)"},
        "62.5%": {"width": "0", "transform": "translateX(40px)"},
        "100%": {"width": "0", "transform": "translateX(40px)"},
    },
    "@keyframes growShrinkHeight": {
        "0%": {"height": "0", "transform": "translateY(0)"},
        "12.5%": {"height": "40px", "transform": "translateY(0)"},
        "37.5%": {"height": "40px", "transform": "translateY(0)"},
        "50%": {"height": "40px", "transform": "translateY(0)"},
        "62.5%": {"height": "0", "transform": "translateY(40px)"},
        "100%": {"height": "0", "transform": "translateY(40px)"},
    },
    "@keyframes growShrinkWidthReverse": {
        "0%": {"width": "0", "transform": "translateX(41px)"},
        "12.5%": {"width": "41px", "transform": "translateX(0)"},
        "37.5%": {"width": "41px", "transform": "translateX(0)"},
        "50%": {"width": "41px", "transform": "translateX(0)"},
        "62.5%": {"width": "0", "transform": "translateX(0)"},
        "100%": {"width": "0", "transform": "translateX(0)"},
    },
    "@keyframes growShrinkHeightReverse": {
        "0%": {"height": "0", "transform": "translateY(40px)"},
        "12.5%": {"height": "40px", "transform": "translateY(0)"},
        "37.5%": {"height": "40px", "transform": "translateY(0)"},
        "50%": {"height": "40px", "transform": "translateY(0)"},
        "62.5%": {"height": "0", "transform": "translateY(0)"},
        "100%": {"height": "0", "transform": "translateY(0)"},
    },
}


def spinner_svg(mask_name: str):
    """Spinner svg.

    Returns:
        The component.
    """
    return rx.box(
        rx.html(
            f"""<svg width="88" height="88" viewBox="0 0 88 88" fill="none" xmlns="http://www.w3.org/2000/svg">
                <mask id="{mask_name}" style="mask-type:alpha" maskUnits="userSpaceOnUse" x="20" y="20" width="48" height="48">
                    <rect x="21" y="21" width="46" height="46" rx="7" stroke="black" stroke-width="2"/>
                </mask>
                <g mask="url(#{mask_name})">
                    <rect x="20" y="20" width="0" height="8" fill="#6E56CF"/>
                    <rect x="60" y="20" width="8" height="0" fill="#6E56CF"/>
                    <rect x="27" y="60" width="0" height="8" fill="#6E56CF"/>
                    <rect x="20" y="28" width="8" height="0" fill="#6E56CF"/>
                </g>
            </svg>"""
        ),
        style=spinner_style,
    )


def r_svg_loader():
    """R svg loader.

    Returns:
        The component.
    """
    return rx.fragment(
        spinner_svg(mask_name="mask"),
        svg_loading(),
    )
