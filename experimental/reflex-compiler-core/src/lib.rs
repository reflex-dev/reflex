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

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyString};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

/// Strict purity mode. When on, any Python-component fallback is a hard error
/// instead of a silent delegation — so a "ported" component cannot quietly
/// regress to calling Python and still pass a string-equality test.
static STRICT: AtomicBool = AtomicBool::new(false);

/// Count of Python-component fallbacks since the last reset (the "cheat
/// ledger"). A genuinely-native render leaves this at 0.
static PY_FALLBACKS: AtomicUsize = AtomicUsize::new(0);

/// A child of a Rust node: either another Rust node (the fast path) or an
/// opaque Python component leaf (the fallback bridge).
enum RChild {
    Node(RNode),
    Py(Py<PyAny>),
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

/// Build a native node from raw props + children. This is the PyO3 seam that
/// replaces `Component.create` for fast-path components.
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

    let mut prop_strs: Vec<String> = Vec::with_capacity(props.len());
    let mut ref_prop: Option<String> = None;

    for (k, v) in props.iter() {
        let key_owned: String = k.extract()?;
        let key = key_owned.strip_suffix('_').unwrap_or(&key_owned);
        // A literal string `id` adds a `ref:ref_<id>` prop (Element behavior).
        if key == "id" {
            if let Ok(s) = v.downcast::<PyString>() {
                ref_prop = Some(format_ref(&s.extract::<String>()?));
            }
        }
        prop_strs.push(format!("{}:{}", to_camel_case(key), literal_to_js(&v)?));
    }
    if let Some(r) = ref_prop {
        prop_strs.push(format!("ref:{r}"));
    }

    let mut child_nodes: Vec<RChild> = Vec::with_capacity(children.len());
    for item in children.iter() {
        // Fast-path child: another NodeHandle — move its subtree into us.
        if let Ok(mut handle) = item.extract::<PyRefMut<NodeHandle>>() {
            if let Some(node) = handle.inner.take() {
                child_nodes.push(RChild::Node(node));
            }
            continue;
        }
        // Literal text child -> bare node.
        if let Ok(s) = item.downcast::<PyString>() {
            child_nodes.push(RChild::Node(RNode::Bare {
                contents: json_quote(&s.extract::<String>()?),
            }));
            continue;
        }
        // Anything else is a real Python component: keep as an opaque leaf and
        // render it via callback at codegen time (the fallback bridge).
        child_nodes.push(RChild::Py(item.unbind()));
    }

    Ok(NodeHandle {
        inner: Some(RNode::Element {
            name,
            props: prop_strs,
            children: child_nodes,
        }),
    })
}

/// Render a Python-component leaf by calling back into Reflex's `_RenderUtils`.
/// Every call is recorded in the fallback ledger; in strict mode it is refused.
fn render_py_leaf(py: Python<'_>, obj: &Py<PyAny>) -> PyResult<String> {
    PY_FALLBACKS.fetch_add(1, Ordering::Relaxed);
    if STRICT.load(Ordering::Relaxed) {
        return Err(PyRuntimeError::new_err(
            "strict purity mode: render hit a Python-component fallback — this \
             node was NOT rendered natively in Rust",
        ));
    }
    let templates = py.import("reflex_base.compiler.templates")?;
    let render_utils = templates.getattr("_RenderUtils")?;
    let render_dict = obj.call_method0(py, "render")?;
    let js = render_utils.call_method1("render", (render_dict,))?;
    js.extract()
}

/// Lower a node to its JSX-call string, mirroring `_RenderUtils.render`.
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
                    RChild::Py(obj) => render_py_leaf(py, obj)?,
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
                    RChild::Py(_) => {
                        return Err(
                            "pure render hit a Python-component leaf — the work was \
                             NOT done natively in Rust (a fallback would be required)"
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
    m.add_function(wrap_pyfunction!(render_to_js, m)?)?;
    m.add_function(wrap_pyfunction!(render_dict_to_js, m)?)?;
    m.add_function(wrap_pyfunction!(render_to_js_pure, m)?)?;
    m.add_function(wrap_pyfunction!(set_strict, m)?)?;
    m.add_function(wrap_pyfunction!(py_fallback_count, m)?)?;
    m.add_function(wrap_pyfunction!(reset_fallback_count, m)?)?;
    Ok(())
}
