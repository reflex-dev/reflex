//! PyO3 walk over a Reflex `Component` PyObject → `reflex_ir::Page<'arena>`.
//!
//! Mirrors `reflex/compiler/ir/bridge.py` one-for-one. Every supported
//! Component subclass dispatches on `type(component).__name__`; props,
//! events, and child references go through PyO3 `getattr` calls.
//!
//! Coverage matches the bridge's: Bare, Fragment, Cond, Foreach, Match,
//! and generic Element. CustomComponent and memo-wrapper subclasses fall
//! through to the generic Element path the same way the bridge does.
//!
//! Var values produce `Value::JsExpr { expr, var_data }` — the same shape
//! the msgpack parser builds — so downstream codegen needs no changes.

use std::cell::RefCell;
use std::collections::HashSet;

use pyo3::prelude::*;
use pyo3::types::{
    PyAnyMethods, PyBool, PyDict, PyFloat, PyInt, PyList, PyMapping, PyString, PyStringMethods,
    PyTuple, PyTypeMethods,
};

use reflex_arena::Arena;
use reflex_intern::{intern, Symbol};
use reflex_ir::{
    Component, EventHandler, Hook, Literal, MatchArm, Meta, NodeId, Page, PyFileId, SourceLoc,
    Value, VarData,
};

use super::text::decode_js_string_literal;
use super::timing::{self, Counter as TC, Field as TF, Span as TSpan};

/// Wire schema version this reader emits. Matches `reflex_ir::parse`'s
/// `SCHEMA_VERSION`. The reader doesn't go through msgpack, but downstream
/// codegen branches on `Page.schema_version`.
const SCHEMA_VERSION: u32 = 2;

/// Errors raised by the PyO3 component reader.
///
/// Surfaced as Python `ValueError`s via `CompilerSession`. They carry
/// enough context to map back to the originating Component without a
/// stack trace.
#[derive(Debug, thiserror::Error)]
pub enum PyReadError {
    #[error("pyo3 attribute error on `{attr}`: {source}")]
    Attr {
        attr: &'static str,
        #[source]
        source: PyErr,
    },
    #[error("pyread does not yet support Component subclass `{class}`")]
    Unsupported { class: String },
    #[error("pyread type error on `{attr}`: expected {expected}, got {got}")]
    TypeMismatch {
        attr: &'static str,
        expected: &'static str,
        got: String,
    },
}

impl From<PyReadError> for PyErr {
    fn from(e: PyReadError) -> Self {
        pyo3::exceptions::PyValueError::new_err(e.to_string())
    }
}

/// Cached PyObject handles the reader needs on the hot path.
///
/// Resolved once per `read_page` call instead of per node — the
/// `import_bound` lookup is ~10 µs but `is_instance` against a cached
/// class is ~100 ns. With ~165 nodes/page and ~5 isinstance checks each,
/// caching saves ~8 ms.
pub struct PyRefs<'py> {
    pub var_cls: Bound<'py, PyAny>,
    pub literal_var_cls: Bound<'py, PyAny>,
    /// `reflex_base.utils.format.format_library_name` for normalizing
    /// `Component.library` and `VarData.imports` module specifiers.
    pub format_library_name: Bound<'py, PyAny>,
    /// Page-level harvests accumulated inline during `read_page` so we
    /// don't have to re-walk the Python tree three more times for
    /// `component_imports` / `state_bindings` / `needs_ref`. Interior
    /// mutability keeps the read helpers' `&PyRefs` signatures intact;
    /// every borrow is scoped to a single registration to avoid
    /// runtime aliasing panics.
    pub harvest: RefCell<HarvestState>,
}

/// Page-level data the bridge collects during `read_page`. Equivalent to
/// what `collect_component_imports` / `collect_state_bindings` /
/// `scan_needs_ref` used to compute in three separate walks; now
/// accumulated in one pass by the read helpers as they visit each
/// node.
#[derive(Default)]
pub struct HarvestState {
    component_imports: Vec<(Symbol, Symbol)>,
    component_imports_seen: HashSet<(Symbol, Symbol)>,
    state_bindings: Vec<Symbol>,
    state_bindings_seen: HashSet<String>,
    needs_ref: bool,
}

impl HarvestState {
    pub fn add_component_import(&mut self, pair: (Symbol, Symbol)) {
        if self.component_imports_seen.insert(pair) {
            self.component_imports.push(pair);
        }
    }

    pub fn add_state_idents_in(&mut self, expr: &str) {
        for ident in find_state_idents(expr) {
            if self.state_bindings_seen.insert(ident.clone()) {
                self.state_bindings.push(intern(&ident));
            }
        }
    }

    pub fn mark_needs_ref(&mut self) {
        self.needs_ref = true;
    }
}

impl<'py> PyRefs<'py> {
    pub fn new(py: Python<'py>) -> Result<Self, PyReadError> {
        let vars_mod = py
            .import_bound("reflex_base.vars.base")
            .map_err(|source| PyReadError::Attr {
                attr: "import reflex_base.vars.base",
                source,
            })?;
        let var_cls = vars_mod.getattr("Var").map_err(|source| PyReadError::Attr {
            attr: "reflex_base.vars.base.Var",
            source,
        })?;
        let literal_var_cls = vars_mod
            .getattr("LiteralVar")
            .map_err(|source| PyReadError::Attr {
                attr: "reflex_base.vars.base.LiteralVar",
                source,
            })?;
        let format_library_name = py
            .import_bound("reflex_base.utils.format")
            .and_then(|m| m.getattr("format_library_name"))
            .map_err(|source| PyReadError::Attr {
                attr: "reflex_base.utils.format.format_library_name",
                source,
            })?;
        Ok(Self {
            var_cls,
            literal_var_cls,
            format_library_name,
            harvest: RefCell::new(HarvestState::default()),
        })
    }
}

// ---- Top-level Page entry ---------------------------------------------------

/// Read a page's root Component into a `reflex_ir::Page<'arena>`.
///
/// Mirrors `reflex.compiler.ir.bridge.page_to_ir`.
pub fn read_page<'arena, 'py>(
    py: Python<'py>,
    root: &Bound<'py, PyAny>,
    route: &str,
    title: Option<&str>,
    meta_tags: &[(String, String)],
    arena: &'arena Arena,
    refs: &PyRefs<'py>,
) -> Result<Page<'arena>, PyReadError> {
    timing::reset();
    let _total = TSpan::new(TF::ReadPageTotal);

    // Reset the harvest accumulator so multiple `read_page` calls
    // sharing a `PyRefs` don't leak prior state into this page.
    *refs.harvest.borrow_mut() = HarvestState::default();

    let root_ir = read_component(py, root, arena, refs)?;
    let root_alloc: &Component<'arena> = arena.alloc(root_ir);

    let meta_arr: Vec<Meta<'arena>> = meta_tags
        .iter()
        .map(|(name, content)| Meta {
            name: intern(name),
            content: arena.alloc_str(content),
        })
        .collect();
    let meta_slice = arena.alloc_slice_fill_iter(meta_arr.into_iter());

    let route_str: &str = arena.alloc_str(route);
    let title_str: Option<&str> = title.map(|s| &*arena.alloc_str(s));

    // Drain the harvests collected during the single walk above.
    let harvest = refs.harvest.borrow();
    let component_imports = arena
        .alloc_slice_fill_iter(harvest.component_imports.iter().copied());
    let state_bindings = arena
        .alloc_slice_fill_iter(harvest.state_bindings.iter().copied());
    let needs_ref = harvest.needs_ref;
    drop(harvest);

    Ok(Page {
        schema_version: SCHEMA_VERSION,
        route: route_str,
        root: root_alloc,
        title: title_str,
        meta: meta_slice,
        source_files: arena.alloc_slice_fill_iter(std::iter::empty::<PyFileId>()),
        component_imports,
        state_bindings,
        needs_ref,
    })
}

// ---- Component dispatch -----------------------------------------------------

fn read_component<'arena, 'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'py>,
) -> Result<Component<'arena>, PyReadError> {
    timing::incr(TC::Node);
    let cls_name = {
        let _s = TSpan::new(TF::ClassName);
        class_name(component)?
    };
    match cls_name.as_str() {
        "Bare" => read_bare(py, component, arena, refs),
        "Fragment" => read_fragment(py, component, arena, refs),
        "Cond" => read_cond(py, component, arena, refs),
        "Foreach" => read_foreach(py, component, arena, refs),
        "Match" => read_match(py, component, arena, refs),
        _ => read_element(py, component, arena, refs),
    }
}

fn read_bare<'arena, 'py>(
    _py: Python<'py>,
    component: &Bound<'py, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'py>,
) -> Result<Component<'arena>, PyReadError> {
    let contents = getattr(component, "contents")?;
    if contents.is_none() {
        return Ok(Component::Text {
            value: arena.alloc_str(""),
            id: NodeId::default(),
            source_loc: SourceLoc::SYNTHETIC,
        });
    }
    let is_var = isinstance(&contents, &refs.var_cls, "Bare.contents")?;
    if is_var {
        let js_expr = read_attr_str(&contents, "_js_expr", "Var._js_expr")?;
        if let Some(decoded) = decode_js_string_literal(&js_expr) {
            return Ok(Component::Text {
                value: arena.alloc_str(&decoded),
                id: NodeId::default(),
                source_loc: SourceLoc::SYNTHETIC,
            });
        }
        // Var-as-expression: emit `Component::Expr` with the JS expression
        // and its merged VarData. Codegen renders this inline.
        refs.harvest.borrow_mut().add_state_idents_in(&js_expr);
        let var_data = read_var_data(&contents, arena, refs)?;
        let value = Value::JsExpr {
            expr: arena.alloc_str(&js_expr),
            var_data,
        };
        return Ok(Component::Expr {
            value,
            id: NodeId::default(),
            source_loc: SourceLoc::SYNTHETIC,
        });
    }
    // Non-Var contents: stringify via Python's `str(...)`.
    let text = py_str(&contents)?;
    Ok(Component::Text {
        value: arena.alloc_str(&text),
        id: NodeId::default(),
        source_loc: SourceLoc::SYNTHETIC,
    })
}

fn read_fragment<'arena, 'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'py>,
) -> Result<Component<'arena>, PyReadError> {
    let children = read_children(py, component, arena, refs)?;
    Ok(Component::Fragment {
        children,
        id: NodeId::default(),
        source_loc: SourceLoc::SYNTHETIC,
    })
}

fn read_cond<'arena, 'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'py>,
) -> Result<Component<'arena>, PyReadError> {
    let cond_obj = getattr(component, "cond")?;
    let test = read_value(py, &cond_obj, arena, refs)?;

    let children_obj = getattr(component, "children")?;
    let children: Bound<'_, PyList> = children_obj.downcast_into().map_err(|e| {
        PyReadError::TypeMismatch {
            attr: "Cond.children",
            expected: "list",
            got: e.to_string(),
        }
    })?;
    let mut iter = children.iter();
    let then_obj = iter.next();
    let else_obj = iter.next();

    let then_ir = match then_obj {
        Some(t) => read_component(py, &t, arena, refs)?,
        None => Component::Text {
            value: arena.alloc_str(""),
            id: NodeId::default(),
            source_loc: SourceLoc::SYNTHETIC,
        },
    };
    let then_alloc: &Component<'arena> = arena.alloc(then_ir);

    let else_alloc: Option<&Component<'arena>> = match else_obj {
        Some(e) => {
            let ir = read_component(py, &e, arena, refs)?;
            Some(arena.alloc(ir))
        }
        None => None,
    };

    Ok(Component::Cond {
        test,
        then: then_alloc,
        else_: else_alloc,
        id: NodeId::default(),
        source_loc: SourceLoc::SYNTHETIC,
    })
}

fn read_foreach<'arena, 'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'py>,
) -> Result<Component<'arena>, PyReadError> {
    // Delegate to `_render()` so the iter-var arg is properly typed —
    // matches the bridge.py rationale (foreach bodies do `item["key"]`
    // etc. and need `ArrayCastedVar`/`ObjectVar`-shaped args).
    let iter_tag = component
        .call_method0("_render")
        .map_err(|source| PyReadError::Attr {
            attr: "Foreach._render()",
            source,
        })?;
    let body_component =
        iter_tag
            .call_method0("render_component")
            .map_err(|source| PyReadError::Attr {
                attr: "IterTag.render_component()",
                source,
            })?;
    let body_ir = read_component(py, &body_component, arena, refs)?;
    let body_alloc: &Component<'arena> = arena.alloc(body_ir);

    let iterable = getattr(component, "iterable")?;
    let iter_val = read_value(py, &iterable, arena, refs)?;
    Ok(Component::Foreach {
        iter: iter_val,
        body: body_alloc,
        id: NodeId::default(),
        source_loc: SourceLoc::SYNTHETIC,
    })
}

fn read_match<'arena, 'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'py>,
) -> Result<Component<'arena>, PyReadError> {
    let cond_obj = getattr(component, "cond")?;
    let test = read_value(py, &cond_obj, arena, refs)?;

    let match_cases_obj = match component.getattr("match_cases") {
        Ok(v) if !v.is_none() => v,
        _ => {
            // No cases — emit an empty Match with no default.
            return Ok(Component::Match {
                value: test,
                arms: arena.alloc_slice_fill_iter(std::iter::empty::<MatchArm<'arena>>()),
                default: None,
                id: NodeId::default(),
                source_loc: SourceLoc::SYNTHETIC,
            });
        }
    };
    let match_cases: Bound<'_, PyList> =
        match_cases_obj
            .downcast_into()
            .map_err(|e| PyReadError::TypeMismatch {
                attr: "Match.match_cases",
                expected: "list",
                got: e.to_string(),
            })?;

    // Match case entries can arrive as either a list or a tuple
    // (`[case_a, case_b, ..., body_component]`); use the generic
    // sequence protocol so both work without a downcast dance.
    let mut arms_vec: Vec<MatchArm<'arena>> = Vec::with_capacity(match_cases.len());
    for case_entry in match_cases.iter() {
        let entries: Vec<Bound<'_, PyAny>> = case_entry
            .iter()
            .map_err(|source| PyReadError::Attr {
                attr: "iter(Match case entry)",
                source,
            })?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|source| PyReadError::Attr {
                attr: "Match case entry[i]",
                source,
            })?;
        if entries.len() < 2 {
            continue;
        }
        let body_obj = &entries[entries.len() - 1];
        let body_ir = read_component(py, body_obj, arena, refs)?;
        let body_alloc: &Component<'arena> = arena.alloc(body_ir);
        for case_val_obj in &entries[..entries.len() - 1] {
            let case = read_value(py, case_val_obj, arena, refs)?;
            arms_vec.push(MatchArm {
                case,
                body: body_alloc,
            });
        }
    }

    let default_obj = component
        .getattr("default")
        .ok()
        .filter(|v| !v.is_none());
    let default: Option<&Component<'arena>> = match default_obj {
        Some(d) => {
            let ir = read_component(py, &d, arena, refs)?;
            Some(arena.alloc(ir))
        }
        None => None,
    };

    Ok(Component::Match {
        value: test,
        arms: arena.alloc_slice_fill_iter(arms_vec.into_iter()),
        default,
        id: NodeId::default(),
        source_loc: SourceLoc::SYNTHETIC,
    })
}

fn read_element<'arena, 'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'py>,
) -> Result<Component<'arena>, PyReadError> {
    timing::incr(TC::Element);
    let tag_sym = {
        let _s = TSpan::new(TF::ResolveTag);
        resolve_tag_symbol(component)?
    };

    // Harvest the component's module/spec for the page-level
    // `import {...} from "<module>";` lines. Inlined from
    // `collect_component_imports` so the bridge doesn't have to walk the
    // tree a second time after IR construction.
    {
        let _s = TSpan::new(TF::ImportAlias);
        if let Some(pair) = import_alias_for(component, refs)? {
            let _h = TSpan::new(TF::HarvestRegister);
            refs.harvest.borrow_mut().add_component_import(pair);
        }
    }

    // Harvest `needs_ref` while we're already at this node — anything
    // with a non-None `id` triggers the `const ref_root = useRef(null)`
    // line in the emitted page module.
    {
        let _s = TSpan::new(TF::NeedsRef);
        if !refs.harvest.borrow().needs_ref {
            if let Ok(v) = component.getattr("id") {
                if !v.is_none() {
                    refs.harvest.borrow_mut().mark_needs_ref();
                }
            }
        }
    }

    // No tag → emit as Fragment around children (matches bridge.py).
    if tag_sym == Symbol::EMPTY {
        let children = read_children(py, component, arena, refs)?;
        return Ok(Component::Fragment {
            children,
            id: NodeId::default(),
            source_loc: SourceLoc::SYNTHETIC,
        });
    }

    // No spans around read_props / read_children / read_event_handlers —
    // they recurse (props value → nested vars/components, children →
    // read_component, event_handlers → event_handler_to_js → read_var_data)
    // so wrapping them would double-count nested work in their own
    // accumulators. The leaf spans inside (`ReadVarData`, `ResolveTag`,
    // `ImportAlias`, etc.) report self-time accurately; everything not
    // covered shows up in the `(unaccounted)` line of the reporter.
    let props = read_props(py, component, arena, refs)?;
    let children = read_children(py, component, arena, refs)?;
    let events = read_event_handlers(py, component, arena, refs)?;
    let hooks: &[Hook<'arena>] =
        arena.alloc_slice_fill_iter(std::iter::empty::<Hook<'arena>>());
    Ok(Component::Element {
        tag: tag_sym,
        props,
        children,
        event_handlers: events,
        hooks,
        id: NodeId::default(),
        source_loc: SourceLoc::SYNTHETIC,
    })
}

// ---- Props, children, events ------------------------------------------------

fn read_children<'arena, 'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'py>,
) -> Result<&'arena [Component<'arena>], PyReadError> {
    let (children_obj, iter) = {
        let _s = TSpan::new(TF::ChildrenAttr);
        let children_obj = match component.getattr("children") {
            Ok(v) if !v.is_none() => v,
            _ => return Ok(arena.alloc_slice_fill_iter(std::iter::empty::<Component<'arena>>())),
        };
        let iter = children_obj.iter().map_err(|source| PyReadError::Attr {
            attr: "iter(component.children)",
            source,
        })?;
        (children_obj, iter)
    };
    let _ = children_obj;
    let mut out: Vec<Component<'arena>> = Vec::new();
    for item in iter {
        let child = item.map_err(|source| PyReadError::Attr {
            attr: "component.children[i]",
            source,
        })?;
        out.push(read_component(py, &child, arena, refs)?);
    }
    Ok(arena.alloc_slice_fill_iter(out.into_iter()))
}

fn read_props<'arena, 'py>(
    py: Python<'py>,
    component: &Bound<'py, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'py>,
) -> Result<&'arena [(Symbol, Value<'arena>)], PyReadError> {
    let mut props: Vec<(Symbol, Value<'arena>)> = Vec::new();

    // Component fields (the dataclass props), in Component.get_props() order.
    let prop_names_obj = {
        let _s = TSpan::new(TF::GetPropsCall);
        component
            .call_method0("get_props")
            .map_err(|source| PyReadError::Attr {
                attr: "Component.get_props()",
                source,
            })?
    };
    let prop_names_iter = prop_names_obj.iter().map_err(|source| PyReadError::Attr {
        attr: "iter(get_props())",
        source,
    })?;
    for name_res in prop_names_iter {
        timing::incr(TC::Prop);
        let name_obj = name_res.map_err(|source| PyReadError::Attr {
            attr: "get_props()[i]",
            source,
        })?;
        let raw: String = py_str(&name_obj)?;
        let attr_name = raw.strip_suffix('_').unwrap_or(&raw).to_owned();
        let value_obj = {
            let _s = TSpan::new(TF::PropValueGetattr);
            match component.getattr(raw.as_str()) {
                Ok(v) => v,
                Err(_) => continue,
            }
        };
        if value_obj.is_none() {
            continue;
        }
        let value = read_value(py, &value_obj, arena, refs)?;
        props.push((intern(&attr_name), value));
    }

    // Identity props the legacy renderer always splices.
    for name in ["key", "id", "class_name"] {
        let v = {
            let _s = TSpan::new(TF::PropValueGetattr);
            match component.getattr(name) {
                Ok(v) if !v.is_none() => v,
                _ => continue,
            }
        };
        let value = read_value(py, &v, arena, refs)?;
        props.push((intern(name), value));
    }

    // custom_attrs: any extra string-keyed attributes.
    if let Ok(custom) = component.getattr("custom_attrs") {
        if !custom.is_none() {
            if let Ok(mapping) = custom.downcast::<PyMapping>() {
                let keys = mapping
                    .keys()
                    .map_err(|source| PyReadError::Attr {
                        attr: "custom_attrs.keys()",
                        source,
                    })?;
                for key_res in keys.iter().map_err(|source| PyReadError::Attr {
                    attr: "iter(custom_attrs.keys())",
                    source,
                })? {
                    let key = key_res.map_err(|source| PyReadError::Attr {
                        attr: "custom_attrs.keys()[i]",
                        source,
                    })?;
                    let name: String = py_str(&key)?;
                    let val =
                        mapping
                            .get_item(&key)
                            .map_err(|source| PyReadError::Attr {
                                attr: "custom_attrs[k]",
                                source,
                            })?;
                    let value = read_value(py, &val, arena, refs)?;
                    props.push((intern(&name), value));
                }
            }
        }
    }

    Ok(arena.alloc_slice_fill_iter(props.into_iter()))
}

fn read_event_handlers<'arena, 'py>(
    _py: Python<'py>,
    component: &Bound<'py, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'py>,
) -> Result<&'arena [EventHandler<'arena>], PyReadError> {
    let triggers = {
        let _s = TSpan::new(TF::EventTriggersAttr);
        let triggers_obj = match component.getattr("event_triggers") {
            Ok(v) if !v.is_none() => v,
            _ => return Ok(arena.alloc_slice_fill_iter(std::iter::empty::<EventHandler<'arena>>())),
        };
        let triggers: Bound<'_, PyDict> = triggers_obj
            .downcast_into()
            .map_err(|e| PyReadError::TypeMismatch {
                attr: "Component.event_triggers",
                expected: "dict",
                got: e.to_string(),
            })?;
        triggers
    };

    let mut out: Vec<EventHandler<'arena>> = Vec::with_capacity(triggers.len());
    for (trigger_obj, handler_obj) in triggers.iter() {
        timing::incr(TC::EventHandler);
        let trigger_name: String = py_str(&trigger_obj)?;
        if trigger_name == "on_mount" || trigger_name == "on_unmount" {
            // Side-effect triggers handled outside JSX — match bridge.py.
            continue;
        }
        let (expr, var_data) =
            event_handler_to_js(&handler_obj, arena, refs)?;
        out.push(EventHandler {
            trigger: intern(&trigger_name),
            expr: arena.alloc_str(&expr),
            var_data,
        });
    }
    Ok(arena.alloc_slice_fill_iter(out.into_iter()))
}

fn event_handler_to_js<'arena>(
    handler: &Bound<'_, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'_>,
) -> Result<(String, VarData<'arena>), PyReadError> {
    if isinstance(handler, &refs.var_cls, "event handler")? {
        let expr = read_attr_str(handler, "_js_expr", "Var._js_expr")?;
        refs.harvest.borrow_mut().add_state_idents_in(&expr);
        let var_data = read_var_data(handler, arena, refs)?;
        return Ok((expr, var_data));
    }
    // Wrap via `LiteralVar.create(handler)` so EventChain / EventSpec /
    // dict / list values get a proper JS expression + VarData.
    let wrapped = refs
        .literal_var_cls
        .call_method1("create", (handler,))
        .map_err(|source| PyReadError::Attr {
            attr: "LiteralVar.create(event handler)",
            source,
        })?;
    if isinstance(&wrapped, &refs.var_cls, "LiteralVar.create result")? {
        let expr = read_attr_str(&wrapped, "_js_expr", "Var._js_expr")?;
        refs.harvest.borrow_mut().add_state_idents_in(&expr);
        let var_data = read_var_data(&wrapped, arena, refs)?;
        Ok((expr, var_data))
    } else {
        Ok((py_str(&wrapped)?, VarData::EMPTY))
    }
}

// ---- Value (Var vs literal) -------------------------------------------------

fn read_value<'arena, 'py>(
    _py: Python<'py>,
    value: &Bound<'py, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'py>,
) -> Result<Value<'arena>, PyReadError> {
    let is_var = {
        let _s = TSpan::new(TF::IsInstanceVar);
        isinstance(value, &refs.var_cls, "prop value")?
    };
    if is_var {
        timing::incr(TC::Var);
        let expr = {
            let _s = TSpan::new(TF::VarJsExprAttr);
            read_attr_str(value, "_js_expr", "Var._js_expr")?
        };
        refs.harvest.borrow_mut().add_state_idents_in(&expr);
        let var_data = read_var_data(value, arena, refs)?;
        return Ok(Value::JsExpr {
            expr: arena.alloc_str(&expr),
            var_data,
        });
    }
    let _s_lit = TSpan::new(TF::ValueLiteralDispatch);
    if value.is_none() {
        return Ok(Value::Literal(Literal::Null));
    }
    if let Ok(b) = value.downcast::<PyBool>() {
        return Ok(Value::Literal(Literal::Bool(b.is_true())));
    }
    if let Ok(i) = value.downcast::<PyInt>() {
        let n: i64 = i.extract().map_err(|source| PyReadError::Attr {
            attr: "int.extract()",
            source,
        })?;
        return Ok(Value::Literal(Literal::Int(n)));
    }
    if let Ok(f) = value.downcast::<PyFloat>() {
        let v: f64 = f.extract().map_err(|source| PyReadError::Attr {
            attr: "float.extract()",
            source,
        })?;
        return Ok(Value::Literal(Literal::Float(v)));
    }
    if let Ok(s) = value.downcast::<PyString>() {
        let raw = s.to_str().map_err(|source| PyReadError::Attr {
            attr: "PyString::to_str",
            source,
        })?;
        return Ok(Value::Literal(Literal::Str(arena.alloc_str(raw))));
    }
    // Complex Python values (EventChain, lists, dicts, …): wrap via
    // `LiteralVar.create` and read as a Var. Matches bridge.var_to_value.
    let wrapped = refs
        .literal_var_cls
        .call_method1("create", (value,))
        .map_err(|source| PyReadError::Attr {
            attr: "LiteralVar.create(prop value)",
            source,
        })?;
    if isinstance(&wrapped, &refs.var_cls, "LiteralVar.create result")? {
        let expr = read_attr_str(&wrapped, "_js_expr", "Var._js_expr")?;
        let var_data = read_var_data(&wrapped, arena, refs)?;
        return Ok(Value::JsExpr {
            expr: arena.alloc_str(&expr),
            var_data,
        });
    }
    // Last-ditch: stringify.
    Ok(Value::JsExpr {
        expr: arena.alloc_str(&py_str(&wrapped)?),
        var_data: VarData::EMPTY,
    })
}

// ---- VarData ----------------------------------------------------------------

fn read_var_data<'arena>(
    var: &Bound<'_, PyAny>,
    arena: &'arena Arena,
    refs: &PyRefs<'_>,
) -> Result<VarData<'arena>, PyReadError> {
    let _s = TSpan::new(TF::ReadVarData);
    let vd_obj = match var.call_method0("_get_all_var_data") {
        Ok(v) if !v.is_none() => v,
        _ => match var.getattr("_var_data") {
            Ok(v) if !v.is_none() => v,
            _ => return Ok(VarData::EMPTY),
        },
    };

    // hooks: list[str]
    let hooks: &'arena [&'arena str] = match vd_obj.getattr("hooks") {
        Ok(v) if !v.is_none() => {
            let mut out: Vec<&'arena str> = Vec::new();
            for item in v.iter().map_err(|source| PyReadError::Attr {
                attr: "iter(VarData.hooks)",
                source,
            })? {
                let s = item.map_err(|source| PyReadError::Attr {
                    attr: "VarData.hooks[i]",
                    source,
                })?;
                let raw = py_str(&s)?;
                out.push(arena.alloc_str(&raw));
            }
            arena.alloc_slice_fill_iter(out.into_iter())
        }
        _ => arena.alloc_slice_fill_iter(std::iter::empty::<&str>()),
    };

    // imports: ParsedImportTuple or dict[str, list[ImportVar]]
    let imports = read_var_data_imports(&vd_obj, refs)?;
    let imports_slice = arena.alloc_slice_fill_iter(imports.into_iter());

    // state: Optional[str]
    let state = match vd_obj.getattr("state") {
        Ok(v) if !v.is_none() => Some(intern(&py_str(&v)?)),
        _ => None,
    };

    // deps: list[Var | str]
    let deps: &'arena [Symbol] = match vd_obj.getattr("deps") {
        Ok(v) if !v.is_none() => {
            let mut out: Vec<Symbol> = Vec::new();
            for item in v.iter().map_err(|source| PyReadError::Attr {
                attr: "iter(VarData.deps)",
                source,
            })? {
                let d = item.map_err(|source| PyReadError::Attr {
                    attr: "VarData.deps[i]",
                    source,
                })?;
                out.push(intern(&py_str(&d)?));
            }
            arena.alloc_slice_fill_iter(out.into_iter())
        }
        _ => arena.alloc_slice_fill_iter(std::iter::empty::<Symbol>()),
    };

    // position: Optional[int | enum-with-value]
    let position = match vd_obj.getattr("position") {
        Ok(v) if !v.is_none() => {
            let p = if let Ok(pi) = v.extract::<u8>() {
                Some(pi)
            } else if let Ok(value_attr) = v.getattr("value") {
                value_attr.extract::<u8>().ok()
            } else {
                None
            };
            p
        }
        _ => None,
    };

    // components: list[str]
    let components: &'arena [Symbol] = match vd_obj.getattr("components") {
        Ok(v) if !v.is_none() => {
            let mut out: Vec<Symbol> = Vec::new();
            for item in v.iter().map_err(|source| PyReadError::Attr {
                attr: "iter(VarData.components)",
                source,
            })? {
                let c = item.map_err(|source| PyReadError::Attr {
                    attr: "VarData.components[i]",
                    source,
                })?;
                out.push(intern(&py_str(&c)?));
            }
            arena.alloc_slice_fill_iter(out.into_iter())
        }
        _ => arena.alloc_slice_fill_iter(std::iter::empty::<Symbol>()),
    };

    Ok(VarData {
        hooks,
        imports: imports_slice,
        state,
        deps,
        position,
        components,
    })
}

fn read_var_data_imports(
    vd: &Bound<'_, PyAny>,
    refs: &PyRefs<'_>,
) -> Result<Vec<(Symbol, Symbol)>, PyReadError> {
    let raw = match vd.getattr("imports") {
        Ok(v) if !v.is_none() => v,
        _ => return Ok(Vec::new()),
    };
    // `ParsedImportTuple = tuple[tuple[str, tuple[ImportVar, ...]], ...]`,
    // or `dict[str, list[ImportVar]]`. Iterate either as (module, entries).
    let mut iter_pairs: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>)> = Vec::new();
    if let Ok(d) = raw.downcast::<PyDict>() {
        for (k, v) in d.iter() {
            iter_pairs.push((k, v));
        }
    } else {
        for pair in raw.iter().map_err(|source| PyReadError::Attr {
            attr: "iter(VarData.imports)",
            source,
        })? {
            let p = pair.map_err(|source| PyReadError::Attr {
                attr: "VarData.imports[i]",
                source,
            })?;
            let t: Bound<'_, PyTuple> = p
                .downcast_into()
                .map_err(|e| PyReadError::TypeMismatch {
                    attr: "VarData.imports[i]",
                    expected: "tuple",
                    got: e.to_string(),
                })?;
            if t.len() != 2 {
                continue;
            }
            iter_pairs.push((
                t.get_item(0).map_err(|source| PyReadError::Attr {
                    attr: "VarData.imports[i][0]",
                    source,
                })?,
                t.get_item(1).map_err(|source| PyReadError::Attr {
                    attr: "VarData.imports[i][1]",
                    source,
                })?,
            ));
        }
    }

    let mut out: Vec<(Symbol, Symbol)> = Vec::new();
    for (module_obj, entries) in iter_pairs {
        let module_raw = py_str(&module_obj)?;
        let module = format_library_name(refs, &module_raw)?;
        if module.is_empty() {
            // Side-effect import; bridge.py skips these for the in-braces list.
            continue;
        }
        for entry in entries.iter().map_err(|source| PyReadError::Attr {
            attr: "iter(imports[module])",
            source,
        })? {
            let e = entry.map_err(|source| PyReadError::Attr {
                attr: "imports[module][i]",
                source,
            })?;
            let tag = read_import_var_tag(&e)?;
            if tag.is_empty() {
                continue;
            }
            let tag_root: String = tag.split('.').next().unwrap_or("").to_owned();
            if !is_js_identifier(&tag_root) {
                continue;
            }
            let module_sym = intern(&module);
            let tag_sym = intern(&tag_root);
            out.push((module_sym, tag_sym));
            // Register at the page level too, matching the old
            // `vardata_import_pairs` walk. Filter out the React runtime
            // names that always come from the baseline imports.
            if !(module == "react"
                && matches!(tag_root.as_str(), "Fragment" | "useContext" | "useRef"))
            {
                refs.harvest
                    .borrow_mut()
                    .add_component_import((module_sym, tag_sym));
            }
        }
    }
    Ok(out)
}

fn read_import_var_tag(entry: &Bound<'_, PyAny>) -> Result<String, PyReadError> {
    let tag = entry.getattr("tag").ok().filter(|v| !v.is_none());
    if let Some(t) = tag {
        if let Ok(s) = py_str(&t) {
            if !s.is_empty() {
                return Ok(s);
            }
        }
    }
    let name = entry.getattr("name").ok().filter(|v| !v.is_none());
    if let Some(n) = name {
        if let Ok(s) = py_str(&n) {
            return Ok(s);
        }
    }
    Ok(String::new())
}

// ---- Page-level harvest walks ----------------------------------------------
//
// Kept for reference / future parity testing. These were the three
// post-IR-build walks `read_page` used to run; they're superseded by
// the inline harvest registrations in `read_element`, `read_var_data_imports`,
// `read_value`, and `read_bare` above.

#[allow(dead_code)]
fn collect_component_imports(
    py: Python<'_>,
    root: &Bound<'_, PyAny>,
    arena: &Arena,
    refs: &PyRefs<'_>,
) -> Result<Vec<(Symbol, Symbol)>, PyReadError> {
    let mut seen: HashSet<(Symbol, Symbol)> = HashSet::new();
    let mut out: Vec<(Symbol, Symbol)> = Vec::new();
    let mut push = |pair: (Symbol, Symbol)| {
        if seen.insert(pair) {
            out.push(pair);
        }
    };

    walk_components(root, &mut |comp| {
        if let Some(pair) = import_alias_for(comp, refs)? {
            push(pair);
        }
        Ok(())
    })?;

    // VarData imports — second pass over all Vars in the tree.
    walk_values(root, refs, &mut |var| {
        let pairs = vardata_import_pairs(var, refs)?;
        for p in pairs {
            push(p);
        }
        Ok(())
    })?;
    let _ = (py, arena); // unused, kept for future GIL handling
    Ok(out)
}

fn import_alias_for(
    component: &Bound<'_, PyAny>,
    refs: &PyRefs<'_>,
) -> Result<Option<(Symbol, Symbol)>, PyReadError> {
    let library = match component.getattr("library") {
        Ok(v) if !v.is_none() => v,
        _ => return Ok(None),
    };
    let library_raw = py_str(&library)?;
    let tag = component.getattr("tag").ok().filter(|v| !v.is_none());
    let alias = component.getattr("alias").ok().filter(|v| !v.is_none());
    if tag.is_none() && alias.is_none() {
        return Ok(None);
    }

    let module = format_library_name(refs, &library_raw)?;
    let tag_root = tag
        .as_ref()
        .and_then(|t| py_str(t).ok())
        .map(|s| s.split('.').next().unwrap_or("").to_owned());
    let alias_root = alias
        .as_ref()
        .and_then(|a| py_str(a).ok())
        .map(|s| s.split('.').next().unwrap_or("").to_owned());

    if module == "react"
        && matches!(
            tag_root.as_deref(),
            Some("Fragment") | Some("useContext") | Some("useRef")
        )
    {
        return Ok(None);
    }

    let spec = match (&tag_root, &alias_root) {
        (Some(t), Some(a)) if a != t && !a.is_empty() => format!("{t} as {a}"),
        (Some(t), _) if !t.is_empty() => t.clone(),
        (_, Some(a)) if !a.is_empty() => a.clone(),
        _ => return Ok(None),
    };

    Ok(Some((intern(&module), intern(&spec))))
}

#[allow(dead_code)]
fn vardata_import_pairs(
    var: &Bound<'_, PyAny>,
    refs: &PyRefs<'_>,
) -> Result<Vec<(Symbol, Symbol)>, PyReadError> {
    let vd = match var.call_method0("_get_all_var_data") {
        Ok(v) if !v.is_none() => v,
        _ => return Ok(Vec::new()),
    };
    let raw = match vd.getattr("imports") {
        Ok(v) if !v.is_none() => v,
        _ => return Ok(Vec::new()),
    };
    let mut pairs: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>)> = Vec::new();
    if let Ok(d) = raw.downcast::<PyDict>() {
        for (k, v) in d.iter() {
            pairs.push((k, v));
        }
    } else {
        for item in raw.iter().map_err(|source| PyReadError::Attr {
            attr: "iter(VarData.imports)",
            source,
        })? {
            let p = item.map_err(|source| PyReadError::Attr {
                attr: "VarData.imports[i]",
                source,
            })?;
            let t: Bound<'_, PyTuple> = p
                .downcast_into()
                .map_err(|e| PyReadError::TypeMismatch {
                    attr: "VarData.imports tuple",
                    expected: "tuple",
                    got: e.to_string(),
                })?;
            if t.len() != 2 {
                continue;
            }
            pairs.push((
                t.get_item(0).map_err(|source| PyReadError::Attr {
                    attr: "VarData.imports[i][0]",
                    source,
                })?,
                t.get_item(1).map_err(|source| PyReadError::Attr {
                    attr: "VarData.imports[i][1]",
                    source,
                })?,
            ));
        }
    }
    let mut out: Vec<(Symbol, Symbol)> = Vec::new();
    for (module_obj, entries) in pairs {
        let module_raw = py_str(&module_obj)?;
        let module = format_library_name(refs, &module_raw)?;
        if module.is_empty() {
            continue;
        }
        for entry in entries.iter().map_err(|source| PyReadError::Attr {
            attr: "iter(imports[module])",
            source,
        })? {
            let e = entry.map_err(|source| PyReadError::Attr {
                attr: "imports[module][i]",
                source,
            })?;
            let tag = read_import_var_tag(&e)?;
            if tag.is_empty() {
                continue;
            }
            let root: String = tag.split('.').next().unwrap_or("").to_owned();
            if !is_js_identifier(&root) {
                continue;
            }
            if module == "react" && matches!(root.as_str(), "Fragment" | "useContext" | "useRef") {
                continue;
            }
            out.push((intern(&module), intern(&root)));
        }
    }
    Ok(out)
}

#[allow(dead_code)]
fn collect_state_bindings(
    _py: Python<'_>,
    root: &Bound<'_, PyAny>,
    _arena: &Arena,
    refs: &PyRefs<'_>,
) -> Result<Vec<Symbol>, PyReadError> {
    let mut seen: HashSet<String> = HashSet::new();
    let mut out: Vec<Symbol> = Vec::new();
    walk_values(root, refs, &mut |var| {
        if let Ok(expr) = read_attr_str(var, "_js_expr", "Var._js_expr") {
            for m in find_state_idents(&expr) {
                if seen.insert(m.to_owned()) {
                    out.push(intern(&m));
                }
            }
        }
        Ok(())
    })?;
    Ok(out)
}

/// Find `reflex___state____state__<name>_state` identifiers inside `expr`.
/// Hand-rolled (avoids pulling regex into the crate); the bridge.py regex
/// is `\breflex___state____state__[A-Za-z0-9_]+_state\b`.
fn find_state_idents(expr: &str) -> Vec<String> {
    const PREFIX: &str = "reflex___state____state__";
    const SUFFIX: &str = "_state";
    let mut out: Vec<String> = Vec::new();
    let bytes = expr.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i..].starts_with(PREFIX.as_bytes()) {
            // Boundary check on the left.
            if i > 0 {
                let prev = bytes[i - 1];
                if prev.is_ascii_alphanumeric() || prev == b'_' {
                    i += 1;
                    continue;
                }
            }
            let body_start = i + PREFIX.len();
            let mut j = body_start;
            while j < bytes.len() {
                let c = bytes[j];
                if c.is_ascii_alphanumeric() || c == b'_' {
                    j += 1;
                } else {
                    break;
                }
            }
            // Body must end with `_state` and right boundary must be non-word.
            if j > body_start && bytes[..j].ends_with(SUFFIX.as_bytes()) {
                let right_ok = j == bytes.len()
                    || !(bytes[j].is_ascii_alphanumeric() || bytes[j] == b'_');
                if right_ok {
                    out.push(String::from_utf8_lossy(&bytes[i..j]).into_owned());
                    i = j;
                    continue;
                }
            }
            i = body_start;
        } else {
            i += 1;
        }
    }
    out
}

#[allow(dead_code)]
fn scan_needs_ref(_py: Python<'_>, root: &Bound<'_, PyAny>) -> Result<bool, PyReadError> {
    let mut found = false;
    walk_components(root, &mut |comp| {
        if found {
            return Ok(());
        }
        if let Ok(v) = comp.getattr("id") {
            if !v.is_none() {
                found = true;
            }
        }
        Ok(())
    })?;
    Ok(found)
}

// ---- Tree iteration ---------------------------------------------------------

#[allow(dead_code)]
fn walk_components<F>(root: &Bound<'_, PyAny>, f: &mut F) -> Result<(), PyReadError>
where
    F: FnMut(&Bound<'_, PyAny>) -> Result<(), PyReadError>,
{
    f(root)?;
    if let Ok(children) = root.getattr("children") {
        if !children.is_none() {
            if let Ok(iter) = children.iter() {
                for c in iter {
                    let child = c.map_err(|source| PyReadError::Attr {
                        attr: "iter(children)",
                        source,
                    })?;
                    walk_components(&child, f)?;
                }
            }
        }
    }
    Ok(())
}

/// Yield every Var-typed value reachable from `root` (props, identity
/// props, event handlers, Bare contents). Matches bridge._walk_values.
#[allow(dead_code)]
fn walk_values<F>(
    root: &Bound<'_, PyAny>,
    refs: &PyRefs<'_>,
    f: &mut F,
) -> Result<(), PyReadError>
where
    F: FnMut(&Bound<'_, PyAny>) -> Result<(), PyReadError>,
{
    walk_components(root, &mut |comp| {
        if let Ok(prop_names) = comp.call_method0("get_props") {
            if let Ok(iter) = prop_names.iter() {
                for name_res in iter {
                    let name_obj = name_res.map_err(|source| PyReadError::Attr {
                        attr: "iter(get_props())",
                        source,
                    })?;
                    let raw: String = py_str(&name_obj)?;
                    let attr_name = raw.strip_suffix('_').unwrap_or(&raw);
                    if let Ok(v) = comp.getattr(attr_name) {
                        if isinstance(&v, &refs.var_cls, "prop value")? {
                            f(&v)?;
                        }
                    }
                }
            }
        }
        for name in ["key", "id", "class_name"] {
            if let Ok(v) = comp.getattr(name) {
                if !v.is_none() && isinstance(&v, &refs.var_cls, "identity prop")? {
                    f(&v)?;
                }
            }
        }
        if let Ok(triggers) = comp.getattr("event_triggers") {
            if !triggers.is_none() {
                if let Ok(d) = triggers.downcast::<PyDict>() {
                    for (_trigger, handler) in d.iter() {
                        if isinstance(&handler, &refs.var_cls, "event handler")? {
                            f(&handler)?;
                        } else if let Ok(wrapped) = refs
                            .literal_var_cls
                            .call_method1("create", (&handler,))
                        {
                            if isinstance(&wrapped, &refs.var_cls, "LiteralVar.create result")? {
                                f(&wrapped)?;
                            }
                        }
                    }
                }
            }
        }
        if let Ok(contents) = comp.getattr("contents") {
            if !contents.is_none() && isinstance(&contents, &refs.var_cls, "Bare.contents")? {
                f(&contents)?;
            }
        }
        Ok(())
    })
}

// ---- PyO3 helpers -----------------------------------------------------------

fn getattr<'py>(obj: &Bound<'py, PyAny>, attr: &'static str) -> Result<Bound<'py, PyAny>, PyReadError> {
    obj.getattr(attr).map_err(|source| PyReadError::Attr {
        attr,
        source,
    })
}

fn read_attr_str(
    obj: &Bound<'_, PyAny>,
    attr: &str,
    attr_static: &'static str,
) -> Result<String, PyReadError> {
    let v = obj.getattr(attr).map_err(|source| PyReadError::Attr {
        attr: attr_static,
        source,
    })?;
    py_str(&v)
}

fn isinstance(
    obj: &Bound<'_, PyAny>,
    cls: &Bound<'_, PyAny>,
    attr_static: &'static str,
) -> Result<bool, PyReadError> {
    obj.is_instance(cls).map_err(|source| PyReadError::Attr {
        attr: attr_static,
        source,
    })
}

pub(crate) fn py_str(obj: &Bound<'_, PyAny>) -> Result<String, PyReadError> {
    let s: Bound<'_, PyString> = obj.str().map_err(|source| PyReadError::Attr {
        attr: "str(value)",
        source,
    })?;
    s.to_str()
        .map(|v| v.to_owned())
        .map_err(|source| PyReadError::Attr {
            attr: "PyString::to_str",
            source,
        })
}

pub(crate) fn class_name(component: &Bound<'_, PyAny>) -> Result<String, PyReadError> {
    let ty = component
        .get_type()
        .name()
        .map_err(|source| PyReadError::Attr {
            attr: "__class__.__name__",
            source,
        })?;
    Ok(ty.to_string())
}

fn format_library_name(refs: &PyRefs<'_>, library: &str) -> Result<String, PyReadError> {
    let result = refs
        .format_library_name
        .call1((library,))
        .map_err(|source| PyReadError::Attr {
            attr: "format_library_name(library)",
            source,
        })?;
    py_str(&result)
}

/// Resolve the JS tag/component name for a generic Component, returning
/// the interned symbol. Bare HTML tags (`title`, `meta`) get quoted to
/// match the legacy emitter (`jsx("title", …)`).
fn resolve_tag_symbol(component: &Bound<'_, PyAny>) -> Result<Symbol, PyReadError> {
    let alias = component.getattr("alias").ok().filter(|v| !v.is_none());
    let tag = component.getattr("tag").ok().filter(|v| !v.is_none());
    let raw_name = match (&alias, &tag) {
        (Some(a), _) => py_str(a)?,
        (None, Some(t)) => py_str(t)?,
        _ => return Ok(Symbol::EMPTY),
    };
    let trimmed = raw_name.trim_matches('"').to_owned();
    if trimmed.is_empty() {
        return Ok(Symbol::EMPTY);
    }
    let library = component.getattr("library").ok().filter(|v| !v.is_none());
    let is_global_scope = match component.getattr("_is_tag_in_global_scope") {
        Ok(v) => v.is_truthy().unwrap_or(false),
        Err(_) => false,
    };
    let final_name = if library.is_none() && is_global_scope {
        format!("\"{trimmed}\"")
    } else {
        trimmed
    };
    Ok(intern(&final_name))
}

fn is_js_identifier(name: &str) -> bool {
    let mut chars = name.chars();
    let Some(first) = chars.next() else {
        return false;
    };
    if !(first.is_ascii_alphabetic() || first == '_' || first == '$') {
        return false;
    }
    for c in chars {
        if !(c.is_ascii_alphanumeric() || c == '_' || c == '$') {
            return false;
        }
    }
    true
}

#[cfg(test)]
mod state_ident_tests {
    use super::find_state_idents;

    #[test]
    fn finds_single_state() {
        let s = find_state_idents("reflex___state____state__counter_state.value");
        assert_eq!(s, vec!["reflex___state____state__counter_state"]);
    }

    #[test]
    fn ignores_partial_prefix() {
        assert!(find_state_idents("notthestate__counter_state").is_empty());
    }

    #[test]
    fn finds_multiple_distinct() {
        let s = find_state_idents(
            "reflex___state____state__a_state + reflex___state____state__b_state",
        );
        assert_eq!(
            s,
            vec![
                "reflex___state____state__a_state".to_owned(),
                "reflex___state____state__b_state".to_owned(),
            ]
        );
    }

    #[test]
    fn requires_state_suffix() {
        assert!(find_state_idents("reflex___state____state__not_terminated").is_empty());
    }
}
