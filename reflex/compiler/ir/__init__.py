"""IR layer between Reflex's Python Component classes and the Rust compiler.

**Status (2026-05-17):** Demoted to debug / diagnostic use only. The
production compile path is ``reflex_pyread`` (PyO3 walks the Component
tree directly — plan §0b lever (a)); ``reflex.compiler.ir.bridge`` is
deleted. The IR-construction helpers below survive because the codegen
corpus IR-shape tests still build IR programmatically, but no production
code path goes through msgpack anymore.

* :mod:`reflex.compiler.ir.schema` — wire-format constants matching
  ``RUST_REWRITE_PLAN.md`` §4.
* :mod:`reflex.compiler.ir.builder` — programmatic builders (``element``,
  ``text``, ``foreach``, …) that produce list-of-lists IR ready for
  ``msgpack.packb``.
* :mod:`reflex.compiler.ir.pack` — one-call ``packb`` wrappers.
* :mod:`reflex.compiler.ir.canonical` — canonical ``NodeId`` hashing
  (``xxh3_64`` of the JSON-serializable canonical form).

The IR contract is positional msgpack arrays; see the Rust side
``crates/reflex_ir/src/parse.rs`` for the canonical wire format.
"""

from reflex.compiler.ir import builder, canonical, pack, schema

__all__ = ["builder", "canonical", "pack", "schema"]
