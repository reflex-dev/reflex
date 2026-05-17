//! PyO3 entry for the reflex-compiler-rust wheel.
//!
//! Two surfaces live here:
//!
//! 1. The spike microbenchmark probes (`empty_call`, `walk_*`) — preserved
//!    because `scripts/spike_bench.py` and `SPIKE_RESULTS.md` reference them.
//!    Spike wire format: positional msgpack arrays, simple shape documented
//!    inline below.
//!
//! 2. `CompilerSession` — the real entry point. Takes a §4 PageIR msgpack
//!    blob, runs the parse → JSX-emit pipeline, returns a JS source string.
//!    Salsa caching lands in D5 — for now every call rebuilds.

mod session;

use std::io::Cursor;

use bumpalo::Bump;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use rmp::decode::{self, RmpRead};
use serde::Deserialize;

// ---- 1. Pure crossing probes -------------------------------------------------

#[pyfunction]
fn empty_call() {}

#[pyfunction]
fn add_one(x: i64) -> i64 {
    x + 1
}

#[pyfunction]
fn bytes_passthrough(b: &Bound<'_, PyBytes>) -> usize {
    b.as_bytes().len()
}

// ---- 2. rmp-serde path -------------------------------------------------------

#[derive(Deserialize)]
#[serde(untagged)]
enum SerdeNode {
    Element(u8, String, Vec<(String, String)>, Vec<SerdeNode>),
    Text(u8, String),
}

fn serde_walk(n: &SerdeNode, nodes: &mut u64, bytes: &mut u64) {
    match n {
        SerdeNode::Element(_, tag, props, children) => {
            *nodes += 1;
            *bytes += tag.len() as u64;
            for (k, v) in props {
                *bytes += (k.len() + v.len()) as u64;
            }
            for c in children {
                serde_walk(c, nodes, bytes);
            }
        }
        SerdeNode::Text(_, s) => {
            *nodes += 1;
            *bytes += s.len() as u64;
        }
    }
}

#[pyfunction]
fn walk_serde(b: &Bound<'_, PyBytes>) -> PyResult<(u64, u64)> {
    let bytes = b.as_bytes();
    let root: SerdeNode = rmp_serde::from_slice(bytes)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("rmp-serde: {e}")))?;
    let mut n = 0u64;
    let mut s = 0u64;
    serde_walk(&root, &mut n, &mut s);
    Ok((n, s))
}

// ---- 3. Hand-rolled msgpack reader, zero-copy borrows -----------------------
//
// rmp::decode lets us read length-prefixed scalars and use the remaining cursor
// to take string bytes as &[u8] without copying. We then `str::from_utf8` (which
// is a check, not a copy). No heap allocations on the parse side at all.
//
// Walking happens inline with parsing — we never materialize the tree. That's
// exactly what real Rust codegen would do; this is the realistic lower bound.

fn manual_read_str<'a>(buf: &mut &'a [u8]) -> std::io::Result<&'a str> {
    let len = decode::read_str_len(buf).map_err(|e| std::io::Error::other(e.to_string()))? as usize;
    if buf.len() < len {
        return Err(std::io::Error::other("short read"));
    }
    let (s, rest) = buf.split_at(len);
    *buf = rest;
    std::str::from_utf8(s).map_err(|e| std::io::Error::other(e.to_string()))
}

fn manual_walk<'a>(buf: &mut &'a [u8], nodes: &mut u64, bytes: &mut u64) -> std::io::Result<()> {
    let arr_len = decode::read_array_len(buf).map_err(|e| std::io::Error::other(e.to_string()))?;
    let kind = buf.read_u8()?;
    *nodes += 1;
    if kind == 0 {
        // [0, tag, props, children]  -> arr_len == 4
        debug_assert_eq!(arr_len, 4);
        let tag = manual_read_str(buf)?;
        *bytes += tag.len() as u64;
        let n_props =
            decode::read_array_len(buf).map_err(|e| std::io::Error::other(e.to_string()))?;
        for _ in 0..n_props {
            let pair_len =
                decode::read_array_len(buf).map_err(|e| std::io::Error::other(e.to_string()))?;
            debug_assert_eq!(pair_len, 2);
            let k = manual_read_str(buf)?;
            let v = manual_read_str(buf)?;
            *bytes += (k.len() + v.len()) as u64;
        }
        let n_children =
            decode::read_array_len(buf).map_err(|e| std::io::Error::other(e.to_string()))?;
        for _ in 0..n_children {
            manual_walk(buf, nodes, bytes)?;
        }
    } else {
        // [1, value]
        debug_assert_eq!(arr_len, 2);
        let v = manual_read_str(buf)?;
        *bytes += v.len() as u64;
    }
    Ok(())
}

#[pyfunction]
fn walk_manual(b: &Bound<'_, PyBytes>) -> PyResult<(u64, u64)> {
    let mut cur: &[u8] = b.as_bytes();
    let mut n = 0u64;
    let mut s = 0u64;
    manual_walk(&mut cur, &mut n, &mut s)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("manual walk: {e}")))?;
    Ok((n, s))
}

// ---- 4. Hand-rolled walk + JSX-like emit into a buffer ----------------------
//
// This is what a real Rust codegen pass would do: parse and emit in a single
// streaming pass, writing into one growable byte buffer. No arena needed for
// this shape because the output buffer IS the only allocation.

fn emit_str(out: &mut Vec<u8>, s: &str) {
    out.push(b'"');
    out.extend_from_slice(s.as_bytes());
    out.push(b'"');
}

fn manual_walk_emit<'a>(buf: &mut &'a [u8], out: &mut Vec<u8>) -> std::io::Result<()> {
    let _ = decode::read_array_len(buf).map_err(|e| std::io::Error::other(e.to_string()))?;
    let kind = buf.read_u8()?;
    if kind == 0 {
        let tag = manual_read_str(buf)?;
        out.extend_from_slice(b"jsx(");
        out.extend_from_slice(tag.as_bytes());
        out.extend_from_slice(b",{");
        let n_props =
            decode::read_array_len(buf).map_err(|e| std::io::Error::other(e.to_string()))?;
        for i in 0..n_props {
            if i > 0 {
                out.push(b',');
            }
            let _ =
                decode::read_array_len(buf).map_err(|e| std::io::Error::other(e.to_string()))?;
            let k = manual_read_str(buf)?;
            let v = manual_read_str(buf)?;
            out.extend_from_slice(k.as_bytes());
            out.push(b':');
            out.extend_from_slice(v.as_bytes());
        }
        out.push(b'}');
        let n_children =
            decode::read_array_len(buf).map_err(|e| std::io::Error::other(e.to_string()))?;
        for _ in 0..n_children {
            out.push(b',');
            manual_walk_emit(buf, out)?;
        }
        out.push(b')');
    } else {
        let v = manual_read_str(buf)?;
        emit_str(out, v);
    }
    Ok(())
}

#[pyfunction]
fn walk_manual_emit<'py>(py: Python<'py>, b: &Bound<'py, PyBytes>) -> PyResult<Bound<'py, PyBytes>> {
    let input = b.as_bytes().to_vec(); // copy out before releasing GIL
    let out = py
        .allow_threads(|| -> std::io::Result<Vec<u8>> {
            let mut cur: &[u8] = &input;
            let mut out = Vec::with_capacity(input.len() * 2);
            manual_walk_emit(&mut cur, &mut out)?;
            Ok(out)
        })
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("emit: {e}")))?;
    Ok(PyBytes::new_bound(py, &out))
}

// ---- 5. Bumpalo arena demo --------------------------------------------------
//
// Parse the tree into a bumpalo-backed AST (Copy nodes, &str borrows into a
// owned String copy in the arena), then walk it. Tests R1/R2: arena holds the
// tree; nothing leaks; drop is a single bump reset.

#[derive(Clone, Copy)]
enum ArenaNode<'a> {
    Element {
        tag: &'a str,
        props: &'a [(&'a str, &'a str)],
        children: &'a [ArenaNode<'a>],
    },
    Text(&'a str),
}

fn parse_arena<'a, 'b>(buf: &mut &'b [u8], arena: &'a Bump) -> std::io::Result<ArenaNode<'a>>
where
    'b: 'a,
{
    let _ = decode::read_array_len(buf).map_err(|e| std::io::Error::other(e.to_string()))?;
    let kind = buf.read_u8()?;
    if kind == 0 {
        let tag = arena.alloc_str(manual_read_str(buf)?);
        let n_props =
            decode::read_array_len(buf).map_err(|e| std::io::Error::other(e.to_string()))? as usize;
        let mut props = bumpalo::collections::Vec::with_capacity_in(n_props, arena);
        for _ in 0..n_props {
            let _ =
                decode::read_array_len(buf).map_err(|e| std::io::Error::other(e.to_string()))?;
            let k = arena.alloc_str(manual_read_str(buf)?);
            let v = arena.alloc_str(manual_read_str(buf)?);
            props.push((&*k, &*v));
        }
        let n_children =
            decode::read_array_len(buf).map_err(|e| std::io::Error::other(e.to_string()))? as usize;
        let mut children = bumpalo::collections::Vec::with_capacity_in(n_children, arena);
        for _ in 0..n_children {
            children.push(parse_arena(buf, arena)?);
        }
        Ok(ArenaNode::Element {
            tag,
            props: props.into_bump_slice(),
            children: children.into_bump_slice(),
        })
    } else {
        Ok(ArenaNode::Text(arena.alloc_str(manual_read_str(buf)?)))
    }
}

fn arena_emit(node: &ArenaNode<'_>, out: &mut Vec<u8>) {
    match node {
        ArenaNode::Element { tag, props, children } => {
            out.extend_from_slice(b"jsx(");
            out.extend_from_slice(tag.as_bytes());
            out.extend_from_slice(b",{");
            for (i, (k, v)) in props.iter().enumerate() {
                if i > 0 {
                    out.push(b',');
                }
                out.extend_from_slice(k.as_bytes());
                out.push(b':');
                out.extend_from_slice(v.as_bytes());
            }
            out.push(b'}');
            for c in *children {
                out.push(b',');
                arena_emit(c, out);
            }
            out.push(b')');
        }
        ArenaNode::Text(s) => emit_str(out, s),
    }
}

#[pyfunction]
fn walk_arena_emit<'py>(py: Python<'py>, b: &Bound<'py, PyBytes>) -> PyResult<Bound<'py, PyBytes>> {
    let input = b.as_bytes().to_vec();
    let out = py
        .allow_threads(|| -> std::io::Result<Vec<u8>> {
            let arena = Bump::with_capacity(input.len() * 2);
            let mut cur: &[u8] = &input;
            let root = parse_arena(&mut cur, &arena)?;
            let mut out = Vec::with_capacity(input.len() * 2);
            arena_emit(&root, &mut out);
            Ok(out)
        })
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("arena emit: {e}")))?;
    Ok(PyBytes::new_bound(py, &out))
}

// ---- 6. rmp-serde + emit (for apples-to-apples vs hand-rolled) --------------

fn serde_emit(n: &SerdeNode, out: &mut Vec<u8>) {
    match n {
        SerdeNode::Element(_, tag, props, children) => {
            out.extend_from_slice(b"jsx(");
            out.extend_from_slice(tag.as_bytes());
            out.extend_from_slice(b",{");
            for (i, (k, v)) in props.iter().enumerate() {
                if i > 0 {
                    out.push(b',');
                }
                out.extend_from_slice(k.as_bytes());
                out.push(b':');
                out.extend_from_slice(v.as_bytes());
            }
            out.push(b'}');
            for c in children {
                out.push(b',');
                serde_emit(c, out);
            }
            out.push(b')');
        }
        SerdeNode::Text(_, s) => emit_str(out, s),
    }
}

#[pyfunction]
fn walk_serde_emit<'py>(py: Python<'py>, b: &Bound<'py, PyBytes>) -> PyResult<Bound<'py, PyBytes>> {
    let input = b.as_bytes().to_vec();
    let out = py
        .allow_threads(|| -> PyResult<Vec<u8>> {
            let mut de = rmp_serde::Deserializer::new(Cursor::new(&input));
            let root: SerdeNode = SerdeNode::deserialize(&mut de)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("rmp-serde: {e}")))?;
            let mut out = Vec::with_capacity(input.len() * 2);
            serde_emit(&root, &mut out);
            Ok(out)
        })?;
    Ok(PyBytes::new_bound(py, &out))
}

// ---- Module export ----------------------------------------------------------

#[pymodule]
fn _native(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Spike probes.
    m.add_function(wrap_pyfunction!(empty_call, m)?)?;
    m.add_function(wrap_pyfunction!(add_one, m)?)?;
    m.add_function(wrap_pyfunction!(bytes_passthrough, m)?)?;
    m.add_function(wrap_pyfunction!(walk_serde, m)?)?;
    m.add_function(wrap_pyfunction!(walk_manual, m)?)?;
    m.add_function(wrap_pyfunction!(walk_manual_emit, m)?)?;
    m.add_function(wrap_pyfunction!(walk_arena_emit, m)?)?;
    m.add_function(wrap_pyfunction!(walk_serde_emit, m)?)?;

    // Schema version sanity (parsers agree with the wire format).
    m.add("SCHEMA_VERSION", reflex_ir::parse::SCHEMA_VERSION)?;

    // The real compiler session.
    m.add_class::<session::CompilerSession>()?;
    m.add_class::<session::CompiledOutput>()?;
    Ok(())
}
