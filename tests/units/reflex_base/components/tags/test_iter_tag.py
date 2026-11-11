"""Tests for the tag that renders the children of rx.foreach."""

import logging

import pytest
from reflex_base.environment import environment

import reflex as rx
from reflex.state import BaseState


class LoopState(BaseState):
    """A state with a list to loop over."""

    items: list[str] = ["alpha", "beta", "gamma"]

    @rx.event
    def record(self, item: str):
        """Record a lifecycle event of an item.

        Args:
            item: The item whose row mounted or unmounted.
        """


def _key_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The warnings about an unkeyed foreach logged so far.

    Args:
        caplog: The log capture fixture.

    Returns:
        The messages of the captured warnings.
    """
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
        and "keyed by its index" in record.getMessage()
    ]


@pytest.fixture
def compiling(monkeypatch: pytest.MonkeyPatch):
    """Evaluate pages as a frontend compile does.

    Args:
        monkeypatch: The monkeypatch fixture.
    """
    monkeypatch.delenv(environment.REFLEX_SKIP_COMPILE.name, raising=False)


@pytest.mark.usefixtures("compiling")
@pytest.mark.parametrize(
    "render_item",
    [
        lambda item: rx.text(
            item, on_mount=LoopState.record(item), on_unmount=LoopState.record(item)
        ),
        lambda item: rx.box(rx.text(item, on_mount=LoopState.record(item))),
        lambda item: rx.text(item, on_unmount=LoopState.record(item)),
    ],
    ids=["mount_and_unmount", "descendant", "unmount"],
)
def test_unkeyed_item_with_lifecycle_events_warns(
    render_item, caplog: pytest.LogCaptureFixture
):
    """An unkeyed item with lifecycle events warns that it is keyed by index.

    Args:
        render_item: Renders an item with lifecycle events and no key.
        caplog: The log capture fixture.
    """
    with caplog.at_level(logging.WARNING):
        rx.foreach(LoopState.items, render_item)

    [message] = _key_warnings(caplog)
    assert "key=" in message
    # Repeat compiles, such as hot reloads, log it once.
    assert all(
        getattr(record, "dedupe", False)
        for record in caplog.records
        if record.getMessage() == message
    )


@pytest.mark.usefixtures("compiling")
@pytest.mark.parametrize(
    "render_item",
    [
        lambda item: rx.text(
            item,
            on_mount=LoopState.record(item),
            on_unmount=LoopState.record(item),
            key=item,
        ),
        lambda item: rx.text(item),
        lambda item: rx.text(item, on_click=LoopState.record(item)),
    ],
    ids=["keyed", "no_hooks", "click_only"],
)
def test_keyed_or_hookless_item_does_not_warn(
    render_item, caplog: pytest.LogCaptureFixture
):
    """A keyed item, or one without instance hooks, does not warn.

    Args:
        render_item: Renders an item.
        caplog: The log capture fixture.
    """
    with caplog.at_level(logging.WARNING):
        rx.foreach(LoopState.items, render_item)

    assert _key_warnings(caplog) == []


def test_unkeyed_item_does_not_warn_without_compiling(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """A process that only evaluates the pages, like a backend worker, does not warn.

    Args:
        monkeypatch: The monkeypatch fixture.
        caplog: The log capture fixture.
    """
    monkeypatch.setenv(environment.REFLEX_SKIP_COMPILE.name, "true")
    with caplog.at_level(logging.WARNING):
        rx.foreach(
            LoopState.items, lambda item: rx.text(item, on_mount=LoopState.record(item))
        )

    assert _key_warnings(caplog) == []
