"""Headless, opt-in personal layout drafts, independent of editor appearance."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

OptionValue = str | bool | int


@dataclass(frozen=True)
class Option:
    """A builder-owned choice; arbitrary properties cannot reach a widget."""

    key: str
    choices: tuple[OptionValue, ...]
    default: OptionValue

    def __post_init__(self):
        """Reject a choice definition with no valid default."""
        object.__setattr__(self, "choices", tuple(self.choices))
        if any(type(choice) not in (str, bool, int) for choice in self.choices):
            msg = "Option choices must be immutable string, boolean or integer values"
            raise ValueError(msg)
        if not self.key or not self.accepts(self.default):
            msg = "An option needs a key and a default from its choices"
            raise ValueError(msg)

    def accepts(self, value: OptionValue) -> bool:
        """Check both type and value so booleans cannot impersonate integers.

        Args:
            value: A candidate option value.

        Returns:
            Whether the value belongs to the allowed choices with the same type.
        """
        return any(
            type(value) is type(choice) and value == choice for choice in self.choices
        )


@dataclass(frozen=True)
class Widget:
    """Builder registration, including one renderer for content and previews."""

    key: str
    render: Callable[..., object]
    options: tuple[Option, ...] = ()
    min_width: int = 1
    max_width: int = 12
    min_height: int = 1
    max_height: int = 24

    def __post_init__(self):
        """Validate builder-owned sizing and option names."""
        object.__setattr__(self, "options", tuple(self.options))
        if not self.key or not callable(self.render):
            msg = "A widget needs a key and renderer"
            raise ValueError(msg)
        if any(
            type(value) is not int
            for value in (
                self.min_width,
                self.max_width,
                self.min_height,
                self.max_height,
            )
        ) or not (
            0 < self.min_width <= self.max_width
            and 0 < self.min_height <= self.max_height
        ):
            msg = "Widget size bounds must be positive and ordered"
            raise ValueError(msg)
        if len({option.key for option in self.options}) != len(self.options):
            msg = "Widget option keys must be unique"
            raise ValueError(msg)


@dataclass(frozen=True)
class Item:
    """Immutable presentation preferences for one widget instance."""

    id: str
    widget: str
    x: int = 0
    y: int = 0
    width: int = 4
    height: int = 3
    options: tuple[tuple[str, OptionValue], ...] = ()

    def __post_init__(self):
        """Detach preferences from mutable input collections."""
        object.__setattr__(self, "options", tuple(tuple(pair) for pair in self.options))


@dataclass(frozen=True)
class Preferences:
    """Presentation only; storage adapters must scope this to one user and page."""

    items: tuple[Item, ...]
    navigation: Literal["top", "left"] = "top"

    def __post_init__(self):
        """Detach the item order from a caller-owned list."""
        object.__setattr__(self, "items", tuple(self.items))


class Registry:
    """Validate complete candidate layouts before any draft is replaced."""

    def __init__(self, widgets: tuple[Widget, ...], columns: int = 12):
        """Register the exact widgets a builder allows on a page.

        Args:
            widgets: Builder-owned widget definitions.
            columns: Width of the logical layout grid.
        """
        if type(columns) is not int or columns < 1:
            msg = "Columns must be a positive integer"
            raise ValueError(msg)
        self._widgets = {widget.key: widget for widget in widgets}
        if len(self._widgets) != len(widgets):
            msg = "Widget keys must be unique"
            raise ValueError(msg)
        self.columns = columns

    def widget(self, key: str) -> Widget:
        """Return a registered renderer and its allowed settings.

        Args:
            key: Builder-defined widget key.

        Returns:
            The registered widget.

        Raises:
            ValueError: The widget is not opted into this page.
        """
        try:
            return self._widgets[key]
        except KeyError as error:
            msg = f"Widget is not registered: {key}"
            raise ValueError(msg) from error

    def validate(self, preferences: Preferences) -> None:
        """Reject unsupported navigation, settings, overlaps and out-of-bounds items.

        Args:
            preferences: A complete candidate layout.

        Raises:
            ValueError: The candidate violates the page's builder-owned contract.
        """
        if preferences.navigation not in ("top", "left"):
            msg = "Navigation must be top or left"
            raise ValueError(msg)
        ids: set[str] = set()
        occupied: list[Item] = []
        for item in preferences.items:
            if not item.id or item.id in ids:
                msg = "Widget instance IDs must be nonempty and unique"
                raise ValueError(msg)
            ids.add(item.id)
            widget = self.widget(item.widget)
            if any(
                type(value) is not int
                for value in (item.x, item.y, item.width, item.height)
            ):
                msg = "Widget geometry must use integers"
                raise ValueError(msg)
            if not (
                item.x >= 0
                and item.y >= 0
                and widget.min_width <= item.width <= widget.max_width
                and widget.min_height <= item.height <= widget.max_height
                and item.x + item.width <= self.columns
            ):
                msg = "Widget geometry is outside the allowed bounds"
                raise ValueError(msg)
            options = {option.key: option for option in widget.options}
            seen: set[str] = set()
            for key, value in item.options:
                if key in seen or key not in options or not options[key].accepts(value):
                    msg = f"Unsupported widget option: {key}"
                    raise ValueError(msg)
                seen.add(key)
            if any(
                item.x < other.x + other.width
                and other.x < item.x + item.width
                and item.y < other.y + other.height
                and other.y < item.y + item.height
                for other in occupied
            ):
                msg = "Widget instances cannot overlap"
                raise ValueError(msg)
            occupied.append(item)


class Draft:
    """Stage presentation changes without invoking renderers or writing storage."""

    def __init__(self, registry: Registry, saved: Preferences, defaults: Preferences):
        """Start an isolated edit transaction.

        Args:
            registry: Builder-owned page registration.
            saved: Current personal preferences.
            defaults: Builder's default layout used by Reset.
        """
        registry.validate(saved)
        registry.validate(defaults)
        self._registry = registry
        self._saved = saved
        self._defaults = defaults
        self._current = saved
        self._active = True

    @property
    def current(self) -> Preferences:
        """The immutable draft for normal content and preview rendering."""
        return self._current

    @property
    def dirty(self) -> bool:
        """Whether the current draft differs from saved preferences."""
        return self._current != self._saved

    def stage(self, preferences: Preferences) -> None:
        """Atomically replace the draft after validating the complete candidate.

        Args:
            preferences: Candidate from drag, resize, settings, or keyboard commands.

        Raises:
            RuntimeError: Save or Cancel already closed this draft.
            ValueError: Candidate violates builder-owned layout rules.
        """
        self._check_active()
        self._registry.validate(preferences)
        self._current = preferences

    def reset(self) -> None:
        """Stage builder defaults; Cancel can still restore saved preferences."""
        self.stage(self._defaults)

    def save(self) -> Preferences:
        """Prepare a snapshot for caller-owned personal storage, keeping edits active.

        Returns:
            Validated presentation preferences; this method performs no writes.
        """
        self._check_active()
        return self._current

    def confirm_save(self, snapshot: Preferences) -> None:
        """Close only after personal persistence succeeds for the current snapshot.

        Args:
            snapshot: The snapshot successfully persisted by the caller.

        Raises:
            ValueError: The draft changed while the snapshot was being saved.
        """
        self._check_active()
        if snapshot != self._current:
            msg = "The draft changed while saving; save the current draft"
            raise ValueError(msg)
        self._saved = snapshot
        self._active = False

    def cancel(self) -> Preferences:
        """Discard staged changes and close the draft.

        Returns:
            The original saved personal preferences.
        """
        self._check_active()
        self._current = self._saved
        self._active = False
        return self._saved

    def _check_active(self) -> None:
        """Reject commands on a completed transaction."""
        if not self._active:
            msg = "This draft is closed; start a new edit session"
            raise RuntimeError(msg)
