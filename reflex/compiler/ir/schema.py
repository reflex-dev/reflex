"""Wire-format constants for the Rust-Python IR. See RUST_REWRITE_PLAN.md §4.

Bumping ``SCHEMA_VERSION`` is a breaking change between Python and Rust; the
Rust parser hard-rejects any blob whose first field doesn't match.

Reading any of these constants is cost-free at runtime: they're module-level
``int`` literals, no class lookup. Keep them in lock-step with
``crates/reflex_ir/src/parse.rs::SCHEMA_VERSION``.
"""

from __future__ import annotations

from typing import Final

SCHEMA_VERSION: Final[int] = 2
"""Current wire-format version. Increment for any breaking IR change.

v2 added page-level ``component_imports``, ``state_bindings``, and
``needs_ref`` fields so the Rust codegen can emit a fully-runtime-compatible
page module (component-class imports + ``useContext(StateContexts.*)`` +
``useRef``) without a Python postprocessor.
"""

# ---- Component kind discriminants -------------------------------------------
COMPONENT_ELEMENT: Final[int] = 0
COMPONENT_TEXT: Final[int] = 1
COMPONENT_FOREACH: Final[int] = 2
COMPONENT_COND: Final[int] = 3
COMPONENT_MATCH: Final[int] = 4
COMPONENT_MEMOIZE: Final[int] = 5
COMPONENT_FRAGMENT: Final[int] = 6
COMPONENT_EXPR: Final[int] = 7

# ---- Value kind discriminants -----------------------------------------------
VALUE_JS_EXPR: Final[int] = 0
VALUE_LITERAL: Final[int] = 1
VALUE_REF: Final[int] = 2

# ---- Literal kind discriminants ---------------------------------------------
LITERAL_NULL: Final[int] = 0
LITERAL_BOOL: Final[int] = 1
LITERAL_INT: Final[int] = 2
LITERAL_FLOAT: Final[int] = 3
LITERAL_STR: Final[int] = 4

# ---- Other constants --------------------------------------------------------

# Default Hook.position bucket meanings — must agree with reflex_semantic::Aggregated.
HOOK_POSITION_INTERNAL: Final[int] = 0
"""State/theme-bound hooks. Emitted first in the render function."""

HOOK_POSITION_USER: Final[int] = 1
"""User-supplied hooks. Emitted after internal hooks."""
