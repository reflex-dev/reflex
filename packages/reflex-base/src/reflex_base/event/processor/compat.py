"""Compatibility shims since asyncio changes quite a bit from 3.11 to 3.14."""

import asyncio
import sys

if sys.version_info >= (3, 13):
    from asyncio import as_completed as as_completed
else:
    # The following implementation of as_completed is adapted from Python 3.14
    # python/cpython@9e1f1644cd7b7661f0748bb37351836e8d6f37e2

    class _AsCompletedIterator:
        """Iterator of awaitables representing tasks of asyncio.as_completed.

        As an asynchronous iterator, iteration yields futures as they finish. As a
        plain iterator, new coroutines are yielded that will return or raise the
        result of the next underlying future to complete.
        """

        def __init__(self, aws, timeout):  # noqa: ANN001
            self._done = asyncio.Queue()
            self._timeout_handle = None

            loop = asyncio.get_event_loop()
            todo = {asyncio.ensure_future(aw, loop=loop) for aw in set(aws)}
            for f in todo:
                f.add_done_callback(self._handle_completion)
            if todo and timeout is not None:
                self._timeout_handle = loop.call_later(timeout, self._handle_timeout)
            self._todo = todo
            self._todo_left = len(todo)

        def __aiter__(self):
            return self

        def __iter__(self):
            return self

        async def __anext__(self):
            if not self._todo_left:
                raise StopAsyncIteration
            assert self._todo_left > 0
            self._todo_left -= 1
            return await self._wait_for_one()

        def __next__(self):
            if not self._todo_left:
                raise StopIteration
            assert self._todo_left > 0
            self._todo_left -= 1
            return self._wait_for_one(resolve=True)

        def _handle_timeout(self):
            for f in self._todo:
                f.remove_done_callback(self._handle_completion)
                self._done.put_nowait(None)  # Sentinel for _wait_for_one().
            self._todo.clear()  # Can't do todo.remove(f) in the loop.

        def _handle_completion(self, f):  # noqa: ANN001
            if not self._todo:
                return  # _handle_timeout() was here first.
            self._todo.remove(f)
            self._done.put_nowait(f)
            if not self._todo and self._timeout_handle is not None:
                self._timeout_handle.cancel()

        async def _wait_for_one(self, resolve=False):  # noqa: ANN001
            # Wait for the next future to be done and return it unless resolve is
            # set, in which case return either the result of the future or raise
            # an exception.
            f = await self._done.get()
            if f is None:
                # Dummy value from _handle_timeout().
                raise asyncio.TimeoutError
            return f.result() if resolve else f

    def as_completed(aws, *, timeout=None):  # noqa: ANN001
        """Return an iterator of coroutines that yield the results of the given awaitables.

        The coroutines are ordered in the order in which the given awaitables complete.
        If a given awaitable raises an exception, the corresponding coroutine raises the same exception.

        Args:
            aws: An iterable of awaitables.
            timeout: If provided, the maximum number of seconds to wait for the next awaitable to complete before raising a TimeoutError.
        """
        return _AsCompletedIterator(aws, timeout)
