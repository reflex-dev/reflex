"""Test cases for code rewriting utilities."""
import inspect

import pytest

import reflex
from reflex.event import BACKGROUND_TASK_MARKER, background
from reflex.utils import rewrites


def test_add_yield_after_async_with_self():
    async def fn(self):
        async with self:
            pass

    orig_code = fn.__code__

    assert inspect.iscoroutinefunction(fn)
    assert not inspect.isasyncgenfunction(fn)
    new_fn = rewrites.add_yield_after_async_with_self(fn)
    assert inspect.isasyncgenfunction(new_fn)
    assert fn is new_fn
    assert orig_code is not new_fn.__code__
    assert inspect.getsource(new_fn).count("yield") == 1


def test_add_yield_after_async_with_foo():
    async def fn(foo):
        async with foo:
            pass

    orig_code = fn.__code__

    assert inspect.iscoroutinefunction(fn)
    assert not inspect.isasyncgenfunction(fn)
    new_fn = rewrites.add_yield_after_async_with_self(fn)
    assert inspect.isasyncgenfunction(new_fn)
    assert fn is new_fn
    assert orig_code is not new_fn.__code__
    assert inspect.getsource(new_fn).count("yield") == 1


def test_add_yield_after_async_with_foo_not_self():
    async def fn(foo, self):
        async with self:
            pass

    orig_code = fn.__code__

    assert inspect.iscoroutinefunction(fn)
    assert not inspect.isasyncgenfunction(fn)
    new_fn = rewrites.add_yield_after_async_with_self(fn)
    assert not inspect.isasyncgenfunction(new_fn)
    assert fn is new_fn
    assert orig_code is new_fn.__code__
    assert "yield" not in inspect.getsource(new_fn)


def test_add_yield_after_async_with_self_no_mod():
    async def fn(self):
        async with self:
            pass
        yield

    orig_code = fn.__code__

    new_fn = rewrites.add_yield_after_async_with_self(fn)
    assert fn is new_fn
    assert orig_code is new_fn.__code__
    assert inspect.getsource(new_fn).count("yield") == 1


def test_add_yield_after_async_with_self_add_yield():
    async def fn(self):
        async with self:
            pass
        pass
        yield

    orig_code = fn.__code__

    new_fn = rewrites.add_yield_after_async_with_self(fn)
    assert fn is new_fn
    assert orig_code is not new_fn.__code__
    assert inspect.getsource(new_fn).count("yield") == 2


def test_add_yield_after_async_with_self_dummy():
    def fn(self):
        pass

    orig_code = fn.__code__

    assert not inspect.iscoroutinefunction(fn)
    assert not inspect.isasyncgenfunction(fn)
    new_fn = rewrites.add_yield_after_async_with_self(fn)
    assert not inspect.isasyncgenfunction(new_fn)
    assert fn is new_fn
    assert orig_code is new_fn.__code__
    assert "yield" not in inspect.getsource(new_fn)


@background
async def _bg_fn1(self):
    async with self:
        pass


@reflex.background
async def _bg_fn2(self):
    async with self:
        pass


@pytest.mark.parametrize(
    "fn",
    [
        _bg_fn1,
        _bg_fn2,
    ],
)
def test_background_decorator(fn):
    assert inspect.isasyncgenfunction(fn)
    assert "background" not in inspect.getsource(fn)
    assert inspect.getsource(fn).count("yield") == 1
    assert getattr(fn, BACKGROUND_TASK_MARKER, None)


def test_background_decorator_no_apply():
    @background
    async def fn(self):
        pass

    assert not inspect.isasyncgenfunction(fn)
    assert "yield" not in inspect.getsource(fn)
    assert inspect.getsource(fn).count("background") == 1
    assert getattr(fn, BACKGROUND_TASK_MARKER, None)


def test_background_decorator_multiple():
    @reflex.background
    @background
    @background
    async def fn(self):
        async with self:
            pass

    assert inspect.isasyncgenfunction(fn)
    assert inspect.getsource(fn).count("background") == 2
    assert inspect.getsource(fn).count("yield") == 1
    assert getattr(fn, BACKGROUND_TASK_MARKER, None)


@pytest.mark.parametrize(
    "param_value",
    [
        True,
        False,
    ],
    ids=["default", "disabled"],
)
def test_background_decorator_automatic_yield_after_modifications(param_value):
    @background(automatic_yield_after_modifications=param_value)
    async def fn(self):
        async with self:
            pass

    if param_value:
        assert inspect.isasyncgenfunction(fn)
        assert "automatic_yield_after_modifications" not in inspect.getsource(fn)
        assert inspect.getsource(fn).count("yield") == 1
        assert "background" not in inspect.getsource(fn)
    else:
        assert not inspect.isasyncgenfunction(fn)
        assert inspect.getsource(fn).count("background") == 1
        assert "automatic_yield_after_modifications" in inspect.getsource(fn)
        assert inspect.getsource(fn).count("yield") == 1
    assert getattr(fn, BACKGROUND_TASK_MARKER, None)
