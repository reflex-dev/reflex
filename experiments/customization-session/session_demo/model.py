"""Session-only adapter around the real Python customization draft engine."""

from collections.abc import Callable
from dataclasses import replace

from reflex_components_internal.experimental.customization import (
    Draft,
    Item,
    Preferences,
    Registry,
)

DEFAULTS = Preferences((
    Item("trend", "trend", y=0, width=12, height=4),
    Item("accounts", "accounts", y=4, width=12, height=4),
    Item("search", "search", y=8, width=12, height=2),
))


class Session:
    """One browser session's personal view; no database or business writes."""

    def __init__(self, registry: Registry):
        """Initialize independent session preferences and the builder registry."""
        self.registry = registry
        self.saved = DEFAULTS
        self.draft: Draft | None = None
        self.engine_calls = 0
        self.last_operation = "Session defaults"

    @property
    def current(self) -> Preferences:
        """The active draft or saved session view."""
        return self.draft.current if self.draft else self.saved

    def begin(self) -> None:
        """Begin an actual Python Draft transaction."""
        if self.draft is None:
            self.draft = Draft(self.registry, self.saved, DEFAULTS)
            self.engine_calls += 1
            self.last_operation = "Draft.begin"

    def stage(self, candidate: Preferences) -> None:
        """Validate an atomic candidate through the actual draft engine."""
        if self.draft is None:
            msg = "Open Customize first"
            raise ValueError(msg)
        self.draft.stage(candidate)
        self.engine_calls += 1
        self.last_operation = "Draft.stage"

    def move(self, item_id: str, offset: int) -> None:
        """Move one instance before or after its neighbor without dense packing."""
        if offset not in (-1, 1):
            msg = "Move offset must name an adjacent position"
            raise ValueError(msg)
        items = list(self.current.items)
        index = next(i for i, item in enumerate(items) if item.id == item_id)
        destination = index + offset
        if destination < 0 or destination >= len(items):
            return
        first_index, second_index = sorted((index, destination))
        first, second = items[first_index], items[second_index]
        gap = second.y - first.y - first.height
        items[first_index] = replace(second, y=first.y)
        items[second_index] = replace(first, y=first.y + second.height + gap)
        self.stage(replace(self.current, items=tuple(items)))

    def size(self, item_id: str) -> None:
        """Toggle explicit half/full logical width without changing item order."""
        items = tuple(
            replace(item, width=6 if item.width == 12 else 12)
            if item.id == item_id
            else item
            for item in self.current.items
        )
        self.stage(replace(self.current, items=items))

    def option(self, item_id: str, key: str, value: str | int | bool) -> None:
        """Stage only builder-allowlisted settings."""
        items = tuple(
            replace(item, options=((key, value),)) if item.id == item_id else item
            for item in self.current.items
        )
        self.stage(replace(self.current, items=items))

    def navigation(self, value: str) -> None:
        """Stage one of the builder-enabled navigation orientations."""
        self.stage(replace(self.current, navigation=value))

    def reset(self) -> None:
        """Stage defaults while retaining the ability to Cancel."""
        if self.draft is None:
            msg = "Open Customize first"
            raise ValueError(msg)
        self.draft.reset()
        self.engine_calls += 1
        self.last_operation = "Draft.reset"

    def cancel(self) -> None:
        """Discard the draft and restore this session's saved view."""
        if self.draft is None:
            msg = "Open Customize first"
            raise ValueError(msg)
        self.draft.cancel()
        self.draft = None
        self.engine_calls += 1
        self.last_operation = "Draft.cancel"

    def save(self, persist: Callable[[Preferences], None] | None = None) -> None:
        """Save to this session's memory, retaining edits if persistence fails.

        Args:
            persist: Optional test-only failure injection; not exposed in the UI.
        """
        if self.draft is None:
            msg = "Open Customize first"
            raise ValueError(msg)
        snapshot = self.draft.save()
        if persist:
            persist(snapshot)
        self.draft.confirm_save(snapshot)
        self.saved = snapshot
        self.draft = None
        self.engine_calls += 2
        self.last_operation = "Draft.save → Draft.confirm_save"

    def add(self, key: str) -> None:
        """Append a builder-registered widget without repacking existing geometry."""
        self.registry.widget(key)
        items = self.current.items
        suffix = 1
        while any(item.id == f"{key}-{suffix}" for item in items):
            suffix += 1
        y = max((item.y + item.height for item in items), default=0)
        item = Item(
            f"{key}-{suffix}", key, y=y, width=12, height=2 if key == "search" else 4
        )
        self.stage(replace(self.current, items=(*items, item)))
