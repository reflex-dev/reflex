//! Rust mirror of `reflex_base.components.component.Component._get_all_imports`
//! and `reflex_base.utils.imports.merge_imports`.
//!
//! Why this exists: profiling `reflex run-rust` on the docs app showed
//! `_get_all_imports` + `merge_imports` at ~1.3 s cumulative for 7 pages
//! — 5.2M iterations through a Python generator. Pushing the walk and
//! merge into Rust drops the inner recursion and lets `compile_pages`
//! accumulate into a single Python dict in-place instead of rebuilding
//! it once per page / memo body.
//!
//! Three entry points:
//!
//! * [`collect_all_imports`] — non-mutating: returns a fresh dict
//!   shaped like `_get_all_imports` returns (no `$` prefix).
//! * [`collect_all_imports_into`] — walks the tree and **merges into a
//!   caller-owned target dict** with the `$/utils/...` prefix transform
//!   applied per key. Replaces the legacy
//!   `merge_imports(target, component._get_all_imports())` pattern.
//! * [`merge_imports_into`] — same prefix transform applied to an
//!   already-built `ParsedImportDict`, no tree walk.
//!
//! The per-Component `_get_imports` work stays on the Python side because
//! user subclasses override it via `add_imports()`; the walker dispatches
//! through PyO3 callbacks rather than reimplementing the override chain.
//!
//! See `RUST_REWRITE_PLAN.md` lever (a) — page-level harvest walks.

use std::collections::HashMap;

use pyo3::prelude::*;
use pyo3::types::{PyAnyMethods, PyDict, PyList, PyString, PyStringMethods};

/// Library-name prefixes that get rewritten to `$<prefix>` so Vite's
/// `$` alias resolves them to `.web/<prefix>/...`. Mirrors
/// `reflex_base.utils.imports.merge_imports`.
const ALIAS_PREFIXES: &[&str] = &["/utils/", "/components/", "/styles/", "/public/"];

fn apply_alias_prefix(lib: &str) -> String {
    if ALIAS_PREFIXES.iter().any(|p| lib.starts_with(p)) {
        let mut out = String::with_capacity(lib.len() + 1);
        out.push('$');
        out.push_str(lib);
        out
    } else {
        lib.to_owned()
    }
}

/// Walk `root`'s component tree (children + `_get_components_in_props()`)
/// and return a merged `dict[str, list[ImportVar]]` — no `$/utils/...`
/// rewrite. Use this when the caller wants the raw shape Python's
/// `_get_all_imports` returns.
pub fn collect_all_imports<'py>(
    py: Python<'py>,
    root: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyDict>> {
    let mut acc: HashMap<String, Vec<PyObject>> = HashMap::new();
    walk_raw(py, root, &mut acc)?;

    let out = PyDict::new_bound(py);
    for (lib, items) in acc {
        let list = PyList::new_bound(py, items);
        out.set_item(lib, list)?;
    }
    Ok(out)
}

/// Walk `root`'s tree like [`collect_all_imports`], applying the
/// `$/utils/...` prefix transform per key, and append every entry into
/// `target` in place. The caller-owned target dict is mutated so the
/// page loop can accumulate across pages without rebuilding the dict on
/// each iteration — the costly pattern profiling exposed.
///
/// `target` is expected to be `dict[str, list[ImportVar]]`. For
/// libraries already present in `target`, items are appended to the
/// existing list; otherwise a fresh list is created.
pub fn collect_all_imports_into<'py>(
    py: Python<'py>,
    target: &Bound<'py, PyDict>,
    root: &Bound<'py, PyAny>,
) -> PyResult<()> {
    walk_into(py, root, target)
}

/// Apply the `$/utils/...` prefix transform to every entry of `source`
/// and append into `target` in place. Equivalent to
/// `merge_imports(target, source)` from
/// `reflex_base.utils.imports` for the `ParsedImportDict` case (no
/// `str`/`set`/`tuple` field dispatch — callers must pre-normalize via
/// `parse_imports` if needed).
pub fn merge_imports_into<'py>(
    py: Python<'py>,
    target: &Bound<'py, PyDict>,
    source: &Bound<'py, PyDict>,
) -> PyResult<()> {
    for (lib_obj, items_obj) in source.iter() {
        let lib_str = lib_obj.downcast::<PyString>()?.to_str()?;
        let new_lib = apply_alias_prefix(lib_str);
        append_items(py, target, &new_lib, &items_obj)?;
    }
    Ok(())
}

fn walk_raw<'py>(
    py: Python<'py>,
    node: &Bound<'py, PyAny>,
    acc: &mut HashMap<String, Vec<PyObject>>,
) -> PyResult<()> {
    let imports_obj = node.call_method0("_get_imports")?;
    let imports_dict = imports_obj.downcast::<PyDict>()?;
    for (lib_obj, items_obj) in imports_dict.iter() {
        let lib_py = lib_obj.downcast::<PyString>()?;
        let lib = lib_py.to_str()?.to_owned();
        let items_list = items_obj.downcast::<PyList>()?;
        let bucket = acc.entry(lib).or_default();
        bucket.reserve(items_list.len());
        for item in items_list.iter() {
            bucket.push(item.unbind());
        }
    }

    recurse_children_and_prop_components(py, node, &mut |child| walk_raw(py, child, acc))
}

fn walk_into<'py>(
    py: Python<'py>,
    node: &Bound<'py, PyAny>,
    target: &Bound<'py, PyDict>,
) -> PyResult<()> {
    let imports_obj = node.call_method0("_get_imports")?;
    let imports_dict = imports_obj.downcast::<PyDict>()?;
    for (lib_obj, items_obj) in imports_dict.iter() {
        let lib_str = lib_obj.downcast::<PyString>()?.to_str()?;
        let new_lib = apply_alias_prefix(lib_str);
        append_items(py, target, &new_lib, &items_obj)?;
    }

    recurse_children_and_prop_components(py, node, &mut |child| walk_into(py, child, target))
}

fn recurse_children_and_prop_components<'py, F>(
    py: Python<'py>,
    node: &Bound<'py, PyAny>,
    visit: &mut F,
) -> PyResult<()>
where
    F: FnMut(&Bound<'py, PyAny>) -> PyResult<()>,
{
    if let Ok(children) = node.getattr("children") {
        if !children.is_none() {
            if let Ok(iter) = children.iter() {
                for c in iter {
                    let child = c?;
                    visit(&child)?;
                }
            }
        }
    }

    if let Ok(prop_components) = node.call_method0("_get_components_in_props") {
        if let Ok(iter) = prop_components.iter() {
            for c in iter {
                let prop_comp = c?;
                visit(&prop_comp)?;
            }
        }
    }

    let _ = py;
    Ok(())
}

/// Append every element of `items_obj` (any iterable, but typically a
/// `list[ImportVar]`) to `target[lib]`. Creates the bucket as a fresh
/// `list` on first sight so we never mutate a cached `_get_imports()`
/// result.
fn append_items<'py>(
    py: Python<'py>,
    target: &Bound<'py, PyDict>,
    lib: &str,
    items_obj: &Bound<'py, PyAny>,
) -> PyResult<()> {
    let items_list = items_obj.downcast::<PyList>()?;
    match target.get_item(lib)? {
        Some(existing) => {
            let existing_list = existing.downcast::<PyList>()?;
            existing_list.call_method1("extend", (items_list,))?;
        }
        None => {
            let new_list = PyList::empty_bound(py);
            new_list.call_method1("extend", (items_list,))?;
            target.set_item(lib, new_list)?;
        }
    }
    Ok(())
}
