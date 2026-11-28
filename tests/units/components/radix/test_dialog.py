"""Tests for the Radix primitive dialog."""

from collections.abc import Callable

import pytest
from reflex_base.components.component import Component
from reflex_components_core.el.elements.forms import Button
from reflex_components_core.el.elements.typography import Li, Ul
from reflex_components_radix.primitives.dialog import (
    DialogClose,
    DialogContent,
    DialogOverlay,
    DialogPortal,
    DialogRoot,
    DialogTitle,
    DialogTrigger,
)


def _trigger() -> Component:
    return DialogTrigger.create(Button.create("Open"), as_child=True)


@pytest.mark.parametrize(
    "children",
    [
        pytest.param(
            lambda: [
                _trigger(),
                DialogPortal.create(
                    DialogOverlay.create(),
                    DialogContent.create(DialogTitle.create("Title")),
                ),
            ],
            id="portal",
        ),
        pytest.param(
            lambda: [
                _trigger(),
                DialogOverlay.create(),
                DialogContent.create(DialogTitle.create("Title")),
            ],
            id="in_place",
        ),
        pytest.param(
            lambda: [
                Ul.create(Li.create(_trigger())),
                DialogContent.create(DialogClose.create()),
                DialogOverlay.create(),
            ],
            id="nested_trigger",
        ),
    ],
)
def test_dialog_parts_inside_root(children: Callable[[], list[Component]]) -> None:
    """Radix only needs the parts inside the root, with or without a portal."""
    parts = children()
    root = DialogRoot.create(*parts)

    assert root.children == parts
