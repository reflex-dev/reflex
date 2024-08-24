"""A module for generating Radix colors.

Converted from https://github.com/radix-ui/website/blob/main/components/generateRadixColors.tsx
"""

import math

from coloraide import Color

from .bezier import bezier
from .default_colors import DEFAULT_DARK_COLORS, DEFAULT_LIGHT_COLORS

ArrayOf12 = list[float]
gray_scale_names = ["gray", "mauve", "slate", "sage", "olive", "sand"]
scale_names = gray_scale_names + [
    "tomato",
    "red",
    "ruby",
    "crimson",
    "pink",
    "plum",
    "purple",
    "violet",
    "iris",
    "indigo",
    "blue",
    "cyan",
    "teal",
    "jade",
    "green",
    "grass",
    "brown",
    "orange",
    "sky",
    "mint",
    "lime",
    "yellow",
    "amber",
]


def get_base_colors(appearance: str):
    """Get the base colors from the default dicts.

    Args:
        appearance: The appearance of the colors.

    Returns:
        dict: The base colors.
    """
    raw_colors = DEFAULT_LIGHT_COLORS if appearance == "light" else DEFAULT_DARK_COLORS
    colors = {}
    for color_name, color_scale in raw_colors.items():
        f_scale = []
        for scale in color_scale:
            scale["coords"] = [
                float("nan") if x is None else x for x in scale["coords"]
            ]
            f_scale.append(Color(scale))
        colors[color_name] = f_scale
    return colors


light_colors = get_base_colors("light")
dark_colors = get_base_colors("dark")
light_gray_colors = {name: light_colors[name] for name in gray_scale_names}
dark_gray_colors = {name: dark_colors[name] for name in gray_scale_names}


def generate_radix_colors(
    appearance: str, accent: str, gray: str, background: str
) -> dict:
    """Generate Radix colors.

    Args:
        appearance: The appearance of the colors.
        accent: The accent color.
        gray: The gray color.
        background: The background color.

    Returns:
        dict: The generated colors.
    """
    all_scales = light_colors if appearance == "light" else dark_colors
    gray_scales = light_gray_colors if appearance == "light" else dark_gray_colors
    background_color = Color(background).convert("oklch")

    gray_base_color = Color(gray).convert("oklch")
    gray_scale_colors = get_scale_from_color(
        gray_base_color, gray_scales, background_color
    )

    accent_base_color = Color(accent).convert("oklch")
    accent_scale_colors = get_scale_from_color(
        accent_base_color, all_scales, background_color
    )

    background_hex = background_color.convert("srgb").to_string(hex=True)

    accent_base_hex = accent_base_color.convert("srgb").to_string(hex=True)
    if accent_base_hex == "#000000" or accent_base_hex == "#ffffff":
        accent_scale_colors = [color.clone() for color in gray_scale_colors]

    accent9_color, accent_contrast_color = get_step9_colors(
        accent_scale_colors, accent_base_color
    )

    accent_scale_colors[8] = accent9_color
    accent_scale_colors[9] = get_button_hover_color(
        accent9_color, [accent_scale_colors]
    )

    # Limit saturation of the text colors
    accent_scale_colors[10] = accent_scale_colors[10].set(
        "oklch.c",
        min(
            max(
                accent_scale_colors[8].get("oklch.c"),
                accent_scale_colors[7].get("oklch.c"),
            ),
            accent_scale_colors[10].get("oklch.c"),
        ),
    )
    accent_scale_colors[11] = accent_scale_colors[11].set(
        "oklch.c",
        min(
            max(
                accent_scale_colors[8].get("oklch.c"),
                accent_scale_colors[7].get("oklch.c"),
            ),
            accent_scale_colors[11].get("oklch.c"),
        ),
    )
    accent_scale_hex = [
        color.convert("srgb").to_string(hex=True) for color in accent_scale_colors
    ]
    accent_scale_wide_gamut = [to_oklch_string(color) for color in accent_scale_colors]
    accent_scale_alpha_hex = [
        get_alpha_color_srgb(color, background_hex) for color in accent_scale_hex
    ]
    accent_scale_alpha_wide_gamut_string = [
        get_alpha_color_p3(color, background_hex) for color in accent_scale_hex
    ]

    accent_contrast_color_hex = accent_contrast_color.convert("srgb").to_string(
        hex=True
    )

    gray_scale_hex = [
        color.convert("srgb").to_string(hex=True) for color in gray_scale_colors
    ]
    gray_scale_wide_gamut = [to_oklch_string(color) for color in gray_scale_colors]
    gray_scale_alpha_hex = [
        get_alpha_color_srgb(color, background_hex) for color in gray_scale_hex
    ]
    gray_scale_alpha_wide_gamut_string = [
        get_alpha_color_p3(color, background_hex) for color in gray_scale_hex
    ]

    accent_surface_hex = (
        get_alpha_color_srgb(accent_scale_hex[1], background_hex, 0.8)
        if appearance == "light"
        else get_alpha_color_srgb(accent_scale_hex[1], background_hex, 0.5)
    )

    accent_surface_wide_gamut_string = (
        get_alpha_color_p3(accent_scale_wide_gamut[1], background_hex, 0.8)
        if appearance == "light"
        else get_alpha_color_p3(accent_scale_wide_gamut[1], background_hex, 0.5)
    )

    return {
        "accentScale": accent_scale_hex,
        "accentScaleAlpha": accent_scale_alpha_hex,
        "accentScaleWideGamut": accent_scale_wide_gamut,
        "accentScaleAlphaWideGamut": accent_scale_alpha_wide_gamut_string,
        "accentContrast": accent_contrast_color_hex,
        "grayScale": gray_scale_hex,
        "grayScaleAlpha": gray_scale_alpha_hex,
        "grayScaleWideGamut": gray_scale_wide_gamut,
        "grayScaleAlphaWideGamut": gray_scale_alpha_wide_gamut_string,
        "graySurface": "#ffffffcc" if appearance == "light" else "rgba(0, 0, 0, 0.05)",
        "graySurfaceWideGamut": "color(display-p3 1 1 1 / 80%)"
        if appearance == "light"
        else "color(display-p3 0 0 0 / 5%)",
        "accentSurface": accent_surface_hex,
        "accentSurfaceWideGamut": accent_surface_wide_gamut_string,
        "background": background_hex,
    }


def get_step9_colors(
    scale: list[Color], accent_base_color: Color
) -> tuple[Color, Color]:
    """Get the step 9 colors.

    Args:
        scale: The scale of colors.
        accent_base_color: The accent base color.

    Returns:
        The step 9 colors.
    """
    reference_background_color = scale[0]
    distance = accent_base_color.delta_e(reference_background_color) * 100

    if distance < 25:
        return scale[8], get_text_color(scale[8])

    return accent_base_color, get_text_color(accent_base_color)


def get_button_hover_color(source: Color, scales: list[list[Color]]) -> Color:
    """Get the button hover color.

    Args:
        source: The source color.
        scales: The scales of colors.

    Returns:
        The button hover color.
    """
    L, C, H = source["lightness"], source["chroma"], source["hue"]

    new_L = L - 0.03 / (L + 0.1) if L > 0.4 else L + 0.03 / (L + 0.1)
    new_C = C * 0.93 if L > 0.4 and not math.isnan(H) else C
    button_hover_color = Color("oklch", [new_L, new_C, H])

    closest_color = button_hover_color
    min_distance = float("inf")

    for scale in scales:
        for color in scale:
            distance = button_hover_color.delta_e(color)
            if distance < min_distance:
                min_distance = distance
                closest_color = color

    button_hover_color["chroma"] = closest_color["chroma"]
    button_hover_color["hue"] = closest_color["hue"]
    return button_hover_color


def get_text_color(background: Color) -> Color:
    """Get the text color.

    Args:
        background: The background color.

    Returns:
        The text color.
    """
    white = Color("oklch", [1, 0, 0])

    if abs(white.contrast(background)) < 40:
        _, C, H = background["lightness"], background["chroma"], background["hue"]
        return Color("oklch", [0.25, max(0.08 * C, 0.04), H])

    return white


def get_alpha_color(
    target_rgb: list[float],
    background_rgb: list[float],
    rgb_precision: int,
    alpha_precision: int,
    target_alpha: float | None = None,
) -> tuple[float, float, float, float]:
    """Get the alpha color.

    Args:
        target_rgb: The target RGB.
        background_rgb: The background RGB.
        rgb_precision: The RGB precision.
        alpha_precision: The alpha precision.
        target_alpha: The target alpha.

    Raises:
        ValueError: If the color is undefined.

    Returns:
        The alpha color.
    """
    tr, tg, tb = [round(c * rgb_precision) for c in target_rgb]
    br, bg, bb = [round(c * rgb_precision) for c in background_rgb]

    if any(c is None for c in [tr, tg, tb, br, bg, bb]):
        raise ValueError("Color is undefined")

    desired_rgb = 0
    if tr > br or tg > bg or tb > bb:
        desired_rgb = rgb_precision

    alpha_r = (tr - br) / (desired_rgb - br)
    alpha_g = (tg - bg) / (desired_rgb - bg)
    alpha_b = (tb - bb) / (desired_rgb - bb)

    is_pure_gray = all(alpha == alpha_r for alpha in [alpha_r, alpha_g, alpha_b])

    if not target_alpha and is_pure_gray:
        v = desired_rgb / rgb_precision
        return v, v, v, alpha_r

    def clamp_rgb(n):
        return 0 if n is None else min(rgb_precision, max(0, n))

    def clamp_a(n):
        return 0 if n is None else min(alpha_precision, max(0, n))

    max_alpha = (
        target_alpha if target_alpha is not None else max(alpha_r, alpha_g, alpha_b)
    )
    A = clamp_a(math.ceil(max_alpha * alpha_precision)) / alpha_precision

    R = clamp_rgb(((br * (1 - A) - tr) / A) * -1)
    G = clamp_rgb(((bg * (1 - A) - tg) / A) * -1)
    B = clamp_rgb(((bb * (1 - A) - tb) / A) * -1)

    R, G, B = map(math.ceil, [R, G, B])

    blended_r = blend_alpha(R, A, br)
    blended_g = blend_alpha(G, A, bg)
    blended_b = blend_alpha(B, A, bb)

    if desired_rgb == 0:
        if tr <= br and tr != blended_r:
            R += 1 if tr > blended_r else -1
        if tg <= bg and tg != blended_g:
            G += 1 if tg > blended_g else -1
        if tb <= bb and tb != blended_b:
            B += 1 if tb > blended_b else -1

    if desired_rgb == rgb_precision:
        if tr >= br and tr != blended_r:
            R += 1 if tr > blended_r else -1
        if tg >= bg and tg != blended_g:
            G += 1 if tg > blended_g else -1
        if tb >= bb and tb != blended_b:
            B += 1 if tb > blended_b else -1

    R /= rgb_precision
    G /= rgb_precision
    B /= rgb_precision

    return R, G, B, A


def blend_alpha(foreground, alpha, background, _round=True) -> float:
    """Blend the alpha.

    Args:
        foreground: The foreground.
        alpha: The alpha.
        background: The background.
        _round: Whether to round the result.

    Returns:
        The blended alpha.
    """
    if _round:
        return round(background * (1 - alpha)) + round(foreground * alpha)

    return background * (1 - alpha) + foreground * alpha


def get_alpha_color_srgb(
    target_color: str, background_color: str, target_alpha: float | None = None
) -> str:
    """Get the alpha color in srgb.

    Args:
        target_color: The target color.
        background_color: The background color.
        target_alpha: The target alpha.

    Returns:
        The alpha color.
    """
    r, g, b, a = get_alpha_color(
        Color(target_color).convert("srgb").coords(),
        Color(background_color).convert("srgb").coords(),
        255,
        255,
        target_alpha,
    )
    return Color("srgb", [r, g, b], a).to_string(format="hex")


def get_alpha_color_p3(
    target_color: str, background_color: str, target_alpha: float | None = None
) -> str:
    """Get the alpha color in display-p3.

    Args:
        target_color: The target color.
        background_color: The background color.
        target_alpha: The target alpha.

    Returns:
        The alpha color.
    """
    r, g, b, a = get_alpha_color(
        Color(target_color).convert("display-p3").coords(),
        Color(background_color).convert("display-p3").coords(),
        255,
        1000,
        target_alpha,
    )
    return Color("display-p3", [r, g, b], a).to_string(precision=4)


def format_hex(s: str) -> str:
    """Format shortform hex to longform.

    Args:
        s: The hex color.

    Returns:
        The formatted hex color.
    """
    if not s.startswith("#"):
        return s

    if len(s) == 4:
        return f"#{s[1]}{s[1]}{s[2]}{s[2]}{s[3]}{s[3]}"

    if len(s) == 5:
        return f"#{s[1]}{s[1]}{s[2]}{s[2]}{s[3]}{s[3]}{s[4]}{s[4]}"

    return s


dark_mode_easing = [1, 0, 1, 0]
light_mode_easing = [0, 2, 0, 2]


def to_oklch_string(color: Color) -> str:
    """Convert a color to an oklch string for CSS.

    Args:
        color: The color to convert.

    Returns:
        The oklch string.
    """
    L = round(color["lightness"] * 100, 1)
    return f"oklch({L}% {color['chroma']:.4f} {color['hue']:.4f})"


def get_scale_from_color(
    source: Color, scales: dict[str, list[Color]], background_color: Color
) -> list[Color]:
    """Get a scale from a color.

    Args:
        source: The source color.
        scales: The scales of colors.
        background_color: The background color.

    Returns:
        The generated scale.
    """
    all_colors = []
    for name, scale in scales.items():
        for color in scale:
            distance = source.delta_e(color)
            all_colors.append({"scale": name, "distance": distance, "color": color})

    all_colors.sort(key=lambda x: x["distance"])

    # Remove non-unique scales
    closest_colors = []
    seen_scales = set()
    for color in all_colors:
        if color["scale"] not in seen_scales:
            closest_colors.append(color)
            seen_scales.add(color["scale"])

    # Handle gray scales
    gray_scale_names = ["gray", "mauve", "slate", "sage", "olive", "sand"]
    all_are_grays = all(color["scale"] in gray_scale_names for color in closest_colors)
    if not all_are_grays and closest_colors[0]["scale"] in gray_scale_names:
        while closest_colors[1]["scale"] in gray_scale_names:
            del closest_colors[1]

    color_a = closest_colors[0]
    color_b = closest_colors[1]

    # Calculate triangle sides
    a = color_b["distance"]
    b = color_a["distance"]
    c = color_a["color"].delta_e(color_b["color"])

    # Calculate angles
    cos_a = (b**2 + c**2 - a**2) / (2 * b * c)
    rad_a = math.acos(cos_a)
    sin_a = math.sin(rad_a)

    cos_b = (a**2 + c**2 - b**2) / (2 * a * c)
    rad_b = math.acos(cos_b)
    sin_b = math.sin(rad_b)

    # Calculate tangents
    tan_c1 = cos_a / sin_a
    tan_c2 = cos_b / sin_b

    # Calculate ratio
    ratio = max(0, tan_c1 / tan_c2) * 0.5

    # Mix scales
    scale_a = scales[color_a["scale"]]
    scale_b = scales[color_b["scale"]]
    scale = [
        Color.mix(scale_a[i], scale_b[i], ratio).convert("oklch") for i in range(12)
    ]

    # Find base color
    base_color = min(scale, key=lambda color: source.delta_e(color))

    # Adjust chroma ratio
    ratio_c = source.get("oklch.c") / base_color.get("oklch.c")

    # Modify hue and chroma of the scale
    for color in scale:
        color = color.set(
            "oklch.c", min(source.get("oklch.c") * 1.5, color.get("oklch.c") * ratio_c)
        )
        color = color.set("oklch.h", source.get("oklch.h"))

    # Handle light and dark modes
    if scale[0].get("oklch.l") > 0.5:  # Light mode
        lightness_scale = [color.get("oklch.l") for color in scale]
        background_l = max(0, min(1, background_color.get("oklch.l")))
        new_lightness_scale = transpose_progression_start(
            background_l, lightness_scale, light_mode_easing
        )
        new_lightness_scale = new_lightness_scale[1:]  # Remove the added step

        for i, lightness in enumerate(new_lightness_scale):
            scale[i] = scale[i].set("oklch.l", lightness)
    else:  # Dark mode
        ease = list(dark_mode_easing)
        reference_background_color_l = scale[0].get("oklch.l")
        background_color_l = max(0, min(1, background_color.get("oklch.l")))
        ratio_l = background_color_l / reference_background_color_l

        if ratio_l > 1:
            max_ratio = 1.5
            for i in range(len(ease)):
                meta_ratio = (ratio_l - 1) * (max_ratio / (max_ratio - 1))
                ease[i] = (  # type: ignore
                    0 if ratio_l > max_ratio else max(0, ease[i] * (1 - meta_ratio))
                )

        lightness_scale = [color.get("oklch.l") for color in scale]
        background_l = background_color.get("oklch.l")
        new_lightness_scale = transpose_progression_start(
            background_l, lightness_scale, ease
        )

        for i, lightness in enumerate(new_lightness_scale):
            scale[i] = scale[i].set("oklch.l", lightness)

    return scale


def transpose_progression_start(to: float, arr: list, curve: list) -> list[float]:
    """Transpose a progression to a new start point.

    Args:
        to: The new start point.
        arr: The progression.
        curve: The bezier curve.

    Returns:
        The transposed progression.
    """
    last_index = len(arr) - 1
    diff = arr[0] - to
    fn = bezier(*curve)
    return [n - diff * fn(1 - i / last_index) for i, n in enumerate(arr)]


def transpose_progression_end(
    to: float, arr: list[float], curve: list[float]
) -> list[float]:
    """Transpose a progression to a new end point.

    Args:
        to: The new end point.
        arr: The progression.
        curve: The bezier curve.

    Returns:
        The transposed progression.
    """
    last_index = len(arr) - 1
    diff = arr[-1] - to
    fn = bezier(*curve)
    return [n - diff * fn(i / last_index) for i, n in enumerate(arr)]
