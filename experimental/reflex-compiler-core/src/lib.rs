//! Proving slice for a Rust-native Reflex compiler core.
//!
//! The thesis under test: the dominant Reflex compile cost is per-component
//! Python instantiation (`Component._post_init` -> per-prop `LiteralVar.create`
//! + `satisfies_type_hint`, per-event `EventChain.create`, on top of the
//! pydantic model machinery). This crate skips all of it: `make_node` receives
//! raw props + child handles and builds a native Rust node directly. Literal
//! props are rendered straight to JS here (no Python `Var`). The Python
//! `Component` object is never instantiated for the fast-path components.
//!
//! A node child may itself be a Python component (a custom/overriding component
//! that cannot be a fast node yet); it is stored as an opaque `Py` leaf and
//! rendered by calling back into Reflex's `_RenderUtils` — the pydantic-core
//! `FunctionWrapValidator` fallback pattern.

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyString};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{OnceLock, RwLock};

/// Strict purity mode. When on, any Python-component fallback is a hard error
/// instead of a silent delegation — so a "ported" component cannot quietly
/// regress to calling Python and still pass a string-equality test.
static STRICT: AtomicBool = AtomicBool::new(false);

/// Count of non-native subtrees since the last reset (the "cheat ledger"). A
/// fully native build leaves this at 0. Incremented whenever a child cannot be
/// built natively and is captured as a pre-rendered dict instead.
static PY_FALLBACKS: AtomicUsize = AtomicUsize::new(0);

/// Component registry: name -> how to build its node natively. Populated from
/// the Python class definitions by `register_component` (the code-generated
/// registry the design calls for). This is what closes the prop-ordering gap
/// and lets one generic factory cover every registered component.
struct CompSpec {
    /// JS tag/identifier. Elements are JSON-quoted ("div"); imported components
    /// are bare identifiers.
    tag: String,
    is_element: bool,
}

static REGISTRY: OnceLock<RwLock<HashMap<String, CompSpec>>> = OnceLock::new();

fn registry() -> &'static RwLock<HashMap<String, CompSpec>> {
    REGISTRY.get_or_init(|| RwLock::new(HashMap::new()))
}

/// A child of a Rust node: another native node, or a non-native subtree kept as
/// a pre-rendered Python dict (codegen still runs natively over the dict; only
/// the *construction* stayed in Python — distinct from full native).
enum RChild {
    Node(RNode),
    RawDict(Py<PyAny>),
}

/// A native component node. Mirrors the two render-dict shapes this slice
/// covers: an element (`{name, props, children}`) and a bare text node
/// (`{contents}`).
enum RNode {
    Element {
        name: String,
        props: Vec<String>,
        children: Vec<RChild>,
    },
    Bare {
        contents: String,
    },
}

/// Lightweight handle returned to Python. Wraps a `NodeId`-equivalent owned
/// subtree; `inner` is consumed (`take`n) when this handle becomes a child of
/// another node, so the tree is moved into the parent without copying.
#[pyclass(unsendable)]
struct NodeHandle {
    inner: Option<RNode>,
}

/// JSON-quote a string the way Reflex's `LiteralVar.create(str)` renders it
/// (`ensure_ascii=False` style: only structural/control chars escaped).
fn json_quote(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// Port of `reflex.utils.format.to_camel_case` (hyphens treated as underscores).
fn to_camel_case(text: &str) -> String {
    let text = text.replace('-', "_");
    let words: Vec<&str> = text.split('_').collect();
    if words.len() == 1 {
        return words[0].to_string();
    }
    let mut out = String::from(words[0]);
    for w in &words[1..] {
        let mut chars = w.chars();
        if let Some(first) = chars.next() {
            out.extend(first.to_uppercase());
            // str.capitalize() lowercases the remainder.
            out.extend(chars.flat_map(|c| c.to_lowercase()));
        }
    }
    out
}

/// Port of `reflex.utils.format.format_ref`: `ref_` + non-word runs -> `_`.
fn format_ref(id: &str) -> String {
    let mut out = String::from("ref_");
    let mut prev_us = false;
    for c in id.chars() {
        if c.is_alphanumeric() || c == '_' {
            out.push(c);
            prev_us = false;
        } else if !prev_us {
            out.push('_');
            prev_us = true;
        }
    }
    out
}

/// Render a literal Python prop value to its JS expression, matching
/// `str(LiteralVar.create(value))` for the scalar surface this slice covers.
/// `bool` must be checked before `int` (bool subclasses int in Python).
fn literal_to_js(value: &Bound<'_, PyAny>) -> PyResult<String> {
    if value.is_none() {
        return Ok("null".to_string());
    }
    if let Ok(b) = value.downcast::<PyBool>() {
        return Ok(if b.is_true() { "true" } else { "false" }.to_string());
    }
    if let Ok(s) = value.downcast::<PyString>() {
        return Ok(json_quote(&s.extract::<String>()?));
    }
    if value.is_instance_of::<PyInt>() || value.is_instance_of::<PyFloat>() {
        // Defer to Python's str() so float formatting (e.g. 3.0 -> "3.0")
        // matches LiteralVar exactly.
        return Ok(value.str()?.extract::<String>()?);
    }
    Err(pyo3::exceptions::PyTypeError::new_err(format!(
        "reflex-compiler-core proving slice: unsupported literal prop type {}",
        value.get_type().name()?
    )))
}

/// Convert children (NodeHandles, text, or non-native components) into RChild.
/// A non-native child is rendered to its dict now (build-time Python) and kept
/// for native codegen; it counts against the fallback ledger and is refused in
/// strict mode.
fn build_children(children: &Bound<'_, PyList>) -> PyResult<Vec<RChild>> {
    let mut out: Vec<RChild> = Vec::with_capacity(children.len());
    for item in children.iter() {
        if let Ok(mut handle) = item.extract::<PyRefMut<NodeHandle>>() {
            if let Some(node) = handle.inner.take() {
                out.push(RChild::Node(node));
            }
            continue;
        }
        if let Ok(s) = item.downcast::<PyString>() {
            out.push(RChild::Node(RNode::Bare {
                contents: json_quote(&s.extract::<String>()?),
            }));
            continue;
        }
        PY_FALLBACKS.fetch_add(1, Ordering::Relaxed);
        if STRICT.load(Ordering::Relaxed) {
            return Err(PyRuntimeError::new_err(
                "strict purity mode: a non-native child subtree was encountered \
                 (component not built via the native registry)",
            ));
        }
        out.push(RChild::RawDict(item.call_method0("render")?.unbind()));
    }
    Ok(out)
}

/// Resolve the `id` -> `ref` prop (Element behavior) for a literal-string id.
fn ref_for(props: &Bound<'_, PyDict>) -> PyResult<Option<String>> {
    if let Some(v) = props.get_item("id")? {
        if let Ok(s) = v.downcast::<PyString>() {
            return Ok(Some(format_ref(&s.extract::<String>()?)));
        }
    }
    Ok(None)
}

/// Emit `key:value` prop fragments: camelCase each key, render each literal
/// value, add the `id`-derived `ref`, then sort by key — matching Reflex's
/// `format_props` (which sorts the camelCased keys). This single rule replaces
/// any per-component field-order table.
fn emit_props(props: &Bound<'_, PyDict>) -> PyResult<Vec<String>> {
    let mut pairs: Vec<(String, String)> = Vec::with_capacity(props.len() + 1);
    for (k, v) in props.iter() {
        let key_owned: String = k.extract()?;
        let norm = key_owned.strip_suffix('_').unwrap_or(&key_owned);
        pairs.push((to_camel_case(norm), literal_to_js(&v)?));
    }
    if let Some(r) = ref_for(props)? {
        pairs.push(("ref".to_string(), r));
    }
    pairs.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(pairs.into_iter().map(|(k, v)| format!("{k}:{v}")).collect())
}

/// Low-level node builder: emits props in the order passed (no registry). Used
/// by hand-written shims and as the primitive under the registry-driven `make`.
#[pyfunction]
fn make_node(
    tag: &str,
    is_element: bool,
    children: &Bound<'_, PyList>,
    props: &Bound<'_, PyDict>,
) -> PyResult<NodeHandle> {
    let name = if is_element {
        json_quote(tag)
    } else {
        tag.to_string()
    };
    Ok(NodeHandle {
        inner: Some(RNode::Element {
            name,
            props: emit_props(props)?,
            children: build_children(children)?,
        }),
    })
}

/// Register a component so `make` can build it natively (name -> tag + kind).
#[pyfunction]
fn register_component(name: &str, tag: &str, is_element: bool) {
    registry().write().unwrap().insert(
        name.to_string(),
        CompSpec {
            tag: tag.to_string(),
            is_element,
        },
    );
}

/// Registry-driven node builder: resolve the tag/kind from the registry, emit
/// sorted props, build children. One generic factory for every registered type.
#[pyfunction]
fn make(
    name: &str,
    children: &Bound<'_, PyList>,
    props: &Bound<'_, PyDict>,
) -> PyResult<NodeHandle> {
    let display_name = {
        let reg = registry().read().unwrap();
        let spec = reg
            .get(name)
            .ok_or_else(|| PyValueError::new_err(format!("component '{name}' is not registered")))?;
        if spec.is_element {
            json_quote(&spec.tag)
        } else {
            spec.tag.clone()
        }
    };
    Ok(NodeHandle {
        inner: Some(RNode::Element {
            name: display_name,
            props: emit_props(props)?,
            children: build_children(children)?,
        }),
    })
}

/// Lower a node to its JSX-call string, mirroring `_RenderUtils.render`. A
/// `RawDict` child is rendered by the native dict renderer (no Python executes;
/// reading the dict needs the GIL, so this is not GIL-pure — see the pure path).
fn render_rnode(py: Python<'_>, node: &RNode) -> PyResult<String> {
    match node {
        RNode::Bare { contents } => Ok(if contents.is_empty() {
            "null".to_string()
        } else {
            contents.clone()
        }),
        RNode::Element {
            name,
            props,
            children,
        } => {
            let mut rendered: Vec<String> = Vec::with_capacity(children.len());
            for c in children {
                let s = match c {
                    RChild::Node(n) => render_rnode(py, n)?,
                    RChild::RawDict(obj) => render_dict(py, obj.bind(py))?,
                };
                if !s.is_empty() {
                    rendered.push(s);
                }
            }
            Ok(format!(
                "jsx({},{{{}}},{})",
                name,
                props.join(","),
                rendered.join(",")
            ))
        }
    }
}

/// Render a node handle's subtree to its JSX-call string.
#[pyfunction]
fn render_to_js(py: Python<'_>, handle: &Bound<'_, NodeHandle>) -> PyResult<String> {
    let h = handle.borrow();
    match &h.inner {
        Some(node) => render_rnode(py, node),
        None => Ok(String::new()),
    }
}

/// Pure render: no `Python` token, so it physically cannot call back into
/// Python. A Python-component leaf is unrenderable here and returns an error.
fn render_rnode_pure(node: &RNode) -> Result<String, String> {
    match node {
        RNode::Bare { contents } => Ok(if contents.is_empty() {
            "null".to_string()
        } else {
            contents.clone()
        }),
        RNode::Element {
            name,
            props,
            children,
        } => {
            let mut rendered: Vec<String> = Vec::with_capacity(children.len());
            for c in children {
                let s = match c {
                    RChild::Node(n) => render_rnode_pure(n)?,
                    RChild::RawDict(_) => {
                        return Err(
                            "pure render hit a non-native subtree — its construction \
                             stayed in Python (codegen-native but not build-native)"
                                .to_string(),
                        )
                    }
                };
                if !s.is_empty() {
                    rendered.push(s);
                }
            }
            Ok(format!(
                "jsx({},{{{}}},{})",
                name,
                props.join(","),
                rendered.join(",")
            ))
        }
    }
}

/// Render a node handle with the GIL **released**. Because `allow_threads`
/// hands the closure no `Python` token (and rejects GIL-bound captures), this
/// code cannot touch Python: if it returns a string, zero Python executed —
/// the strongest proof the work was native. Errors if the tree needs Python.
#[pyfunction]
fn render_to_js_pure(py: Python<'_>, handle: &Bound<'_, NodeHandle>) -> PyResult<String> {
    let h = handle.borrow();
    let node = match &h.inner {
        Some(n) => n,
        None => return Ok(String::new()),
    };
    py.allow_threads(|| render_rnode_pure(node))
        .map_err(PyRuntimeError::new_err)
}

// --- Slice 0: render an existing Python render-dict to JS (no component port) ---
//
// Consumes the dict produced by `Component.render()` and emits the JS string,
// mirroring `_RenderUtils.render` for all five shapes. Works on ANY app's
// output (incl. cond/foreach/match/markdown-produced dicts) without porting
// components, so it can be diffed byte-for-byte against the Python compiler on
// every page of a real app. This is the codegen-correctness foundation; it
// reads Python data structures, so it is NOT GIL-pure (that is the make_node
// path's job).

fn dict_get<'py>(d: &Bound<'py, PyDict>, key: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
    d.get_item(key)
}

fn render_dict(py: Python<'_>, component: &Bound<'_, PyAny>) -> PyResult<String> {
    if let Ok(s) = component.downcast::<PyString>() {
        let v = s.extract::<String>()?;
        return Ok(if v.is_empty() { "null".to_string() } else { v });
    }
    let d = component.downcast::<PyDict>()?;
    if d.contains("iterable")? {
        return render_iterable(py, d);
    }
    if d.contains("match_cases")? {
        return render_match(py, d);
    }
    if d.contains("cond_state")? {
        return render_condition(py, d);
    }
    if let Some(contents) = dict_get(d, "contents")? {
        if !contents.is_none() {
            let v = contents.extract::<String>()?;
            return Ok(if v.is_empty() { "null".to_string() } else { v });
        }
    }
    render_tag(py, d)
}

fn render_tag(py: Python<'_>, d: &Bound<'_, PyDict>) -> PyResult<String> {
    // name = component.get("name") or "Fragment"
    let name = match dict_get(d, "name")? {
        Some(n) if n.is_truthy()? => n.extract::<String>()?,
        _ => "Fragment".to_string(),
    };
    let props: Vec<String> = match dict_get(d, "props")? {
        Some(p) => p.extract()?,
        None => Vec::new(),
    };
    let mut rendered: Vec<String> = Vec::new();
    if let Some(children) = dict_get(d, "children")? {
        for child in children.try_iter()? {
            let child = child?;
            if child.is_truthy()? {
                rendered.push(render_dict(py, &child)?);
            }
        }
    }
    Ok(format!(
        "jsx({},{{{}}},{})",
        name,
        props.join(","),
        rendered.join(",")
    ))
}

fn render_condition(py: Python<'_>, d: &Bound<'_, PyDict>) -> PyResult<String> {
    let cond: String = dict_get(d, "cond_state")?.unwrap().extract()?;
    let t = render_dict(py, &dict_get(d, "true_value")?.unwrap())?;
    let f = render_dict(py, &dict_get(d, "false_value")?.unwrap())?;
    Ok(format!("({cond}?({t}):({f}))"))
}

fn render_iterable(py: Python<'_>, d: &Bound<'_, PyDict>) -> PyResult<String> {
    let iterable: String = dict_get(d, "iterable_state")?.unwrap().extract()?;
    let arg_name: String = dict_get(d, "arg_name")?.unwrap().extract()?;
    let arg_index: String = dict_get(d, "arg_index")?.unwrap().extract()?;
    let mut children = String::new();
    if let Some(ch) = dict_get(d, "children")? {
        for child in ch.try_iter()? {
            children.push_str(&render_dict(py, &child?)?);
        }
    }
    Ok(format!(
        "Array.prototype.map.call({iterable} ?? [],(({arg_name},{arg_index})=>({children})))"
    ))
}

fn render_match(py: Python<'_>, d: &Bound<'_, PyDict>) -> PyResult<String> {
    let cond: String = dict_get(d, "cond")?.unwrap().extract()?;
    let mut cases_code = String::new();
    for case in dict_get(d, "match_cases")?.unwrap().try_iter()? {
        let case = case?;
        let conditions = case.get_item(0)?;
        let return_value = case.get_item(1)?;
        for condition in conditions.try_iter()? {
            let c: String = condition?.extract()?;
            cases_code.push_str(&format!("    case JSON.stringify({c}):\n"));
        }
        cases_code.push_str(&format!(
            "      return {};\n      break;\n",
            render_dict(py, &return_value)?
        ));
    }
    let default = render_dict(py, &dict_get(d, "default")?.unwrap())?;
    Ok(format!(
        "(() => {{\n  switch (JSON.stringify({cond})) {{\n{cases_code}    default:\n      return {default};\n      break;\n  }}\n}})()"
    ))
}

/// Render an existing Python render-dict (from `Component.render()`) to JS.
#[pyfunction]
fn render_dict_to_js(py: Python<'_>, component: &Bound<'_, PyAny>) -> PyResult<String> {
    render_dict(py, component)
}

/// Enable/disable strict purity mode (any Python fallback becomes an error).
#[pyfunction]
fn set_strict(value: bool) {
    STRICT.store(value, Ordering::Relaxed);
}

/// Number of Python-component fallbacks since the last reset.
#[pyfunction]
fn py_fallback_count() -> usize {
    PY_FALLBACKS.load(Ordering::Relaxed)
}

/// Reset the fallback ledger to zero.
#[pyfunction]
fn reset_fallback_count() {
    PY_FALLBACKS.store(0, Ordering::Relaxed);
}

#[pymodule]
fn reflex_compiler_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NodeHandle>()?;
    m.add_function(wrap_pyfunction!(make_node, m)?)?;
    m.add_function(wrap_pyfunction!(make, m)?)?;
    m.add_function(wrap_pyfunction!(register_component, m)?)?;
    m.add_function(wrap_pyfunction!(render_to_js, m)?)?;
    m.add_function(wrap_pyfunction!(render_dict_to_js, m)?)?;
    m.add_function(wrap_pyfunction!(render_to_js_pure, m)?)?;
    m.add_function(wrap_pyfunction!(set_strict, m)?)?;
    m.add_function(wrap_pyfunction!(py_fallback_count, m)?)?;
    m.add_function(wrap_pyfunction!(reset_fallback_count, m)?)?;
    Ok(())
}
