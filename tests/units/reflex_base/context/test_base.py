"""Tests for BaseContext."""

import dataclasses

import pytest
from reflex_base.context.base import BaseContext


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class _TestContext(BaseContext):
    """Minimal BaseContext subclass for unit testing."""

    label: str = "test"


def test_get_without_set_raises():
    """get() raises LookupError when no context is set."""
    with pytest.raises(LookupError):
        _TestContext.get()


def test_set_and_get():
    """set() makes the context retrievable via get()."""
    ctx = _TestContext(label="a")
    token = _TestContext.set(ctx)
    try:
        assert _TestContext.get() is ctx
    finally:
        _TestContext.reset(token)


def test_reset_restores_previous():
    """reset() restores the previously active context."""
    outer = _TestContext(label="outer")
    outer_tok = _TestContext.set(outer)
    try:
        inner = _TestContext(label="inner")
        inner_tok = _TestContext.set(inner)
        assert _TestContext.get() is inner
        _TestContext.reset(inner_tok)
        assert _TestContext.get() is outer
    finally:
        _TestContext.reset(outer_tok)


def test_context_manager_enter_exit():
    """__enter__ sets the context and __exit__ removes it."""
    ctx = _TestContext(label="cm")
    with ctx as entered:
        assert entered is ctx
        assert _TestContext.get() is ctx
    with pytest.raises(LookupError):
        _TestContext.get()


def test_context_manager_nesting():
    """Nested context managers restore the outer context on inner exit."""
    outer = _TestContext(label="outer")
    inner = _TestContext(label="inner")
    with outer:
        assert _TestContext.get().label == "outer"
        with inner:
            assert _TestContext.get().label == "inner"
        assert _TestContext.get().label == "outer"


def test_double_enter_raises():
    """Entering the same context instance twice raises RuntimeError."""
    ctx = _TestContext(label="double")
    with ctx, pytest.raises(RuntimeError, match="already attached"):
        ctx.__enter__()


def test_ensure_context_attached():
    """ensure_context_attached raises when not entered, succeeds when entered."""
    ctx = _TestContext(label="ensure")
    with pytest.raises(RuntimeError, match="must be entered"):
        ctx.ensure_context_attached()
    with ctx:
        ctx.ensure_context_attached()


def test_subclasses_have_independent_context_vars():
    """Two BaseContext subclasses do not share their ContextVar."""

    @dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
    class _OtherContext(BaseContext):
        value: int = 0

    ctx_a = _TestContext(label="a")
    ctx_b = _OtherContext(value=42)
    with ctx_a, ctx_b:
        assert _TestContext.get().label == "a"
        assert _OtherContext.get().value == 42
