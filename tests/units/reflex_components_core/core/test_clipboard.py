"""Tests for clipboard target selection with immutable children."""

import pytest
from reflex_base.vars.base import Var
from reflex_components_core.core.clipboard import Clipboard
from reflex_components_core.el.elements.forms import Input

import reflex as rx


def test_clipboard_assigns_missing_ids_without_mutating_children():
    """Generated targets reach rendered children without changing shared inputs."""
    unnamed = Input.create()
    named = Input.create(id="existing-target")
    original_render = unnamed.render()

    clipboard = Clipboard.create(unnamed, named, on_paste=rx.console_log("paste"))
    generated, preserved = clipboard.children

    assert unnamed.id is None
    assert unnamed.render() == original_render
    assert generated is not unnamed
    assert isinstance(generated, Input)
    assert isinstance(generated.id, str)
    assert generated.id.startswith("clipboard_")
    assert preserved is named
    assert clipboard._render().props["key"].equals(Var.create([generated.id, named.id]))
    assert f'id:"{generated.id}"' in generated.render()["props"]
    assert "usePasteHandler" in " ".join(str(hook) for hook in clipboard.add_hooks())


def test_clipboard_reused_child_gets_independent_targets():
    """Reusing an unnamed child does not share generated IDs across clipboards."""
    child = Input.create()
    first = Clipboard.create(child)
    second = Clipboard.create(child)
    first_child = first.children[0]
    second_child = second.children[0]

    assert child.id is None
    assert isinstance(first_child, Input)
    assert isinstance(second_child, Input)
    assert first_child.id != second_child.id
    assert first._render().props["key"].equals(Var.create([first_child.id]))
    assert second._render().props["key"].equals(Var.create([second_child.id]))


@pytest.mark.parametrize("targets", [[], ["external-target"]])
def test_clipboard_explicit_targets_preserve_children(targets: list[str]):
    """Explicit targets bypass ID generation, including an empty target list.

    Args:
        targets: The explicit clipboard targets.
    """
    child = Input.create()
    clipboard = Clipboard.create(child, targets=targets)

    assert clipboard.children[0] is child
    assert child.id is None
    assert clipboard._render().props["key"].equals(Var.create(targets))


def test_clipboard_without_children_targets_document():
    """A clipboard without children keeps an empty target list for the document."""
    clipboard = Clipboard.create()

    assert not clipboard.children
    assert clipboard._render().props["key"].equals(Var.create([]))
