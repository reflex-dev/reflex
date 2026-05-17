//! PyO3 Component-tree reader. See plan §0b lever (a).
//!
//! Replaces `reflex/compiler/ir/bridge.py` by walking Reflex `Component`
//! PyObjects directly via PyO3 `getattr`. Each Python attribute access is
//! ~100 ns (per spike measurement); a 165-node page costs ~80 µs, vs
//! ~3.9 ms for the msgpack bridge.
//!
//! The reader produces the same `reflex_ir::Component<'arena>` tree the
//! msgpack parser produces, so downstream codegen is unchanged. Strings
//! are arena-allocated; identifiers are interned.
//!
//! The pyo3 dep is feature-gated (default-on). `--no-default-features`
//! builds skip pyo3 so the pure-Rust helpers in `text` can be unit-tested
//! without libpython on the system linker — uv's snap-managed Python isn't
//! visible to `cc`. End-to-end coverage of the PyO3 reader runs through
//! `reflex_py`'s wheel tests (plan task #7).

#![forbid(unsafe_code)]

pub mod text;

#[cfg(feature = "pyo3")]
mod pyo3_reader;

#[cfg(feature = "pyo3")]
pub mod memoize;

#[cfg(feature = "pyo3")]
pub mod imports;

#[cfg(feature = "pyo3")]
pub mod timing;

#[cfg(feature = "pyo3")]
pub use pyo3_reader::{read_page, PyReadError, PyRefs};

#[cfg(feature = "pyo3")]
pub use memoize::{should_memoize, MemoRefs};

#[cfg(feature = "pyo3")]
pub use imports::{collect_all_imports, collect_all_imports_into, merge_imports_into};

#[cfg(feature = "pyo3")]
pub use timing::{
    Counter as TimingCounter, Field as TimingField, PhaseTimings, Span as TimingSpan,
};
