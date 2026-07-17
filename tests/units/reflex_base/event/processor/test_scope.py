"""Tests for the per-event ambient-context scope hook."""

import contextlib

import pytest
from reflex_base.event.processor import scope


@pytest.fixture(autouse=True)
def clean_providers():
    """Isolate the global provider registry per test.

    Yields:
        None
    """
    saved = list(scope._providers)
    scope._providers.clear()
    yield
    scope._providers[:] = saved


def test_no_providers_is_nullcontext():
    assert isinstance(scope.event_scope(object()), contextlib.nullcontext)
    assert not scope.has_event_scope_providers()


@pytest.mark.asyncio
async def test_provider_scope_entered_and_exited():
    events: list[str] = []

    @contextlib.contextmanager
    def cm():
        events.append("enter")
        try:
            yield
        finally:
            events.append("exit")

    async def provider(_root):  # noqa: RUF029 (async required by provider protocol)
        return cm()

    scope.register_event_scope_provider(provider)
    async with scope.event_scope(object()):
        events.append("body")

    assert events == ["enter", "body", "exit"]


@pytest.mark.asyncio
async def test_earlier_scope_cleaned_up_when_later_provider_raises():
    exited: list[str] = []

    @contextlib.contextmanager
    def tracking_cm():
        try:
            yield
        finally:
            exited.append("first")

    async def first(_root):  # noqa: RUF029 (async required by provider protocol)
        return tracking_cm()

    async def second(_root):  # noqa: RUF029 (async required by provider protocol)
        msg = "boom"
        raise RuntimeError(msg)

    scope.register_event_scope_provider(first)
    scope.register_event_scope_provider(second)

    with pytest.raises(RuntimeError, match="boom"):
        async with scope.event_scope(object()):
            pass

    # The first provider's context must be exited even though the second raised.
    assert exited == ["first"]
