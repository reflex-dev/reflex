"""The look of a skeleton: a pulsing block in the place of what is loading."""

from __future__ import annotations

from reflex_components_ui import tokens
from reflex_components_ui.style import ComponentStyles, keyframes, unchecked

_PULSE = keyframes({
    "from": {"background_color": tokens.gray.a[3]},
    "to": {"background_color": tokens.gray.a[4]},
})

# Most of it is important, as in Radix Themes: a skeleton rendered as its
# child takes the look of the skeleton over the one of the child, wherever
# the styles of the child come from.
SKELETON: ComponentStyles = {
    "base": unchecked({
        "animation_name": _PULSE,
        "animation_duration": "1000ms !important",
        "animation_timing_function": "ease !important",
        "animation_delay": "0s !important",
        "animation_iteration_count": "infinite !important",
        "animation_direction": "alternate-reverse !important",
        "animation_fill_mode": "none !important",
        "animation_play_state": "running !important",
        "background_image": "none !important",
        "background_clip": "border-box !important",
        "border_style": "none !important",
        "border_width": "medium !important",
        "border_color": "currentcolor !important",
        "box_shadow": "none !important",
        "box_decoration_break": "clone !important",
        "color": "transparent !important",
        "outline_style": "none !important",
        "outline_width": "medium !important",
        "outline_color": "currentcolor !important",
        "pointer_events": "none !important",
        "user_select": "none !important",
        "cursor": "default !important",
        "_before": {"visibility": "hidden !important"},
        "_after": {"visibility": "hidden !important"},
        # Without anything to stand in for, a line of its own.
        ":empty": {"display": "block", "height": tokens.space[3]},
    }),
    "variants": {
        # Unless the element the skeleton is rendered as has corners of its
        # own, which it keeps.
        "_rounded": {"true": {"border_radius": tokens.radius[1]}},
        # Around text rather than an element. The metrics of Arial give the
        # background of a line of text a better height.
        "_inline": {
            "true": {
                "line_height": 0,
                "font_family": "Arial, sans-serif !important",
            }
        },
    },
}
