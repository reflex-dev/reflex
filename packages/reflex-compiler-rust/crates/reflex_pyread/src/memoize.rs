//! Rust port of `reflex.compiler.plugins.memoize._should_memoize` and
//! `_subtree_has_reactive_data`. See plan §0a phase 2 / §0b lever (b2).
//!
//! Operates on Python `Component` PyObjects via PyO3 — the framework
//! primitives (`Component._memoization_mode`, `Component._get_vars`,
//! `_get_hooks_internal`, `Var._get_all_var_data`, etc.) are read with
//! `getattr`/`call_method` instead of through the IR. The decision logic
//! itself runs in Rust.
//!
//! Used by:
//!
//! * `compute_should_memoize(component)` — PyO3-exposed predicate that
//!   matches the legacy plugin's per-node decision. Foundation for
//!   phase 3, where wrapper construction moves to Rust too.

use std::collections::{HashMap, HashSet};

use pyo3::prelude::*;
use pyo3::types::{PyAnyMethods, PyDict};

use super::pyo3_reader::{class_name, py_str, PyReadError, PyRefs};

/// Memoize plugin's per-node decision, ported from
/// `reflex.compiler.plugins.memoize._should_memoize`.
///
/// Returns `Ok(true)` iff `component` is a candidate for auto-memoization.
/// The PyO3 boundary keeps the contract identical to the Python version —
/// every framework lookup (disposition, hooks, vars, var_data) goes
/// through `getattr`/`call_method` on the live Component.
pub fn should_memoize<'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
    refs: &MemoRefs<'py>,
) -> Result<bool, PyReadError> {
    let disposition = read_disposition(component)?;
    if disposition == Disposition::Never {
        return Ok(false);
    }

    let cls = class_name(component)?;

    // Bare: short-circuit on contents-Var's var_data.
    if cls == "Bare" {
        if let Some(b) = bare_should_memoize(py, component, refs)? {
            if b {
                return Ok(true);
            }
        }
    }

    let tag = component
        .getattr("tag")
        .ok()
        .filter(|v| !v.is_none());
    let is_cond_or_match = matches!(cls.as_str(), "Cond" | "Match");
    let is_structural_child = is_structural_memoization_child(&cls);
    if tag.is_none() && !is_cond_or_match && !is_structural_child {
        return Ok(false);
    }

    if disposition == Disposition::Always {
        return Ok(true);
    }

    // Direct props (include_children=False).
    let prop_vars = component
        .call_method1("_get_vars", (false,))
        .map_err(|source| PyReadError::Attr {
            attr: "Component._get_vars(include_children=False)",
            source,
        })?;
    let prop_iter = prop_vars.iter().map_err(|source| PyReadError::Attr {
        attr: "iter(_get_vars())",
        source,
    })?;
    let mut cache: HashMap<usize, bool> = HashMap::new();
    for var_res in prop_iter {
        let prop_var = var_res.map_err(|source| PyReadError::Attr {
            attr: "_get_vars()[i]",
            source,
        })?;
        if var_data_indicates_reactive(py, &prop_var, refs, &mut cache)? {
            return Ok(true);
        }
    }

    let boundary = is_snapshot_boundary(component)?;
    if is_strategy_snapshot(boundary, is_structural_child) && !boundary {
        return Ok(true);
    }
    if boundary && subtree_has_reactive_data(py, component, refs, &mut cache)? {
        return Ok(true);
    }

    // Event triggers — non-empty dict means memo-wrap to stabilize callbacks.
    let triggers = component
        .getattr("event_triggers")
        .ok()
        .filter(|v| !v.is_none());
    match triggers {
        Some(t) => {
            let has = match t.downcast::<PyDict>() {
                Ok(d) => !d.is_empty(),
                Err(_) => t.is_truthy().unwrap_or(false),
            };
            Ok(has)
        }
        None => Ok(false),
    }
}

/// Whether `component`'s subtree carries reactive signals worth memoizing.
///
/// Mirrors `_subtree_has_reactive_data` + `_component_subtree_is_reactive`.
/// The `id()`-keyed cache breaks the `var_data.components` ↔ children
/// graph cycles the same way the Python version does.
pub fn subtree_has_reactive_data<'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
    refs: &MemoRefs<'py>,
    cache: &mut HashMap<usize, bool>,
) -> Result<bool, PyReadError> {
    let id = component.as_ptr() as usize;
    if let Some(&cached) = cache.get(&id) {
        return Ok(cached);
    }
    // Placeholder to break cycles — matches Python.
    cache.insert(id, false);
    let result = component_subtree_is_reactive(py, component, refs, cache)?;
    cache.insert(id, result);
    Ok(result)
}

fn component_subtree_is_reactive<'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
    refs: &MemoRefs<'py>,
    cache: &mut HashMap<usize, bool>,
) -> Result<bool, PyReadError> {
    // Filter out the ref hook (static-id useRef) from _get_hooks_internal.
    let ref_hook = component
        .call_method0("_get_ref_hook")
        .map_err(|source| PyReadError::Attr {
            attr: "Component._get_ref_hook",
            source,
        })?;
    let ref_hook_key: Option<String> = if ref_hook.is_none() {
        None
    } else {
        Some(py_str(&ref_hook)?)
    };

    let hooks_internal = component
        .call_method0("_get_hooks_internal")
        .map_err(|source| PyReadError::Attr {
            attr: "Component._get_hooks_internal",
            source,
        })?;
    if !hooks_internal.is_none() {
        // `_get_hooks_internal` returns a dict (or dict-like) keyed by
        // hook code; iterate keys uniformly via the generic Python iter
        // protocol (works for both PyDict and any dict-shaped mapping).
        let iterable: Bound<'_, PyAny> = if let Ok(d) = hooks_internal.downcast::<PyDict>() {
            d.keys().into_any()
        } else {
            hooks_internal.clone()
        };
        for k_res in iterable.iter().map_err(|source| PyReadError::Attr {
            attr: "iter(_get_hooks_internal())",
            source,
        })? {
            let k = k_res.map_err(|source| PyReadError::Attr {
                attr: "_get_hooks_internal()[i]",
                source,
            })?;
            let key_str = py_str(&k)?;
            if ref_hook_key.as_deref() != Some(key_str.as_str()) {
                return Ok(true);
            }
        }
    }

    let hooks_str = component
        .call_method0("_get_hooks")
        .map_err(|source| PyReadError::Attr {
            attr: "Component._get_hooks",
            source,
        })?;
    if !hooks_str.is_none() {
        return Ok(true);
    }
    let added = component
        .call_method0("_get_added_hooks")
        .map_err(|source| PyReadError::Attr {
            attr: "Component._get_added_hooks",
            source,
        })?;
    if !added.is_none() && added.is_truthy().unwrap_or(false) {
        return Ok(true);
    }

    // Own props (include_children=False).
    let prop_vars = component
        .call_method1("_get_vars", (false,))
        .map_err(|source| PyReadError::Attr {
            attr: "Component._get_vars(include_children=False)",
            source,
        })?;
    for var_res in prop_vars.iter().map_err(|source| PyReadError::Attr {
        attr: "iter(_get_vars())",
        source,
    })? {
        let var = var_res.map_err(|source| PyReadError::Attr {
            attr: "_get_vars()[i]",
            source,
        })?;
        if var_data_indicates_reactive(py, &var, refs, cache)? {
            return Ok(true);
        }
    }

    // Children.
    let children = component
        .getattr("children")
        .ok()
        .filter(|v| !v.is_none());
    if let Some(c) = children {
        for child_res in c.iter().map_err(|source| PyReadError::Attr {
            attr: "iter(children)",
            source,
        })? {
            let child = child_res.map_err(|source| PyReadError::Attr {
                attr: "children[i]",
                source,
            })?;
            // The legacy walk only recurses through Components. Non-
            // Component children (raw strings, numbers wrapped at compile
            // time) carry no reactive signal.
            if !is_component_subclass(&child, refs)? {
                continue;
            }
            if subtree_has_reactive_data(py, &child, refs, cache)? {
                return Ok(true);
            }
        }
    }
    Ok(false)
}

/// `var._get_all_var_data()` carries `state`, `hooks`, and `components`.
/// Returns True iff any of those signals fire.
fn var_data_indicates_reactive<'py>(
    py: Python<'py>,
    var: &Bound<'py, PyAny>,
    refs: &MemoRefs<'py>,
    cache: &mut HashMap<usize, bool>,
) -> Result<bool, PyReadError> {
    let vd = var
        .call_method0("_get_all_var_data")
        .map_err(|source| PyReadError::Attr {
            attr: "Var._get_all_var_data",
            source,
        })?;
    if vd.is_none() {
        return Ok(false);
    }
    if attr_truthy(&vd, "state")? || attr_truthy(&vd, "hooks")? {
        return Ok(true);
    }
    let embedded = match vd.getattr("components") {
        Ok(v) if !v.is_none() => v,
        _ => return Ok(false),
    };
    for item_res in embedded.iter().map_err(|source| PyReadError::Attr {
        attr: "iter(var_data.components)",
        source,
    })? {
        let item = item_res.map_err(|source| PyReadError::Attr {
            attr: "var_data.components[i]",
            source,
        })?;
        if !is_component_subclass(&item, refs)? {
            continue;
        }
        if subtree_has_reactive_data(py, &item, refs, cache)? {
            return Ok(true);
        }
    }
    Ok(false)
}

fn bare_should_memoize<'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
    refs: &MemoRefs<'py>,
) -> Result<Option<bool>, PyReadError> {
    let contents = component
        .getattr("contents")
        .ok()
        .filter(|v| !v.is_none());
    let Some(contents) = contents else {
        return Ok(None);
    };
    // Only Vars carry var_data. Non-Var contents short-circuit to None.
    let is_var = contents
        .is_instance(&refs.var_cls)
        .map_err(|source| PyReadError::Attr {
            attr: "isinstance(Bare.contents, Var)",
            source,
        })?;
    if !is_var {
        return Ok(None);
    }
    let mut cache: HashMap<usize, bool> = HashMap::new();
    Ok(Some(var_data_indicates_reactive(py, &contents, refs, &mut cache)?))
}

// ---- Helpers ---------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Disposition {
    Stateful,
    Always,
    Never,
}

fn read_disposition(component: &Bound<'_, PyAny>) -> Result<Disposition, PyReadError> {
    let mode = component
        .getattr("_memoization_mode")
        .map_err(|source| PyReadError::Attr {
            attr: "Component._memoization_mode",
            source,
        })?;
    let disp = mode
        .getattr("disposition")
        .map_err(|source| PyReadError::Attr {
            attr: "MemoizationMode.disposition",
            source,
        })?;
    let value = disp
        .getattr("value")
        .map_err(|source| PyReadError::Attr {
            attr: "MemoizationDisposition.value",
            source,
        })?;
    let s = py_str(&value)?;
    match s.as_str() {
        "stateful" => Ok(Disposition::Stateful),
        "always" => Ok(Disposition::Always),
        "never" => Ok(Disposition::Never),
        other => Err(PyReadError::TypeMismatch {
            attr: "MemoizationDisposition.value",
            expected: "stateful|always|never",
            got: other.to_owned(),
        }),
    }
}

fn is_snapshot_boundary(component: &Bound<'_, PyAny>) -> Result<bool, PyReadError> {
    let mode = component
        .getattr("_memoization_mode")
        .map_err(|source| PyReadError::Attr {
            attr: "Component._memoization_mode",
            source,
        })?;
    let recursive = mode
        .getattr("recursive")
        .map_err(|source| PyReadError::Attr {
            attr: "MemoizationMode.recursive",
            source,
        })?;
    let r: bool = recursive.extract().map_err(|source| PyReadError::Attr {
        attr: "recursive.extract::<bool>()",
        source,
    })?;
    Ok(!r)
}

fn is_structural_memoization_child(cls_name: &str) -> bool {
    // Mirrors `_is_structural_memoization_child` — currently restricted
    // to `Foreach`.
    cls_name == "Foreach"
}

fn is_strategy_snapshot(boundary: bool, structural_child: bool) -> bool {
    // `get_memoization_strategy` returns SNAPSHOT iff snapshot boundary
    // or structural child.
    boundary || structural_child
}

fn attr_truthy(obj: &Bound<'_, PyAny>, name: &str) -> Result<bool, PyReadError> {
    let v = obj.getattr(name).ok().filter(|v| !v.is_none());
    Ok(match v {
        Some(x) => x.is_truthy().unwrap_or(false),
        None => false,
    })
}

fn is_component_subclass(obj: &Bound<'_, PyAny>, refs: &MemoRefs<'_>) -> Result<bool, PyReadError> {
    obj.is_instance(&refs.component_cls)
        .map_err(|source| PyReadError::Attr {
            attr: "isinstance(obj, Component)",
            source,
        })
}

// ---- Cached PyObjects ------------------------------------------------------

/// Framework classes the memoize-decision walk uses.
///
/// Built on top of `PyRefs` (Var/LiteralVar) — we cache the `Component`
/// class here too so children/var_data.components can be filtered by
/// type quickly. Building this once per page mirrors the cost story of
/// pyread itself: ~10 µs lookup amortized across hundreds of nodes.
pub struct MemoRefs<'py> {
    pub var_cls: Bound<'py, PyAny>,
    pub component_cls: Bound<'py, PyAny>,
}

impl<'py> MemoRefs<'py> {
    pub fn from_pyrefs(py: Python<'py>, pyrefs: &PyRefs<'py>) -> Result<Self, PyReadError> {
        let component_cls = py
            .import_bound("reflex_base.components.component")
            .and_then(|m| m.getattr("Component"))
            .map_err(|source| PyReadError::Attr {
                attr: "reflex_base.components.component.Component",
                source,
            })?;
        Ok(Self {
            var_cls: pyrefs.var_cls.clone(),
            component_cls,
        })
    }
}

// Unused-import guard for the HashSet import — kept around for future
// use (the legacy walk could be extended with per-page seen-sets).
#[allow(dead_code)]
fn _hash_set_marker() -> HashSet<usize> {
    HashSet::new()
}
