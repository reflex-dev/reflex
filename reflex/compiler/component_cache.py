"""Experimental in-process construction cache for static subtrees (flag-gated).

Enabled by ``REFLEX_COMPONENT_CACHE``. When off (default), nothing changes.

The dominant compile cost is per-component construction (``Component._create`` ->
``_post_init``: per-prop ``LiteralVar.create`` + ``satisfies_type_hint``, etc.).
Structurally-identical *static* subtrees recur heavily across a project (shared
chrome: footer, nav, layout shells) — on the docs app a large fraction of
subtrees are duplicates. This cache builds each such subtree once and reuses it.

**Interception point.** ``Component.create`` is captured into pre-bound module
factories at import time (``div = Div.create``), so patching it cannot reach
``rx.el.div(...)``. But ``create`` delegates to ``cls._create(...)`` via a fresh
attribute lookup, so patching ``Component._create`` is reached by *every*
``create`` call. By then string children are already normalized to
``Bare(contents=LiteralVar(...))``; a constant ``LiteralVar`` (no var data) is
still signable, so static text leaves don't break the chain.

**Key (cheap, pre-build).** A signature is computed from the call arguments —
the class, the prop values, and the child signatures (propagated bottom-up). It
is computed before ``_post_init`` runs, so a cache hit skips construction
entirely (unlike a post-render structural hash, which would cost as much as the
work it saves). A subtree is cacheable only when **every prop is a literal or a
constant Var** and **every child is cacheable**; anything with a state-bound Var,
an event handler, or a component-valued prop yields no signature and is built
normally — i.e. dynamic subtrees are simply re-built.

**Safety — NOT yet sound on its own; requires verify mode.** A reused subtree
is shared across pages on the assumption that the pipeline clones-before-mutate
via ``PageContext.own()``. Measuring on the real docs app refuted that: the
head-injection pass mutates a shared subtree (the redirect ``<head>`` fragment)
**in place**, bypassing ``own()``, so a fragment reused across N pages
accumulates N copies of its children. Until every child mutation in the compile
pipeline goes through ``own()``, this cache **must** run with
``REFLEX_COMPILE_CACHE_VERIFY`` — which compiles both ways, byte-compares, and
falls back to the full (uncached) result on any mismatch. Measured cold-build
upside when correct: ~1.5x; do not enable unguarded.

In-process only (caches live ``Component`` objects); reset per compile.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from reflex.vars import Var

if TYPE_CHECKING:
    from collections.abc import Sequence

    from reflex_base.components.component import BaseComponent

#: signature -> cached built component (this compile only).
_CACHE: dict[str, Any] = {}
#: id(component) -> its signature, to propagate child signatures bottom-up.
_SIG_BY_ID: dict[int, str] = {}
#: hit/build counters for tests and observability.
STATS = {"hits": 0, "builds": 0}

_ORIGINAL_FUNC: Any = None
_BARE_CLS: Any = None


def _child_signature(child: object) -> str | None:
    """Return a signature for a normalized child component, or None.

    Args:
        child: A child passed to ``_create`` (already a component).

    Returns:
        The child's propagated signature, or a derived one for static text
        leaves (``Bare`` wraps text via ``_unsafe_create``, so it never passes
        through the cached ``_create`` and has no propagated signature), else
        None when the child is dynamic.
    """
    sig = _SIG_BY_ID.get(id(child))
    if sig is not None:
        return sig
    if _BARE_CLS is not None and type(child) is _BARE_CLS:
        contents_sig = _value_signature(getattr(child, "contents", None))
        return None if contents_sig is None else "bare" + contents_sig
    return None


def _value_signature(value: object) -> str | None:
    """Return a stable signature for a prop value, or None if not static.

    Args:
        value: A prop value passed to ``_create``.

    Returns:
        A stable string for a literal or constant Var, else None. None means the
        value is dynamic (a state-bound Var, an event handler, a component, …),
        which makes the whole subtree uncacheable.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return repr(value)
    if isinstance(value, Var):
        # A constant Var (no state/hook/import var data) is fully determined by
        # its JS form, so it is safe to key on. State-bound Vars carry var data.
        return "V" + str(value) if value._get_all_var_data() is None else None
    if isinstance(value, (list, tuple)):
        parts = [_value_signature(v) for v in value]
        return None if None in parts else "[" + ",".join(parts) + "]"  # type: ignore[arg-type]
    if isinstance(value, dict):
        parts = []
        for key, val in value.items():
            vs = _value_signature(val)
            if vs is None:
                return None
            parts.append(f"{key!r}:{vs}")
        return "{" + ",".join(sorted(parts)) + "}"
    return None


def signature(cls: type, children: Sequence[BaseComponent], props: dict) -> str | None:
    """Compute a cheap pre-build signature for a ``_create`` call, or None.

    Args:
        cls: The component class.
        children: Already-normalized child components passed to ``_create``.
        props: Keyword props passed to ``_create``.

    Returns:
        A hex signature if the subtree is fully static, else None.
    """
    child_sigs = []
    for child in children:
        sig = _child_signature(child)
        if sig is None:
            return None  # a dynamic / uncached child -> not cacheable
        child_sigs.append(sig)
    prop_parts = []
    for key, value in props.items():
        vs = _value_signature(value)
        if vs is None:
            return None
        prop_parts.append(f"{key}={vs}")
    raw = (
        f"{cls.__module__}.{cls.__qualname__}"
        f"|{','.join(sorted(prop_parts))}|{'|'.join(child_sigs)}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def install() -> None:
    """Patch ``Component._create`` to memoize static subtrees by signature."""
    global _ORIGINAL_FUNC, _BARE_CLS
    if _ORIGINAL_FUNC is not None:
        return
    from reflex_base.components.component import Component
    from reflex_components_core.base.bare import Bare

    _BARE_CLS = Bare
    _ORIGINAL_FUNC = Component._create.__func__  # type: ignore[attr-defined]

    def cached_create(
        cls: type, children: Sequence[BaseComponent], **props: Any
    ) -> Any:
        sig = signature(cls, children, props)
        if sig is not None:
            hit = _CACHE.get(sig)
            if hit is not None:
                STATS["hits"] += 1
                return hit
        comp = _ORIGINAL_FUNC(cls, children, **props)
        STATS["builds"] += 1
        if sig is not None:
            _CACHE[sig] = comp
            _SIG_BY_ID[id(comp)] = sig
        return comp

    Component._create = classmethod(cached_create)  # type: ignore[assignment]


def uninstall() -> None:
    """Restore the original ``Component._create``."""
    global _ORIGINAL_FUNC
    if _ORIGINAL_FUNC is None:
        return
    from reflex_base.components.component import Component

    Component._create = classmethod(_ORIGINAL_FUNC)  # type: ignore[assignment]
    _ORIGINAL_FUNC = None


def reset() -> None:
    """Clear the per-compile caches and stats."""
    _CACHE.clear()
    _SIG_BY_ID.clear()
    STATS["hits"] = 0
    STATS["builds"] = 0
