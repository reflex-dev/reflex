"""Components for displaying the Reflex watermark."""

from reflex.components.component import ComponentNamespace
from reflex.components.core.colors import color
from reflex.components.core.cond import color_mode_cond
from reflex.components.el.elements.media import Path, Rect, Svg
from reflex.components.radix.themes.layout.box import Box
from reflex.components.radix.themes.typography.text import Text
from reflex.style import Style


class WatermarkLogo(Svg):
    """A simple Reflex logo SVG with only the letter R."""

    @classmethod
    def create(cls):
        """Create the simple Reflex logo SVG.

        Returns:
            The simple Reflex logo SVG.
        """
        return super().create(
            Rect.create(width="16", height="16", rx="2", fill="#6E56CF"),
            Path.create(d="M10 9V13H12V9H10Z", fill="white"),
            Path.create(d="M4 3V13H6V9H10V7H6V5H10V7H12V3H4Z", fill="white"),
            width="16",
            height="16",
            viewBox="0 0 16 16",
            xmlns="http://www.w3.org/2000/svg",
        )

    def add_style(self):
        """Add the style to the component.

        Returns:
            The style of the component.
        """
        return Style(
            {
                "fill": "white",
            }
        )


class WatermarkLabel(Text):
    """A label that displays the Reflex watermark."""

    @classmethod
    def create(cls):
        """Create the watermark label.

        Returns:
            The watermark label.
        """
        return super().create("Built with Reflex!")

    def add_style(self):
        """Add the style to the component.

        Returns:
            The style of the component.
        """
        return Style(
            {
                "color": color("slate", 1),
                "font-weight": "600",
                "font-family": "'Instrument Sans', sans-serif",
                "font-size": "0.875rem",
                "line-height": "1rem",
                "letter-spacing": "-0.00656rem",
            }
        )


class WatermarkBadge(Box):
    """A badge that displays the Reflex watermark."""

    @classmethod
    def create(cls):
        """Create the watermark badge.

        Returns:
            The watermark badge.
        """
        return super().create(
            WatermarkLogo.create(),
            WatermarkLabel.create(),
            width="auto",
            padding="0.375rem",
            align="center",
            text_align="center",
        )

    def add_style(self):
        """Add the style to the component.

        Returns:
            The style of the component.
        """
        return Style(
            {
                "position": "fixed",
                "bottom": "1rem",
                "right": "1rem",
                "display": "flex",
                "flex-direction": "row",
                "gap": "0.375rem",
                "align-items": "center",
                "width": "auto",
                "border-radius": "0.5rem",
                "color": color_mode_cond("#E5E7EB", "#27282B"),
                "border": color_mode_cond("1px solid #27282B", "1px solid #E5E7EB"),
                "background-color": color_mode_cond("#151618", "#FCFCFD"),
                "padding": "0.375rem",
                "transition": "background-color 0.2s ease-in-out",
                "box-shadow": "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
                "z-index": "9998",
                "cursor": "pointer",
            }
        )


class WatermarkNamespace(ComponentNamespace):
    """Watermark components namespace."""

    __call__ = staticmethod(WatermarkBadge.create)
    label = staticmethod(WatermarkLabel.create)
    logo = staticmethod(WatermarkLogo.create)


watermark = WatermarkNamespace()
