//! `CompilerSession` — the real PyO3 entry point. See plan §3.4, D4.
//!
//! The Python side keeps a long-lived `CompilerSession` instance across
//! reloads. Each `compile_app(...)` call ships per-page msgpack blobs plus
//! the theme/global-state/plugin-manifest blobs; Rust parses, emits, and
//! returns a `CompiledOutput` carrying `{path: bytes}` for the Python side
//! to write.
//!
//! Salsa caching lands in D5. Until then every call rebuilds — the
//! `content_hash` ferried over the wire is recorded but unused.

use std::collections::HashMap;

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList, PyTuple};

use reflex_arena::Arena;
use reflex_codegen::{
    emit_app_root, emit_app_root_module, emit_context, emit_context_module,
    emit_document_root_module, emit_memo_index, emit_memo_module, emit_page,
    emit_page_with_extras, emit_page_with_map, emit_stateful_pages_json, emit_styles_root,
    emit_theme, emit_theme_module, emit_vite_config, CodeBuffer, SourceMap,
};
use reflex_db::CompilerDb;
use reflex_ir::{parse_global_state, parse_page, parse_plugin_manifest, parse_theme};
use reflex_pyread::{
    collect_all_imports as pyread_collect_all_imports,
    collect_all_imports_into as pyread_collect_all_imports_into,
    merge_imports_into as pyread_merge_imports_into, read_page,
    should_memoize as memoize_should_memoize, MemoRefs, PyRefs,
};

/// One per Python `reflex.compiler.session.CompilerSession`. Holds the
/// content-hash-keyed compile cache (D5) so hot-reload is incremental.
#[pyclass]
pub struct CompilerSession {
    db: CompilerDb,
}

#[pymethods]
impl CompilerSession {
    #[new]
    fn new() -> Self {
        Self {
            db: CompilerDb::new(),
        }
    }

    /// Cap the page cache. Pass `None` for unbounded.
    fn set_cache_capacity(&self, cap: Option<usize>) {
        self.db.set_cache_capacity(cap);
    }

    /// Drop all cached page renders. Equivalent to creating a new session.
    fn clear_cache(&self) {
        self.db.clear();
    }

    /// Number of cached page renders. Useful for tests + diagnostics.
    fn cache_len(&self) -> usize {
        self.db.cache_len()
    }

    /// Compile a single page's IR bytes to a JS source string. The Python side
    /// passes `(route_ident, page_ir_bytes)`; we return the rendered module
    /// source.
    ///
    /// This is the single-page fast path used by hot-reload. `compile_app`
    /// below batches over many pages and produces auxiliary artifacts.
    fn compile_page(
        &self,
        py: Python<'_>,
        route_ident: &str,
        page_bytes: &Bound<'_, PyBytes>,
    ) -> PyResult<String> {
        let bytes = page_bytes.as_bytes().to_vec();
        let route_ident = route_ident.to_owned();
        let db = self.db.clone();
        py.allow_threads(move || {
            db.emit_page(&route_ident, &bytes)
                .map(|s| s.as_ref().to_owned())
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
        })
    }

    /// Compile one page and also return its source map. The cache is bypassed
    /// (it stores only the rendered string, not the map). Use when you need
    /// diagnostic back-mapping; use `compile_page` for hot-reload.
    ///
    /// Returns `(rendered_js, [(offset, file_id, line, col), ...])`.
    fn compile_page_with_sourcemap(
        &self,
        py: Python<'_>,
        route_ident: &str,
        page_bytes: &Bound<'_, PyBytes>,
    ) -> PyResult<(String, Vec<(u32, u32, u32, u32)>)> {
        let bytes = page_bytes.as_bytes().to_vec();
        let route_ident = route_ident.to_owned();
        py.allow_threads(move || compile_page_with_sourcemap_inner(&route_ident, &bytes))
    }

    /// Compile a memo wrapper module from a Component PyObject.
    ///
    /// Mirrors `templates.memo_single_component_template` (plan §0b
    /// lever (b3)). The Component should already have its `{children}`
    /// hole substituted at the Python level (passthrough wrappers carry
    /// a single `Bare(Var(_js_expr="children"))` child; snapshot bodies
    /// own their full subtree). Pyread walks the tree; `emit_memo_module`
    /// emits the `export const <name> = memo(...)` shell.
    ///
    /// Args:
    ///     name: exported memo identifier.
    ///     signature: parameter list spliced after `memo(`. Typical
    ///         values are `"{ children }"` for passthroughs and `"()"`
    ///         for snapshot bodies.
    ///     component: the wrapper-component PyObject (already
    ///         hole-substituted).
    #[pyo3(signature = (name, signature, component, route="/__memo__", pre_hooks=""))]
    fn compile_memo_from_component<'py>(
        &self,
        py: Python<'py>,
        name: &str,
        signature: &str,
        component: &Bound<'py, PyAny>,
        route: &str,
        pre_hooks: &str,
    ) -> PyResult<String> {
        let refs = PyRefs::new(py)?;
        let arena = Arena::new();
        let page = read_page(py, component, route, None, &[], &arena, &refs)?;
        let mut buf = CodeBuffer::with_capacity(1024);
        emit_memo_module(&mut buf, &page, name, signature, pre_hooks);
        String::from_utf8(buf.into_bytes()).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "rust memo emit produced non-utf8: {e}"
            ))
        })
    }

    /// Emit the memo index module to `out_path`.
    ///
    /// Streams the rendered bytes straight to disk via a
    /// `BufWriter<File>` — no intermediate `String` allocation. Mirrors
    /// `memo_index_template` in
    /// `packages/reflex-base/src/reflex_base/compiler/templates.py`.
    ///
    /// Args:
    ///     reexports: list of `(export_name, relative_module_specifier)`
    ///         tuples.
    ///     out_path: absolute filesystem path the index gets written to.
    ///         Parent directory must already exist.
    fn compile_memo_index(
        &self,
        reexports: Vec<(String, String)>,
        out_path: &str,
    ) -> PyResult<()> {
        let pairs: Vec<(&str, &str)> = reexports
            .iter()
            .map(|(n, s)| (n.as_str(), s.as_str()))
            .collect();
        write_to_file(out_path, |w| emit_memo_index(&pairs, w))
    }

    /// Emit `.web/styles/styles.css`.
    ///
    /// Ports `styles_template` — wraps every stylesheet in an
    /// `@import url('…');` line under a single
    /// `@layer __reflex_base;` header.
    fn compile_styles_root(
        &self,
        stylesheets: Vec<String>,
        out_path: &str,
    ) -> PyResult<()> {
        let refs: Vec<&str> = stylesheets.iter().map(String::as_str).collect();
        write_to_file(out_path, |w| emit_styles_root(&refs, w))
    }

    /// Emit `.web/utils/theme.js`.
    ///
    /// Ports `theme_template` — a single
    /// `export default <theme_js>` line where `theme_js` is the JS
    /// object literal Python builds via `LiteralVar.create(theme)`.
    fn compile_theme_module(&self, theme_js: &str, out_path: &str) -> PyResult<()> {
        write_to_file(out_path, |w| emit_theme_module(theme_js, w))
    }

    /// Emit `.web/backend/stateful_pages.json`.
    ///
    /// Mirrors `App._write_stateful_pages_marker`. Python decides which
    /// routes are stateful (it requires a state walk we haven't ported);
    /// Rust just serializes the list as JSON and writes the file.
    fn compile_stateful_pages_marker(
        &self,
        routes: Vec<String>,
        out_path: &str,
    ) -> PyResult<()> {
        let refs: Vec<&str> = routes.iter().map(String::as_str).collect();
        write_to_file(out_path, |w| emit_stateful_pages_json(&refs, w))
    }

    /// Emit `.web/utils/context.js`.
    ///
    /// Ports `context_template` from
    /// `packages/reflex-base/src/reflex_base/compiler/templates.py`.
    ///
    /// Args:
    ///     is_dev_mode: emitted as `export const isDevMode = …`.
    ///     default_color_mode_js: the JS expression assigned to
    ///         `defaultColorMode` (a quoted string or a lookup expr).
    ///     state_name: full dotted name of the state root, or `None`
    ///         for the no-state fallback.
    ///     state_keys: full dotted names of every state context.
    ///     initial_state_json: pre-serialized initial-state dict.
    ///     client_storage_json: pre-serialized client-storage config.
    /// Emit `.web/app/root.jsx`.
    ///
    /// Ports `app_root_template`. Python pre-renders the dynamic
    /// strings (imports, hooks, render_str, …) using
    /// `_RenderUtils.render` + friends — those depend on the legacy
    /// Python JSX renderer. Rust splices them into the static layout.
    fn compile_app_root_module(
        &self,
        imports_str: &str,
        dynamic_imports_str: &str,
        custom_code_str: &str,
        hooks_str: &str,
        render_str: &str,
        import_window_libraries: &str,
        window_imports_str: &str,
        out_path: &str,
    ) -> PyResult<()> {
        write_to_file(out_path, |w| {
            emit_app_root_module(
                imports_str,
                dynamic_imports_str,
                custom_code_str,
                hooks_str,
                render_str,
                import_window_libraries,
                window_imports_str,
                w,
            )
        })
    }

    /// Emit `.web/app/_document.js`.
    ///
    /// Ports `document_root_template`. Python pre-renders the imports
    /// list and the document JSX expression; Rust splices both into
    /// the layout function.
    fn compile_document_root_module(
        &self,
        imports_str: &str,
        document_render_str: &str,
        out_path: &str,
    ) -> PyResult<()> {
        write_to_file(out_path, |w| {
            emit_document_root_module(imports_str, document_render_str, w)
        })
    }

    #[pyo3(signature = (is_dev_mode, default_color_mode_js, state_name, state_keys, initial_state_json, client_storage_json, out_path))]
    fn compile_context_module(
        &self,
        is_dev_mode: bool,
        default_color_mode_js: &str,
        state_name: Option<&str>,
        state_keys: Vec<String>,
        initial_state_json: &str,
        client_storage_json: &str,
        out_path: &str,
    ) -> PyResult<()> {
        let keys: Vec<&str> = state_keys.iter().map(String::as_str).collect();
        write_to_file(out_path, |w| {
            emit_context_module(
                is_dev_mode,
                default_color_mode_js,
                state_name,
                &keys,
                initial_state_json,
                client_storage_json,
                w,
            )
        })
    }

    /// Run the memoize-decision walk on a Component PyObject.
    ///
    /// Ports `reflex.compiler.plugins.memoize._should_memoize` to Rust
    /// (plan §0a phase 2 / §0b lever (b2)). Behavior-identical with the
    /// legacy predicate: for any Component the legacy plugin would
    /// memoize, this returns True; for any it would skip, False.
    ///
    /// Used by:
    ///
    /// * Parity tests (`tests/units/compiler/test_memoize_plugin.py`).
    /// * Phase 3 (wrapper construction in Rust) — once the decision is
    ///   produced here, the same walk can drive `Component::Memoize`
    ///   wrapping during pyread.
    fn should_memoize<'py>(
        &self,
        py: Python<'py>,
        component: &Bound<'py, PyAny>,
    ) -> PyResult<bool> {
        let pyrefs = PyRefs::new(py)?;
        let refs = MemoRefs::from_pyrefs(py, &pyrefs)?;
        Ok(memoize_should_memoize(py, component, &refs)?)
    }

    /// Mirror `Component._get_all_imports()` with the merge happening in
    /// Rust. Walks `component`'s children + `_get_components_in_props()`,
    /// calls each node's cached `_get_imports()`, and merges into a
    /// `HashMap` rather than the Python `merge_parsed_imports` recursion.
    ///
    /// Returns the same shape `_get_all_imports` returns:
    /// `dict[str, list[ImportVar]]` with no library-prefix transform —
    /// callers wrap in `merge_imports(...)` for the `$/utils/...`
    /// rewrite.
    fn collect_all_imports<'py>(
        &self,
        py: Python<'py>,
        component: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyDict>> {
        pyread_collect_all_imports(py, component)
    }

    /// In-place variant of [`collect_all_imports`]: walks `component`'s
    /// tree and merges every entry into `target` with the
    /// `merge_imports` library-prefix transform (`$/utils/...`)
    /// applied. The caller-owned `target` dict is mutated.
    ///
    /// Replaces the
    /// `merge_imports(target, component._get_all_imports())` pattern in
    /// `rust_pipeline.compile_pages` — accumulating across pages
    /// into one dict cuts the O(N²) outer-loop iteration the Python
    /// pattern incurs.
    fn collect_all_imports_into<'py>(
        &self,
        py: Python<'py>,
        target: &Bound<'py, PyDict>,
        component: &Bound<'py, PyAny>,
    ) -> PyResult<()> {
        pyread_collect_all_imports_into(py, target, component)
    }

    /// Apply the `merge_imports` library-prefix transform to every
    /// entry of `source` and append into `target` in place. Use this
    /// for dicts that aren't paired with a Component tree walk (custom
    /// component imports, hand-built import dicts), where the tree-
    /// walking [`collect_all_imports_into`] doesn't apply.
    fn merge_imports_into<'py>(
        &self,
        py: Python<'py>,
        target: &Bound<'py, PyDict>,
        source: &Bound<'py, PyDict>,
    ) -> PyResult<()> {
        pyread_merge_imports_into(py, target, source)
    }

    /// Snapshot the Rust-side per-phase timings from the most recent
    /// `compile_page_from_component` (or `read_page` directly). Returns
    /// a `dict[str, int]` keyed by phase name with nanosecond totals.
    ///
    /// Counters reset at the start of every `read_page`. Phase names
    /// mirror the call sites in `pyo3_reader.rs`:
    ///
    /// * `class_name_ns` — `type(c).__name__` dispatch
    /// * `resolve_tag_ns` — alias/tag/library reads in `resolve_tag_symbol`
    /// * `import_alias_ns` — same attrs re-read in `import_alias_for`
    /// * `needs_ref_ns` — `getattr("id")` check
    /// * `read_props_ns`, `read_children_ns`, `read_event_handlers_ns`
    /// * `read_var_data_ns` — Var._get_all_var_data + decode
    /// * `harvest_register_ns` — RefCell mutations
    /// * `emit_ns` — pure-Rust IR → JSX string build
    /// * `read_page_total_ns` — end-to-end `read_page`
    fn last_phase_timings_ns<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let t = reflex_pyread::timing::snapshot();
        let d = PyDict::new_bound(py);
        d.set_item("read_page_total_ns", t.read_page_total_ns)?;
        d.set_item("emit_ns", t.emit_ns)?;
        d.set_item("class_name_ns", t.class_name_ns)?;
        d.set_item("resolve_tag_ns", t.resolve_tag_ns)?;
        d.set_item("import_alias_ns", t.import_alias_ns)?;
        d.set_item("needs_ref_ns", t.needs_ref_ns)?;
        d.set_item("read_var_data_ns", t.read_var_data_ns)?;
        d.set_item("harvest_register_ns", t.harvest_register_ns)?;
        d.set_item("get_props_call_ns", t.get_props_call_ns)?;
        d.set_item("prop_value_getattr_ns", t.prop_value_getattr_ns)?;
        d.set_item("children_attr_ns", t.children_attr_ns)?;
        d.set_item("event_triggers_attr_ns", t.event_triggers_attr_ns)?;
        d.set_item("isinstance_var_ns", t.isinstance_var_ns)?;
        d.set_item("value_literal_dispatch_ns", t.value_literal_dispatch_ns)?;
        d.set_item("var_js_expr_attr_ns", t.var_js_expr_attr_ns)?;
        // Counts.
        d.set_item("node_count", t.node_count)?;
        d.set_item("element_count", t.element_count)?;
        d.set_item("var_count", t.var_count)?;
        d.set_item("prop_count", t.prop_count)?;
        d.set_item("event_handler_count", t.event_handler_count)?;
        Ok(d)
    }

    /// Compile a single page directly from a Python `Component` PyObject —
    /// the new lever-(a) entry point that bypasses `bridge.py` + msgpack.
    ///
    /// The reader walks `component` via PyO3 `getattr` (see plan §0b and
    /// `reflex_pyread::read_page`), builds the IR in-arena, and emits JSX.
    /// The cache is not consulted; D5's Salsa storage keys on msgpack
    /// content hashes and the pyread path doesn't produce one. Hot reload
    /// gains incremental caching later.
    ///
    /// Args:
    ///     route_ident: JS identifier used for the route export.
    ///     component: the page's root `BaseComponent` instance.
    ///     route: URL path (e.g. `/about`).
    ///     title: optional document title.
    ///     meta_tags: optional `[(name_or_property, content), …]` list.
    #[pyo3(signature = (route_ident, component, route, title=None, meta_tags=None, custom_code=None, hooks_body=None))]
    fn compile_page_from_component<'py>(
        &self,
        py: Python<'py>,
        route_ident: &str,
        component: &Bound<'py, PyAny>,
        route: &str,
        title: Option<&str>,
        meta_tags: Option<&Bound<'py, PyList>>,
        custom_code: Option<Vec<String>>,
        hooks_body: Option<&str>,
    ) -> PyResult<String> {
        let meta_pairs: Vec<(String, String)> = match meta_tags {
            Some(list) => {
                let mut out = Vec::with_capacity(list.len());
                for item in list.iter() {
                    let tup: Bound<PyTuple> = item.downcast_into()?;
                    if tup.len() != 2 {
                        return Err(pyo3::exceptions::PyValueError::new_err(
                            "meta_tags entries must be (name, content) tuples",
                        ));
                    }
                    let n: String = tup.get_item(0)?.extract()?;
                    let c: String = tup.get_item(1)?.extract()?;
                    out.push((n, c));
                }
                out
            }
            None => Vec::new(),
        };

        let custom_code_owned: Vec<String> = custom_code.unwrap_or_default();
        let custom_code_refs: Vec<&str> = custom_code_owned.iter().map(String::as_str).collect();
        let hooks = hooks_body.unwrap_or("");

        let refs = PyRefs::new(py)?;
        let arena = Arena::new();
        let page = read_page(py, component, route, title, &meta_pairs, &arena, &refs)?;
        let mut buf = CodeBuffer::with_capacity(1024);
        {
            let _emit = reflex_pyread::TimingSpan::new(reflex_pyread::TimingField::Emit);
            emit_page_with_extras(&mut buf, &page, route_ident, &custom_code_refs, hooks);
        }
        String::from_utf8(buf.into_bytes()).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "rust pyread emit produced non-utf8: {e}"
            ))
        })
    }

    /// Compile a whole app. Returns a `CompiledOutput` whose `files` dict maps
    /// output paths (relative to the Vite project root) to UTF-8 byte blobs.
    ///
    /// `pages`: list of `(route_ident, route_path, page_ir_bytes)` triples.
    /// `theme`: optional theme IR bytes.
    /// `global_state`: optional global-state IR bytes.
    /// `plugin_manifest`: optional plugin-manifest IR bytes.
    #[pyo3(signature = (pages, theme=None, global_state=None, plugin_manifest=None))]
    fn compile_app(
        &self,
        py: Python<'_>,
        pages: &Bound<'_, PyList>,
        theme: Option<&Bound<'_, PyBytes>>,
        global_state: Option<&Bound<'_, PyBytes>>,
        plugin_manifest: Option<&Bound<'_, PyBytes>>,
    ) -> PyResult<CompiledOutput> {
        let mut page_inputs: Vec<(String, String, Vec<u8>)> = Vec::with_capacity(pages.len());
        for item in pages.iter() {
            let tup: Bound<PyTuple> = item.downcast_into()?;
            if tup.len() != 3 {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "each page entry must be (route_ident, route_path, ir_bytes)",
                ));
            }
            let ident: String = tup.get_item(0)?.extract()?;
            let route: String = tup.get_item(1)?.extract()?;
            let bytes: Vec<u8> = tup.get_item(2)?.extract::<&[u8]>()?.to_vec();
            page_inputs.push((ident, route, bytes));
        }
        let theme_bytes = theme.map(|b| b.as_bytes().to_vec());
        let state_bytes = global_state.map(|b| b.as_bytes().to_vec());
        let plugin_bytes = plugin_manifest.map(|b| b.as_bytes().to_vec());

        let db = self.db.clone();
        let result = py
            .allow_threads(move || compile_app_inner(&db, page_inputs, theme_bytes, state_bytes, plugin_bytes))
            .map_err(map_err)?;
        Ok(result)
    }
}

fn map_err(e: CompileError) -> PyErr {
    pyo3::exceptions::PyValueError::new_err(e.to_string())
}

#[derive(Debug, thiserror::Error)]
enum CompileError {
    #[error("page compile failed for {route_ident}: {source}")]
    Page {
        route_ident: String,
        #[source]
        source: reflex_db::DbError,
    },
    #[error("theme parse failed: {0}")]
    Theme(reflex_ir::ParseError),
    #[error("global-state parse failed: {0}")]
    GlobalState(reflex_ir::ParseError),
    #[error("plugin manifest parse failed: {0}")]
    PluginManifest(reflex_ir::ParseError),
}

fn compile_page_with_sourcemap_inner(
    route_ident: &str,
    page_bytes: &[u8],
) -> PyResult<(String, Vec<(u32, u32, u32, u32)>)> {
    let arena = Arena::with_capacity(page_bytes.len() * 4);
    let page = parse_page(&arena, page_bytes)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("page parse: {e}")))?;
    let mut buf = CodeBuffer::with_capacity(page_bytes.len() * 2);
    let mut map = SourceMap::new();
    emit_page_with_map(&mut buf, &page, route_ident, &mut map);
    let js = String::from_utf8(buf.into_bytes()).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("emit produced non-utf8: {e}"))
    })?;
    let mappings: Vec<(u32, u32, u32, u32)> = map
        .entries()
        .iter()
        .map(|(offset, loc)| (*offset, loc.file.0, loc.line, loc.col))
        .collect();
    Ok((js, mappings))
}

fn compile_app_inner(
    db: &CompilerDb,
    pages: Vec<(String, String, Vec<u8>)>,
    theme: Option<Vec<u8>>,
    global_state: Option<Vec<u8>>,
    plugin_manifest: Option<Vec<u8>>,
) -> Result<CompiledOutput, CompileError> {
    let arena = Arena::new();
    let mut files: HashMap<String, Vec<u8>> = HashMap::with_capacity(pages.len() + 4);

    // D11: parallel page emit via rayon. Cache hits still avoid work.
    let parallel_inputs: Vec<(String, Vec<u8>)> = pages
        .iter()
        .map(|(ident, _, bytes)| (ident.clone(), bytes.clone()))
        .collect();
    let results = db.emit_pages_parallel(&parallel_inputs);
    for ((ident, route, _), result) in pages.iter().zip(results.into_iter()) {
        let rendered = result.map_err(|source| CompileError::Page {
            route_ident: ident.clone(),
            source,
        })?;
        let out_path = page_output_path(route);
        files.insert(out_path, rendered.as_bytes().to_vec());
    }

    if let Some(bytes) = theme {
        let theme = parse_theme(&arena, &bytes).map_err(CompileError::Theme)?;
        let mut buf = CodeBuffer::with_capacity(1024);
        emit_theme(&mut buf, &theme);
        files.insert("src/styles/theme.css".to_owned(), buf.into_bytes());
    }
    if let Some(bytes) = global_state {
        let state = parse_global_state(&arena, &bytes).map_err(CompileError::GlobalState)?;
        let mut buf = CodeBuffer::with_capacity(2048);
        emit_context(&mut buf, &state);
        files.insert("src/context.js".to_owned(), buf.into_bytes());
    }
    if let Some(bytes) = plugin_manifest {
        let manifest = parse_plugin_manifest(&arena, &bytes).map_err(CompileError::PluginManifest)?;
        let mut buf = CodeBuffer::with_capacity(2048);
        emit_app_root(&mut buf, &manifest);
        files.insert("src/AppWrap.jsx".to_owned(), buf.into_bytes());

        // Plugin static assets pass-through (artifact #7 in §4.5 — Python
        // ships path+bytes, Rust copies into the output map verbatim).
        for plugin in manifest.plugins {
            for (path, body) in plugin.static_assets {
                files.insert(
                    reflex_intern::resolve_unchecked(*path).to_owned(),
                    body.to_vec(),
                );
            }
        }
    }

    // Always emit a Vite config — Python doesn't need to opt in.
    let mut vite_buf = CodeBuffer::with_capacity(512);
    emit_vite_config(&mut vite_buf, "");
    files.insert("vite.config.js".to_owned(), vite_buf.into_bytes());

    Ok(CompiledOutput {
        files,
        orphans: Vec::new(),
        diagnostics: Vec::new(),
    })
}

/// Convert a route path to the emitted JS module path. `/` → `pages/index.jsx`,
/// `/about` → `pages/about.jsx`, `/foo/bar` → `pages/foo/bar.jsx`. The Python
/// side will respect this layout when writing files.
fn page_output_path(route: &str) -> String {
    let trimmed = route.trim_start_matches('/');
    if trimmed.is_empty() {
        return "pages/index.jsx".to_owned();
    }
    let mut out = String::with_capacity(8 + trimmed.len());
    out.push_str("pages/");
    out.push_str(trimmed);
    out.push_str(".jsx");
    out
}

#[pyclass]
pub struct CompiledOutput {
    files: HashMap<String, Vec<u8>>,
    orphans: Vec<String>,
    diagnostics: Vec<String>,
}

#[pymethods]
impl CompiledOutput {
    /// Return the rendered files as a `dict[str, bytes]`.
    fn files<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let dict = PyDict::new_bound(py);
        for (path, contents) in &self.files {
            dict.set_item(path, PyBytes::new_bound(py, contents))?;
        }
        Ok(dict)
    }

    /// Paths the Python side should delete (no longer emitted by Rust).
    fn orphans(&self) -> Vec<String> {
        self.orphans.clone()
    }

    /// Compiler diagnostics. List of pre-formatted strings for now; D11 will
    /// convert to structured `miette`-style records.
    fn diagnostics(&self) -> Vec<String> {
        self.diagnostics.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "CompiledOutput(files={}, orphans={}, diagnostics={})",
            self.files.len(),
            self.orphans.len(),
            self.diagnostics.len()
        )
    }
}

/// Open `out_path` for buffered write and run `f` on the writer, mapping
/// any `io::Error` into a Python `OSError`.
///
/// Used by every "build content + write to disk" PyO3 method on
/// `CompilerSession` so the buffering, error mapping, and flush
/// behaviour stay consistent across the whole static-artifact surface.
fn write_to_file<F>(out_path: &str, f: F) -> PyResult<()>
where
    F: FnOnce(&mut std::io::BufWriter<std::fs::File>) -> std::io::Result<()>,
{
    let file = std::fs::File::create(out_path)
        .map_err(|e| pyo3::exceptions::PyOSError::new_err(format!("{out_path}: {e}")))?;
    let mut w = std::io::BufWriter::new(file);
    f(&mut w).map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;
    std::io::Write::flush(&mut w)
        .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))
}
