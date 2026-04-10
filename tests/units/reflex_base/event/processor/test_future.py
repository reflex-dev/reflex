"""Tests for EventFuture."""

import asyncio

import pytest
from reflex_base.event.processor.future import EventFuture


@pytest.mark.asyncio
async def test_create_uses_running_loop():  # noqa: RUF029
    """EventFuture() defaults to the running event loop."""
    running_loop = asyncio.get_running_loop()
    f = EventFuture(txid="f")
    assert isinstance(f, EventFuture)
    assert f.get_loop() is running_loop
    assert f.children == []
    assert not f.done()


@pytest.mark.asyncio
async def test_create_with_explicit_loop():  # noqa: RUF029
    """EventFuture(loop=...) uses the given (non-default) loop."""
    other_loop = asyncio.new_event_loop()
    try:
        f = EventFuture(txid="f", loop=other_loop)
        assert isinstance(f, EventFuture)
        assert f.get_loop() is other_loop
        assert f.get_loop() is not asyncio.get_running_loop()
    finally:
        other_loop.close()


@pytest.mark.asyncio
async def test_add_child_multiple():  # noqa: RUF029
    """add_child can be called multiple times."""
    parent = EventFuture(txid="parent")
    children = [EventFuture(txid=f"c{i}") for i in range(3)]
    for c in children:
        parent.add_child(c)
    assert parent.children == children


@pytest.mark.asyncio
async def test_add_child_to_done_future_raises():  # noqa: RUF029
    """add_child raises RuntimeError if the parent future is already done."""
    parent = EventFuture(txid="parent")
    parent.set_result(None)
    child = EventFuture(txid="child")
    with pytest.raises(RuntimeError, match="already done"):
        parent.add_child(child)


@pytest.mark.asyncio
async def test_add_child_to_cancelled_future_raises():  # noqa: RUF029
    """add_child raises RuntimeError if the parent future is cancelled."""
    parent = EventFuture(txid="parent")
    parent.cancel()
    child = EventFuture(txid="child")
    with pytest.raises(RuntimeError, match="already done"):
        parent.add_child(child)


@pytest.mark.asyncio
async def test_all_done_no_children():  # noqa: RUF029
    """all_done is True when the future is resolved and has no children."""
    f = EventFuture(txid="f")
    assert not f.all_done()
    f.set_result(42)
    assert f.all_done()


@pytest.mark.asyncio
async def test_all_done_with_pending_child():  # noqa: RUF029
    """all_done is False when a child is still pending."""
    parent = EventFuture(txid="parent")
    child = EventFuture(txid="child")
    parent.add_child(child)
    parent.set_result(None)
    assert not parent.all_done()
    child.set_result(None)
    assert parent.all_done()


@pytest.mark.asyncio
async def test_all_done_nested():  # noqa: RUF029
    """all_done checks the full descendant tree."""
    root = EventFuture(txid="root")
    child = EventFuture(txid="child")
    grandchild = EventFuture(txid="grandchild")
    root.add_child(child)
    child.add_child(grandchild)

    root.set_result(None)
    child.set_result(None)
    # grandchild still pending
    assert not root.all_done()

    grandchild.set_result(None)
    assert root.all_done()


@pytest.mark.asyncio
async def test_all_done_with_cancelled_child():  # noqa: RUF029
    """all_done is True when all children are cancelled (done)."""
    parent = EventFuture(txid="parent")
    child = EventFuture(txid="child")
    parent.add_child(child)
    parent.set_result(None)
    child.cancel()
    assert parent.all_done()


@pytest.mark.asyncio
async def test_all_done_with_exception_child():  # noqa: RUF029
    """all_done is True when a child has an exception (still done)."""
    parent = EventFuture(txid="parent")
    child = EventFuture(txid="child")
    parent.add_child(child)
    parent.set_result(None)
    child.set_exception(ValueError("boom"))
    assert parent.all_done()


@pytest.mark.asyncio
async def test_wait_all_returns_result():
    """wait_all returns the result of the root future."""
    f = EventFuture(txid="f")
    f.set_result(42)
    result = await f.wait_all()
    assert result == 42


@pytest.mark.asyncio
async def test_wait_all_waits_for_children():
    """wait_all waits for all children to complete."""
    parent = EventFuture(txid="parent")
    child = EventFuture(txid="child")
    parent.add_child(child)

    async def resolve_later():
        await asyncio.sleep(0.01)
        child.set_result("child_done")

    parent.set_result("parent_done")
    task = asyncio.create_task(resolve_later())
    result = await parent.wait_all()
    assert result == "parent_done"
    assert child.done()
    await task


@pytest.mark.asyncio
async def test_wait_all_waits_for_nested_children():
    """wait_all waits for grandchildren too."""
    root = EventFuture(txid="root")
    child = EventFuture(txid="child")
    grandchild = EventFuture(txid="grandchild")
    root.add_child(child)
    child.add_child(grandchild)

    async def resolve_chain():
        await asyncio.sleep(0.01)
        child.set_result(None)
        await asyncio.sleep(0.01)
        grandchild.set_result(None)

    root.set_result("root")
    task = asyncio.create_task(resolve_chain())
    result = await root.wait_all()
    assert result == "root"
    assert grandchild.done()
    await task


@pytest.mark.asyncio
async def test_wait_all_suppresses_child_exceptions():
    """wait_all suppresses exceptions from children."""
    parent = EventFuture(txid="parent")
    child = EventFuture(txid="child")
    parent.add_child(child)

    parent.set_result("ok")
    child.set_exception(ValueError("child error"))

    # Should not raise
    result = await parent.wait_all()
    assert result == "ok"


@pytest.mark.asyncio
async def test_wait_all_suppresses_child_cancellation():
    """wait_all suppresses CancelledError from children."""
    parent = EventFuture(txid="parent")
    child = EventFuture(txid="child")
    parent.add_child(child)

    parent.set_result("ok")
    child.cancel()

    result = await parent.wait_all()
    assert result == "ok"


@pytest.mark.asyncio
async def test_wait_all_children_added_during_iteration():
    """wait_all picks up children added while iterating (index-based walk)."""
    parent = EventFuture(txid="parent")
    child1 = EventFuture(txid="child1")
    parent.add_child(child1)
    parent.set_result("done")

    # child2 will be added to child1 after child1 resolves,
    # simulating a chained event that enqueues more events.
    child2 = EventFuture(txid="child2")

    async def resolve_and_chain():
        await asyncio.sleep(0.01)
        child1.add_child(child2)
        child1.set_result(None)
        await asyncio.sleep(0.01)
        child2.set_result(None)

    task = asyncio.create_task(resolve_and_chain())
    await parent.wait_all()
    assert child2.done()
    await task


@pytest.mark.asyncio
async def test_cancel_no_children():  # noqa: RUF029
    """Cancel cancels the future itself."""
    f = EventFuture(txid="f")
    assert f.cancel()
    assert f.cancelled()


@pytest.mark.asyncio
async def test_cancel_cascades_to_children():  # noqa: RUF029
    """Cancel propagates to all children."""
    parent = EventFuture(txid="parent")
    child1 = EventFuture(txid="child1")
    child2 = EventFuture(txid="child2")
    parent.add_child(child1)
    parent.add_child(child2)

    parent.cancel()
    assert parent.cancelled()
    assert child1.cancelled()
    assert child2.cancelled()


@pytest.mark.asyncio
async def test_cancel_cascades_to_grandchildren():  # noqa: RUF029
    """Cancel propagates through the full descendant tree."""
    root = EventFuture(txid="root")
    child = EventFuture(txid="child")
    grandchild = EventFuture(txid="grandchild")
    root.add_child(child)
    child.add_child(grandchild)

    root.cancel()
    assert grandchild.cancelled()


@pytest.mark.asyncio
async def test_cancel_with_message():  # noqa: RUF029
    """Cancel passes the message to children."""
    parent = EventFuture(txid="parent")
    child = EventFuture(txid="child")
    parent.add_child(child)

    parent.cancel("shutting down")
    assert parent.cancelled()
    assert child.cancelled()
    with pytest.raises(asyncio.CancelledError, match="shutting down"):
        parent.result()
    with pytest.raises(asyncio.CancelledError, match="shutting down"):
        child.result()


@pytest.mark.asyncio
async def test_cancel_already_done_child():  # noqa: RUF029
    """Cancel on a parent does not fail if a child is already resolved."""
    parent = EventFuture(txid="parent")
    child = EventFuture(txid="child")
    parent.add_child(child)
    child.set_result("already done")

    parent.cancel()
    assert parent.cancelled()
    # child was already done, cancel returns False but doesn't raise
    assert not child.cancelled()
    assert child.result() == "already done"


@pytest.mark.asyncio
async def test_cancel_already_done_parent_returns_false():  # noqa: RUF029
    """Cancel returns False if the parent is already resolved."""
    f = EventFuture(txid="f")
    f.set_result(None)
    assert not f.cancel()
