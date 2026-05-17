"""Programmatic builder for the Rust-Python IR.

Every helper here returns a plain ``list`` in the positional shape the Rust
parser expects (see ``RUST_REWRITE_PLAN.md`` §4.1 and
``crates/reflex_ir/src/parse.rs``). The whole tree is built bottom-up and
serialized in **one** ``msgpack.packb`` call — see the spike note in §1 of
the plan: streaming via ``msgpack.Packer`` is 5-7% slower because
msgpack-python descends a tree-of-lists in C.

The builders deliberately accept ``Sequence``/``Mapping`` Python types and
do no validation — they're the hottest path in IR emit and pre-validated
component classes feed them directly. Bad inputs surface as
``ParseError::BadArrayLen`` on the Rust side, which contains enough context
to trace back to the offending builder call.

Example::

    >>> from reflex.compiler.ir import builder as ir
    >>> page = ir.page(
    ...     route="/about",
    ...     root=ir.element(
    ...         "div",
    ...         props=[("id", ir.js_expr("\"main\""))],
    ...         children=[ir.text("hi")],
    ...     ),
    ... )
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from reflex.compiler.ir import schema as _schema
from reflex.compiler.ir.canonical import hash_ir_subtree

# Type aliases for clarity — these are list aliases, not nominal types.
ValueIR = list
ComponentIR = list
PageIR = list
VarDataIR = list
EventHandlerIR = list
HookIR = list
SourceLocIR = list
MatchArmIR = list
MetaIR = list
LiteralIR = list

# ---- Leaf builders ----------------------------------------------------------


def source_loc(file_id: int = 0, line: int = 0, col: int = 0) -> SourceLocIR:
    """Build a ``SourceLoc`` triple. ``(0, 0, 0)`` means synthetic."""
    return [file_id, line, col]


SYNTHETIC_LOC: SourceLocIR = source_loc()


def var_data(
    *,
    hooks: Sequence[str] = (),
    imports: Sequence[tuple[str, str]] = (),
    state: str | None = None,
    deps: Sequence[str] = (),
    position: int | None = None,
    components: Sequence[str] = (),
) -> VarDataIR:
    """Build a ``VarData`` IR fragment.

    Args:
        hooks: raw JS hook fragments this expression depends on.
        imports: ``(module, name)`` pairs.
        state: owning state class name, if any.
        deps: dependency identifiers.
        position: hoist position hint.
        components: component memo wrappers needed at hoist time.

    Returns:
        The positional-array IR fragment.
    """
    return [
        list(hooks),
        [[m, n] for m, n in imports],
        state,
        list(deps),
        position,
        list(components),
    ]


EMPTY_VAR_DATA: VarDataIR = var_data()


# ---- Value builders ---------------------------------------------------------


def js_expr(expr: str, var_data_: VarDataIR | None = None) -> ValueIR:
    """A pre-baked JS expression with optional VarData.

    Args:
        expr: the JS source string (Reflex Python typically calls ``str(var)``
            for a ``Var`` instance to get this).
        var_data_: hoist metadata; defaults to empty.
    """
    return [_schema.VALUE_JS_EXPR, expr, var_data_ if var_data_ is not None else EMPTY_VAR_DATA]


def literal_null() -> ValueIR:
    return [_schema.VALUE_LITERAL, [_schema.LITERAL_NULL]]


def literal_bool(value: bool) -> ValueIR:
    return [_schema.VALUE_LITERAL, [_schema.LITERAL_BOOL, bool(value)]]


def literal_int(value: int) -> ValueIR:
    return [_schema.VALUE_LITERAL, [_schema.LITERAL_INT, int(value)]]


def literal_float(value: float) -> ValueIR:
    return [_schema.VALUE_LITERAL, [_schema.LITERAL_FLOAT, float(value)]]


def literal_str(value: str) -> ValueIR:
    return [_schema.VALUE_LITERAL, [_schema.LITERAL_STR, value]]


def ref(name: str) -> ValueIR:
    return [_schema.VALUE_REF, name]


def event_handler(
    trigger: str, expr: str, var_data_: VarDataIR | None = None
) -> EventHandlerIR:
    return [trigger, expr, var_data_ if var_data_ is not None else EMPTY_VAR_DATA]


def hook(code: str, deps: Sequence[str] = (), position: int = _schema.HOOK_POSITION_USER) -> HookIR:
    return [code, list(deps), int(position)]


# ---- Component builders -----------------------------------------------------
#
# Each builder accepts an optional ``id``. When omitted we hash the canonical
# bytes of the constructed node to assign a stable NodeId. Component classes
# that already know a stable id (e.g. one derived from their Python source
# location) can pass it directly to skip the hash.


def _assign_id(component_ir: ComponentIR, id_index: int) -> ComponentIR:
    """Compute and set the NodeId at ``id_index`` if it's currently 0."""
    if component_ir[id_index] == 0:
        component_ir[id_index] = hash_ir_subtree(component_ir)
    return component_ir


def element(
    tag: str,
    *,
    props: Sequence[tuple[str, ValueIR]] = (),
    children: Sequence[ComponentIR] = (),
    events: Sequence[EventHandlerIR] = (),
    hooks: Sequence[HookIR] = (),
    id: int = 0,
    loc: SourceLocIR | None = None,
) -> ComponentIR:
    """Build an ``Element`` component IR node."""
    return _assign_id(
        [
            _schema.COMPONENT_ELEMENT,
            tag,
            [[name, value] for name, value in props],
            list(children),
            list(events),
            list(hooks),
            id,
            loc if loc is not None else SYNTHETIC_LOC,
        ],
        id_index=6,
    )


def text(value: str, *, id: int = 0, loc: SourceLocIR | None = None) -> ComponentIR:
    """Build a ``Text`` component IR node."""
    return _assign_id(
        [_schema.COMPONENT_TEXT, value, id, loc if loc is not None else SYNTHETIC_LOC],
        id_index=2,
    )


def foreach(
    iter_value: ValueIR,
    body: ComponentIR,
    *,
    id: int = 0,
    loc: SourceLocIR | None = None,
) -> ComponentIR:
    """Build a ``Foreach`` component IR node."""
    return _assign_id(
        [
            _schema.COMPONENT_FOREACH,
            iter_value,
            body,
            id,
            loc if loc is not None else SYNTHETIC_LOC,
        ],
        id_index=3,
    )


def cond(
    test: ValueIR,
    then: ComponentIR,
    else_: ComponentIR | None = None,
    *,
    id: int = 0,
    loc: SourceLocIR | None = None,
) -> ComponentIR:
    """Build a ``Cond`` component IR node."""
    return _assign_id(
        [
            _schema.COMPONENT_COND,
            test,
            then,
            else_,
            id,
            loc if loc is not None else SYNTHETIC_LOC,
        ],
        id_index=4,
    )


def match_arm(case: ValueIR, body: ComponentIR) -> MatchArmIR:
    return [case, body]


def match(
    value: ValueIR,
    arms: Sequence[MatchArmIR],
    default: ComponentIR | None = None,
    *,
    id: int = 0,
    loc: SourceLocIR | None = None,
) -> ComponentIR:
    """Build a ``Match`` component IR node."""
    return _assign_id(
        [
            _schema.COMPONENT_MATCH,
            value,
            list(arms),
            default,
            id,
            loc if loc is not None else SYNTHETIC_LOC,
        ],
        id_index=4,
    )


def memoize(
    inner: ComponentIR,
    key: int,
    *,
    id: int = 0,
    loc: SourceLocIR | None = None,
) -> ComponentIR:
    """Build a ``Memoize`` component IR node."""
    return _assign_id(
        [
            _schema.COMPONENT_MEMOIZE,
            inner,
            int(key),
            id,
            loc if loc is not None else SYNTHETIC_LOC,
        ],
        id_index=3,
    )


def fragment(
    children: Sequence[ComponentIR],
    *,
    id: int = 0,
    loc: SourceLocIR | None = None,
) -> ComponentIR:
    """Build a ``Fragment`` component IR node."""
    return _assign_id(
        [
            _schema.COMPONENT_FRAGMENT,
            list(children),
            id,
            loc if loc is not None else SYNTHETIC_LOC,
        ],
        id_index=2,
    )


def expr_node(
    value: ValueIR, *, id: int = 0, loc: SourceLocIR | None = None
) -> ComponentIR:
    """Build an ``Expr`` component IR node (inline JSX expression)."""
    return _assign_id(
        [_schema.COMPONENT_EXPR, value, id, loc if loc is not None else SYNTHETIC_LOC],
        id_index=2,
    )


# ---- Top-level page --------------------------------------------------------


def meta(name: str, content: str) -> MetaIR:
    return [name, content]


def page(
    *,
    route: str,
    root: ComponentIR,
    title: str | None = None,
    meta_: Iterable[MetaIR] = (),
    source_files: Iterable[int] = (),
    component_imports: Iterable[tuple[str, str]] = (),
    state_bindings: Iterable[str] = (),
    needs_ref: bool = False,
) -> PageIR:
    """Build a complete ``Page`` IR (schema v2).

    Args:
        route: URL path served by this page.
        root: the root Component IR.
        title: document title; ``None`` to omit.
        meta_: per-page <meta> entries.
        source_files: ``PyFileId``s this page depends on.
        component_imports: ``(module, alias)`` pairs emitted as
            ``import { <alias> } from "<module>";`` at module scope.
            The alias may contain ``"<src> as <local>"`` to rename.
        state_bindings: distinct ``StateContexts`` keys this page needs
            via ``useContext``.
        needs_ref: whether any element uses an ``id`` prop that the
            React runtime should wire to a ``useRef``.
    """
    return [
        _schema.SCHEMA_VERSION,
        route,
        root,
        title,
        list(meta_),
        list(source_files),
        [[m, a] for m, a in component_imports],
        list(state_bindings),
        bool(needs_ref),
    ]
