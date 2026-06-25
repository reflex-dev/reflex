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

use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyString};

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
fn render_py_leaf(py: Python<'_>, obj: &Py<PyAny>) -> PyResult<String> {
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

#[pymodule]
fn reflex_compiler_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NodeHandle>()?;
    m.add_function(wrap_pyfunction!(make_node, m)?)?;
    m.add_function(wrap_pyfunction!(render_to_js, m)?)?;
    Ok(())
}
