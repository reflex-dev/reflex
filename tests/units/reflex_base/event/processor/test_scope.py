"""Tests for the per-event ambient-context scope hook."""

import contextlib
from typing import TYPE_CHECKING, cast

import pytest
from reflex_base.event.processor import scope

if TYPE_CHECKING:
    from reflex.state import BaseState

# The scope hook never touches the root state when providers ignore it, so a
# dummy stands in for a real BaseState in these tests.
_ROOT = cast("BaseState", object())


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
    assert isinstance(scope.event_scope(_ROOT), contextlib.nullcontext)
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
    async with scope.event_scope(_ROOT):
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
        async with scope.event_scope(_ROOT):
            pass

    # The first provider's context must be exited even though the second raised.
    assert exited == ["first"]


@pytest.mark.asyncio
async def test_body_exception_is_forwarded_to_providers():
    seen: list[BaseException | None] = []

    @contextlib.contextmanager
    def observing_cm():
        try:
            yield
        except BaseException as exc:
            seen.append(exc)
            raise

    async def provider(_root):  # noqa: RUF029 (async required by provider protocol)
        return observing_cm()

    scope.register_event_scope_provider(provider)

    with pytest.raises(RuntimeError, match="handler failed"):
        async with scope.event_scope(_ROOT):
            msg = "handler failed"
            raise RuntimeError(msg)

    assert [str(exc) for exc in seen] == ["handler failed"]


@pytest.mark.asyncio
async def test_provider_can_suppress_a_body_exception():
    async def provider(_root):  # noqa: RUF029 (async required by provider protocol)
        return contextlib.suppress(RuntimeError)

    scope.register_event_scope_provider(provider)

    async with scope.event_scope(_ROOT):
        msg = "swallowed"
        raise RuntimeError(msg)
