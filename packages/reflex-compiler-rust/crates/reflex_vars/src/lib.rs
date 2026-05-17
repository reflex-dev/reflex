//! Rust port of `packages/reflex-base/src/reflex_base/vars/` — see plan §0b.
//!
//! This iteration ships the pure-Rust data model only: `Var`, `VarData`,
//! `ImportVar`, `HookPosition`, and `VarData::merge`. No PyO3 bindings yet —
//! those land in the next iteration once the data shape is reviewed.
//!
//! The semantics here mirror the Python `dataclass`-based originals:
//!
//! * `VarData` is *frozen* (immutable after construction) and hash-equal so it
//!   can be stored in sets/dicts on the Python side.
//! * `VarData::merge` flattens a chain of `Option<&VarData>` into a single
//!   merged `Option<VarData>`, preserving first-seen ordering of hooks/imports
//!   and union-ing the rest. The Python implementation lives at
//!   `packages/reflex-base/src/reflex_base/vars/base.py:200-270`.
//! * `Var` carries the final `_js_expr` string + optional `VarData`. The
//!   typed-expression hierarchy (`NumberVar`, `StringVar`, …) lands in
//!   follow-up iterations.

mod var;
mod var_data;

pub use var::Var;
pub use var_data::{HookPosition, ImportVar, VarData};
