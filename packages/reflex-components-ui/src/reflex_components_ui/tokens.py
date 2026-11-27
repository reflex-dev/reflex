"""The design tokens of the rx.ui components, as values of a style.

A token is the CSS ``var()`` of a custom property, as a plain string, so it
goes wherever a CSS value does: the ``style`` of any component, the style
table of an rx.ui component, or inside a larger value such as
``f"calc({tokens.space[4]} * 2)"``.

    rx.ui.tokens.space[4]           "var(--space-4)"
    rx.ui.tokens.accent[9]          "var(--accent-9)"
    rx.ui.tokens.accent.a[3]        "var(--accent-a3)"
    rx.ui.tokens.accent.contrast    "var(--accent-contrast)"
    rx.ui.tokens.font_weight.bold   "var(--font-weight-bold)"

The names and the values are the ones of Radix Themes. A step that does not
exist and a name that is misspelt are errors to a type checker, and raise a
``TokenError`` that lists what exists.
"""

from __future__ import annotations

from typing import Literal, NoReturn

from reflex_base.utils.exceptions import ReflexError

from reflex_components_ui.style.lower import _suggest

Step6 = Literal[1, 2, 3, 4, 5, 6]
Step9 = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9]
Step12 = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

LiteralColorScale = Literal[
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
    "gold",
    "bronze",
    "mauve",
    "slate",
    "sage",
    "olive",
    "sand",
]


class TokenError(ReflexError, AttributeError, LookupError):
    """A design token that does not exist."""


class _Tokens:
    """A group of tokens: named ones as attributes, and steps by number.

    Attributes:
        _path: How an app refers to the group, which starts an error message.
        _steps: The token of each step, the first one being step 1.
    """

    _path: str
    _steps: tuple[str, ...]

    def __init__(self, path: str, prefix: str, steps: int = 0, infix: str = ""):
        """Name the steps of the group.

        Args:
            path: How an app refers to the group.
            prefix: What the custom properties of the group start with.
            steps: How many steps the group has.
            infix: What comes between the prefix and the number of a step.
        """
        self._path = path
        self._steps = tuple([
            f"var(--{prefix}-{infix}{step})" for step in range(1, steps + 1)
        ])

    def _step(self, step: int) -> str:
        """Get the token of a step.

        Args:
            step: The number of the step.

        Returns:
            The token.

        Raises:
            TokenError: If the group has no such step.
        """
        # A bool is an int, and a negative number would count from the end.
        if step.__class__ is int and 0 < step <= len(self._steps):
            return self._steps[step - 1]
        if self._steps:
            msg = (
                f"{self._path} has no step {step!r}. Its steps are 1 to "
                f"{len(self._steps)}."
            )
        else:
            msg = (
                f"{self._path} has no steps. Its tokens are "
                f"{', '.join(self._names())}."
            )
        raise TokenError(msg)

    def _names(self) -> list[str]:
        """List the named tokens of the group.

        Returns:
            Their names, sorted.
        """
        return sorted([name for name in vars(self) if name[0] != "_"])

    def __getitem__(self, step: int) -> str:
        """Get the token of a step.

        Args:
            step: The number of the step.

        Returns:
            The token.
        """
        return self._step(step)

    def __getattr__(self, name: str) -> NoReturn:
        """Fail on a token the group does not have.

        Args:
            name: The name that was asked for.

        Raises:
            AttributeError: For a private name, which python and the standard
                library probe and no token has.
            TokenError: For any other name: python only gets here for a
                missing one.
        """
        if name[:1] == "_":
            raise AttributeError(name)
        names = self._names()
        msg = f'{self._path} has no token "{name}".{_suggest(name, names)}'
        if names:
            msg += f" Its tokens are {', '.join(names)}"
            if self._steps:
                msg += f", and the steps [1] to [{len(self._steps)}]"
            msg += "."
        else:
            msg += f" Its tokens are the steps [1] to [{len(self._steps)}]."
        raise TokenError(msg)


class _Steps6(_Tokens):
    """Tokens of a scale of six steps."""

    def __getitem__(self, step: Step6) -> str:
        """Get the token of a step.

        Args:
            step: The number of the step, from 1 to 6.

        Returns:
            The token.
        """
        return self._step(step)


class _Steps9(_Tokens):
    """Tokens of a scale of nine steps."""

    def __getitem__(self, step: Step9) -> str:
        """Get the token of a step.

        Args:
            step: The number of the step, from 1 to 9.

        Returns:
            The token.
        """
        return self._step(step)


class _Steps12(_Tokens):
    """Tokens of a scale of twelve steps."""

    def __getitem__(self, step: Step12) -> str:
        """Get the token of a step.

        Args:
            step: The number of the step, from 1 to 12.

        Returns:
            The token.
        """
        return self._step(step)


class _Radius(_Steps6):
    """The radius scale, and what the radius of a theme sets.

    Attributes:
        factor: What the radius of the theme multiplies every step by.
        full: The radius of a pill, when the radius of the theme is full.
        thumb: The radius of the thumb of a switch or a slider.
    """

    def __init__(self):
        """Name the tokens."""
        super().__init__("rx.ui.tokens.radius", "radius", 6)
        self.factor = "var(--radius-factor)"
        self.full = "var(--radius-full)"
        self.thumb = "var(--radius-thumb)"


class _FontWeight(_Tokens):
    """The font weights.

    Attributes:
        light: The light weight.
        regular: The weight of body text.
        medium: The weight of labels and buttons.
        bold: The weight of headings.
    """

    def __init__(self):
        """Name the tokens."""
        super().__init__("rx.ui.tokens.font_weight", "font-weight")
        self.light = "var(--font-weight-light)"
        self.regular = "var(--font-weight-regular)"
        self.medium = "var(--font-weight-medium)"
        self.bold = "var(--font-weight-bold)"


class _Alpha(_Steps12):
    """The translucent steps of a color scale."""


class _AlphaScale(_Tokens):
    """A scale that only has translucent steps: black and white.

    Attributes:
        a: The translucent steps.
    """

    def __init__(self, name: str):
        """Name the tokens.

        Args:
            name: The name of the scale.
        """
        path = f"rx.ui.tokens.{name}"
        super().__init__(path, name)
        self.a = _Alpha(f"{path}.a", name, 12, "a")


class _Focus(_Steps12):
    """The colors of a focus ring, which follow the accent.

    Attributes:
        a: The translucent steps.
    """

    def __init__(self):
        """Name the tokens."""
        super().__init__("rx.ui.tokens.focus", "focus", 12)
        self.a = _Alpha("rx.ui.tokens.focus.a", "focus", 12, "a")


class _Scale(_Steps12):
    """A color scale: twelve steps, from a background to high-contrast text.

    Attributes:
        a: The translucent steps.
        contrast: The color of text on step 9.
        surface: The background of a translucent surface.
        indicator: The color of an indicator, such as a checked checkbox.
        track: The color of a track, such as the filled part of a slider.
    """

    def __init__(self, path: str, name: str):
        """Name the tokens.

        Args:
            path: How an app refers to the scale.
            name: The name of the scale.
        """
        super().__init__(path, name, 12)
        self.a = _Alpha(f"{path}.a", name, 12, "a")
        self.contrast = f"var(--{name}-contrast)"
        self.surface = f"var(--{name}-surface)"
        self.indicator = f"var(--{name}-indicator)"
        self.track = f"var(--{name}-track)"


class _Color(_Tokens):
    """The colors with a role of their own.

    Attributes:
        background: The background of the page.
        overlay: The backdrop of a dialog.
        panel: The background of a panel, as the theme sets it.
        panel_solid: The background of an opaque panel.
        panel_translucent: The background of a see-through panel.
        panel_if_solid: The opaque background when the theme sets it, and
            nothing otherwise.
        surface: The background of a form control.
        transparent: A color that paints nothing.
    """

    def __init__(self):
        """Name the tokens."""
        super().__init__("rx.ui.tokens.color", "color")
        self.background = "var(--color-background)"
        self.overlay = "var(--color-overlay)"
        self.panel = "var(--color-panel)"
        self.panel_solid = "var(--color-panel-solid)"
        self.panel_translucent = "var(--color-panel-translucent)"
        self.panel_if_solid = "var(--color-panel-if-solid)"
        self.surface = "var(--color-surface)"
        self.transparent = "var(--color-transparent)"


class _Cursor(_Tokens):
    """The cursor over each kind of control.

    Attributes:
        button: Over a button.
        checkbox: Over a checkbox.
        disabled: Over a disabled control.
        link: Over a link.
        menu_item: Over an item of a menu.
        radio: Over a radio button.
        slider_thumb: Over the thumb of a slider.
        slider_thumb_active: Over the thumb of a slider while it is dragged.
        switch: Over a switch.
    """

    def __init__(self):
        """Name the tokens."""
        super().__init__("rx.ui.tokens.cursor", "cursor")
        self.button = "var(--cursor-button)"
        self.checkbox = "var(--cursor-checkbox)"
        self.disabled = "var(--cursor-disabled)"
        self.link = "var(--cursor-link)"
        self.menu_item = "var(--cursor-menu-item)"
        self.radio = "var(--cursor-radio)"
        self.slider_thumb = "var(--cursor-slider-thumb)"
        self.slider_thumb_active = "var(--cursor-slider-thumb-active)"
        self.switch = "var(--cursor-switch)"


class _Panel(_Tokens):
    """What the panel background of a theme sets.

    Attributes:
        backdrop_filter: The backdrop filter of a panel.
        solid: Empty when panels are opaque, and invalid otherwise: a value
            that starts with it only applies to an opaque panel.
    """

    def __init__(self):
        """Name the tokens."""
        super().__init__("rx.ui.tokens.panel", "panel")
        self.backdrop_filter = "var(--backdrop-filter-panel)"
        self.solid = "var(--panel-solid)"


class _Default(_Tokens):
    """The typography of body text.

    Attributes:
        font_family: The font family.
        font_size: The font size.
        font_style: The font style.
        font_weight: The font weight.
        line_height: The line height.
        letter_spacing: The letter spacing.
        leading_trim_start: The space to take off above the first line.
        leading_trim_end: The space to take off below the last line.
    """

    def __init__(self):
        """Name the tokens."""
        super().__init__("rx.ui.tokens.default", "default")
        self.font_family = "var(--default-font-family)"
        self.font_size = "var(--default-font-size)"
        self.font_style = "var(--default-font-style)"
        self.font_weight = "var(--default-font-weight)"
        self.line_height = "var(--default-line-height)"
        self.letter_spacing = "var(--default-letter-spacing)"
        self.leading_trim_start = "var(--default-leading-trim-start)"
        self.leading_trim_end = "var(--default-leading-trim-end)"


class _Heading(_Tokens):
    """The typography of headings.

    Attributes:
        font_family: The font family.
        font_size_adjust: What the font size is multiplied by.
        font_style: The font style.
        letter_spacing: The letter spacing, added to the one of the size.
        leading_trim_start: The space to take off above the first line.
        leading_trim_end: The space to take off below the last line.
        line_height: The line height of each font size.
    """

    def __init__(self):
        """Name the tokens."""
        super().__init__("rx.ui.tokens.heading", "heading")
        self.font_family = "var(--heading-font-family)"
        self.font_size_adjust = "var(--heading-font-size-adjust)"
        self.font_style = "var(--heading-font-style)"
        self.letter_spacing = "var(--heading-letter-spacing)"
        self.leading_trim_start = "var(--heading-leading-trim-start)"
        self.leading_trim_end = "var(--heading-leading-trim-end)"
        self.line_height = _Steps9(
            "rx.ui.tokens.heading.line_height", "heading-line-height", 9
        )


class _Inline(_Tokens):
    """The typography of an inline element: strong, em or quote.

    Attributes:
        font_family: The font family.
        font_size_adjust: What the font size is multiplied by.
        font_style: The font style.
        font_weight: The font weight.
        letter_spacing: The letter spacing, added to the one of the size.
    """

    def __init__(self, name: str):
        """Name the tokens.

        Args:
            name: The element.
        """
        super().__init__(f"rx.ui.tokens.{name}", name)
        self.font_family = f"var(--{name}-font-family)"
        self.font_size_adjust = f"var(--{name}-font-size-adjust)"
        self.font_style = f"var(--{name}-font-style)"
        self.font_weight = f"var(--{name}-font-weight)"
        self.letter_spacing = f"var(--{name}-letter-spacing)"


class _Code(_Inline):
    """The typography of code.

    Attributes:
        padding_top: The padding above inline code.
        padding_bottom: The padding below inline code.
        padding_left: The padding before inline code.
        padding_right: The padding after inline code.
    """

    def __init__(self):
        """Name the tokens."""
        super().__init__("code")
        self.padding_top = "var(--code-padding-top)"
        self.padding_bottom = "var(--code-padding-bottom)"
        self.padding_left = "var(--code-padding-left)"
        self.padding_right = "var(--code-padding-right)"


class _Tab(_Tokens):
    """The spacing that keeps a tab the same width when it becomes bold.

    Attributes:
        active_letter_spacing: The letter spacing of the selected tab.
        active_word_spacing: The word spacing of the selected tab.
        inactive_letter_spacing: The letter spacing of the other tabs.
        inactive_word_spacing: The word spacing of the other tabs.
    """

    def __init__(self):
        """Name the tokens."""
        super().__init__("rx.ui.tokens.tab", "tab")
        self.active_letter_spacing = "var(--tab-active-letter-spacing)"
        self.active_word_spacing = "var(--tab-active-word-spacing)"
        self.inactive_letter_spacing = "var(--tab-inactive-letter-spacing)"
        self.inactive_word_spacing = "var(--tab-inactive-word-spacing)"


# The scale every size is multiplied by.
scaling = "var(--scaling)"

space = _Steps9("rx.ui.tokens.space", "space", 9)
radius = _Radius()
shadow = _Steps6("rx.ui.tokens.shadow", "shadow", 6)

font_size = _Steps9("rx.ui.tokens.font_size", "font-size", 9)
line_height = _Steps9("rx.ui.tokens.line_height", "line-height", 9)
letter_spacing = _Steps9("rx.ui.tokens.letter_spacing", "letter-spacing", 9)
font_weight = _FontWeight()
default = _Default()
heading = _Heading()
code = _Code()
strong = _Inline("strong")
em = _Inline("em")
quote = _Inline("quote")
tab = _Tab()

# The accent and the gray of the theme the element is in.
accent = _Scale("rx.ui.tokens.accent", "accent")
gray = _Scale("rx.ui.tokens.gray", "gray")
focus = _Focus()
black = _AlphaScale("black")
white = _AlphaScale("white")
color = _Color()
panel = _Panel()
cursor = _Cursor()

_SCALES: dict[str, _Scale] = {}


def scale(name: LiteralColorScale) -> _Scale:
    """Get a color scale by its name, whatever the theme.

    Args:
        name: The name of the scale, such as ``"ruby"``.

    Returns:
        The tokens of the scale.

    Raises:
        TokenError: If there is no such scale.
    """
    found = _SCALES.get(name)
    if found is None:
        scales = LiteralColorScale.__args__
        if name == "accent" or name == "gray":
            msg = (
                f'rx.ui.tokens.scale: "{name}" is not a color scale of its own, '
                f"but the {name} of the theme: use rx.ui.tokens.{name}."
            )
            raise TokenError(msg)
        if name not in scales:
            shown = f'"{name}"' if isinstance(name, str) else repr(name)
            suggestion = _suggest(name, scales) if isinstance(name, str) else ""
            msg = (
                f"rx.ui.tokens.scale: unknown color scale {shown}.{suggestion} "
                f"The scales are {', '.join(sorted(scales))}."
            )
            raise TokenError(msg)
        found = _SCALES[name] = _Scale(f'rx.ui.tokens.scale("{name}")', name)
    return found
