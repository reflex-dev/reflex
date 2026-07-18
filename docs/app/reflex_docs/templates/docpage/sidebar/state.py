"""The state of the sidebar component."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class SideBarBase:
    """Base class for the Side bar."""

    # The name to display in the sidebar.
    names: str = ""

    alt_name_for_next_prev: str = ""

    # The link to navigate to when the item is clicked.
    link: str = ""

    # The children items.
    children: list[SideBarItem] = field(default_factory=list)

    # Whether the item is a category. Occurs if a single item is at the top level of the sidebar for aesthetics.
    outer: bool = False

    def __post_init__(self):
        """Post initialization processing."""
        if self.link:
            # Pre-normalize the link so we don't have to do it in memo'd functions.
            self.link = self.link.replace("_", "-").rstrip("/") + "/"


class SideBarItem(SideBarBase):
    """A single item in the sidebar."""

    ...


class SideBarSection(SideBarBase):
    """A section in the sidebar."""

    ...
