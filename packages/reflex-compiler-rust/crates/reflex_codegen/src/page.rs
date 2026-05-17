//! Page-level emission: render a `Page` as a JS source string ready for the
//! Vite frontend to consume. See plan §4.1, §4.8.
//!
//! Output shape — the contract the running React frontend expects:
//!
//! ```js
//! import { Fragment, useContext, useRef } from "react";
//! import { Box as RadixThemesBox } from "@radix-ui/themes";   // from page.component_imports
//! import { EventLoopContext, StateContexts } from "$/utils/context";
//! import { refs, ReflexEvent } from "$/utils/state";
//! import { jsx } from "@emotion/react";
//!
//! export default function Component() {
//!   const ref_root = useRef(null); refs["ref_root"] = ref_root;   // when page.needs_ref
//!   const <state_path> = useContext(StateContexts.<state_path>);  // per state_bindings entry
//!   const [addEvents, connectErrors] = useContext(EventLoopContext);
//!   return ( jsx(...) );
//! }
//!
//! export const __reflex_route = "<route>";
//! export const __reflex_title = "<title>";
//! ```
//!
//! `route_ident` is only used for the `__reflex_route_ident` constant —
//! the React runtime always imports the page via the default export named
//! `Component`. Caller can override with [`emit_page_named`].

use reflex_intern::{intern, resolve_unchecked, Symbol};
use reflex_ir::Page;

use crate::buffer::CodeBuffer;
use crate::jsx::emit_component_with_map;
use crate::sourcemap::SourceMap;

/// Default JS function name the React runtime imports from each page module.
pub const DEFAULT_ROUTE_FN: &str = "Component";

/// Emit a full page module (no source-map recording, default `Component` name).
#[inline]
pub fn emit_page(buf: &mut CodeBuffer, page: &Page<'_>, route_ident: &str) {
    emit_page_inner(buf, page, route_ident, DEFAULT_ROUTE_FN, None, &[], "")
}

/// Emit a full page module with a custom JS function name.
#[inline]
pub fn emit_page_named(
    buf: &mut CodeBuffer,
    page: &Page<'_>,
    route_ident: &str,
    fn_name: &str,
) {
    emit_page_inner(buf, page, route_ident, fn_name, None, &[], "")
}

/// Emit a full page module and record an optional `SourceMap`.
pub fn emit_page_with_map(
    buf: &mut CodeBuffer,
    page: &Page<'_>,
    route_ident: &str,
    map: &mut SourceMap,
) {
    emit_page_inner(buf, page, route_ident, DEFAULT_ROUTE_FN, Some(map), &[], "")
}

/// Emit a full page module with caller-provided `custom_code` blocks
/// (Component `_get_all_custom_code()` strings spliced between imports
/// and the `export default function` line) and a `hooks_body` (pre-
/// rendered hooks block inserted inside the component function before
/// the `useContext(EventLoopContext)` line).
///
/// Mirrors the legacy `page_template` which renders custom code +
/// hooks alongside the JSX. Used by `compile_page_from_component` so
/// pages emitted via pyread include the markdown `ComponentMap_*`
/// closures (and similar helpers) the legacy template produced.
pub fn emit_page_with_extras(
    buf: &mut CodeBuffer,
    page: &Page<'_>,
    route_ident: &str,
    custom_code: &[&str],
    hooks_body: &str,
) {
    emit_page_inner(
        buf,
        page,
        route_ident,
        DEFAULT_ROUTE_FN,
        None,
        custom_code,
        hooks_body,
    )
}

fn emit_page_inner(
    buf: &mut CodeBuffer,
    page: &Page<'_>,
    route_ident: &str,
    fn_name: &str,
    map: Option<&mut SourceMap>,
    custom_code: &[&str],
    hooks_body: &str,
) {
    // ---- Imports ------------------------------------------------------
    //
    // React + Reflex runtime imports are always present. Component-class
    // imports come from page.component_imports (harvested by the bridge).
    //
    // We merge baseline runtime imports with component_imports through a
    // single grouped emitter so that aliases bringing in extras from the
    // same module (e.g. `ColorModeContext` alongside `EventLoopContext`)
    // collapse onto one import line instead of producing duplicates.

    emit_combined_imports(buf, page.component_imports);

    // ---- Custom code blocks ------------------------------------------
    // Component `_get_all_custom_code()` strings (markdown component
    // maps, JIT helpers, etc.) get spliced between imports and the
    // `export default function` line — matching the legacy `page_template`.
    for block in custom_code {
        buf.write_byte(b'\n');
        buf.write_str(block);
        if !block.ends_with('\n') {
            buf.write_byte(b'\n');
        }
    }

    // ---- Render function ---------------------------------------------
    buf.write_str("\nexport default function ");
    buf.write_str(fn_name);
    buf.write_str("() {\n");

    if page.needs_ref {
        // Single shared ref for now; once the bridge tracks per-`id` refs
        // we'll emit one line per id. The legacy renderer uses
        // `ref_<id_or_synthetic>`.
        buf.write_str(
            "  const ref_root = useRef(null); refs[\"ref_root\"] = ref_root;\n",
        );
    }
    for binding in page.state_bindings {
        let s = resolve_unchecked(*binding);
        buf.write_str("  const ");
        buf.write_str(s);
        buf.write_str(" = useContext(StateContexts.");
        buf.write_str(s);
        buf.write_str(");\n");
    }
    buf.write_str(
        "  const [addEvents, connectErrors] = useContext(EventLoopContext);\n",
    );

    // ---- Hooks block --------------------------------------------------
    // Pre-rendered hook body from the caller — declarations the
    // legacy `_render_hooks` would have produced. We splice the
    // string verbatim; if it's non-empty and doesn't end with a
    // newline, add one to keep the trailing `return` separate.
    if !hooks_body.is_empty() {
        buf.write_str(hooks_body);
        if !hooks_body.ends_with('\n') {
            buf.write_byte(b'\n');
        }
    }

    // If the page declares a title or any meta tags, wrap the root in a
    // Fragment alongside the synthetic <title> / <meta> JSX children so the
    // browser tab + social-card metadata work the same way the legacy
    // compiler emits them.
    let wrap_in_fragment = page.title.is_some() || !page.meta.is_empty();

    buf.write_str("  return ");
    if wrap_in_fragment {
        buf.write_str("jsx(Fragment, {}, ");
        emit_component_with_map(buf, page.root, map);
        if let Some(title) = page.title {
            buf.write_str(", jsx(\"title\", {}, ");
            buf.write_js_string(title);
            buf.write_str(")");
        }
        for meta in page.meta {
            buf.write_str(", jsx(\"meta\", {");
            let name = resolve_unchecked(meta.name);
            // Treat well-known social/OG keys as `property=…`; everything
            // else uses `name=…`. Matches the legacy emitter's convention.
            let key = if name.starts_with("og:") || name.starts_with("twitter:") {
                "property"
            } else {
                "name"
            };
            buf.write_str(key);
            buf.write_str(": ");
            buf.write_js_string(name);
            buf.write_str(", content: ");
            buf.write_js_string(meta.content);
            buf.write_str("})");
        }
        buf.write_str(")");
    } else {
        emit_component_with_map(buf, page.root, map);
    }
    buf.write_str(";\n}\n");

    // ---- Page metadata exports ---------------------------------------
    buf.write_str("\nexport const __reflex_route = ");
    buf.write_js_string(page.route);
    buf.write_str(";\n");

    buf.write_str("export const __reflex_route_ident = ");
    buf.write_js_string(route_ident);
    buf.write_str(";\n");

    if let Some(title) = page.title {
        buf.write_str("export const __reflex_title = ");
        buf.write_js_string(title);
        buf.write_str(";\n");
    }
}

/// Baseline runtime aliases that every page module needs, paired with the
/// module they come from. Emitted alongside `component_imports` so a single
/// grouped pass dedupes overlapping symbols (e.g. `EventLoopContext`).
const RUNTIME_IMPORTS: &[(&str, &str)] = &[
    ("react", "Fragment"),
    ("react", "useContext"),
    ("react", "useRef"),
    ("$/utils/context", "EventLoopContext"),
    ("$/utils/context", "StateContexts"),
    ("$/utils/state", "refs"),
    ("$/utils/state", "ReflexEvent"),
    ("@emotion/react", "jsx"),
];

/// Emit imports for a page module by combining baseline runtime imports with
/// the component-harvested `component_imports` from the IR, in that order.
///
/// `react` is anchored at the top and `@emotion/react` at the bottom to match
/// the layout the legacy emitter produced; modules harvested from
/// `component_imports` slot in between in first-seen order. Aliases that
/// appear in both sources collapse via the per-module dedup inside
/// `emit_imports_grouped_by_module`.
fn emit_combined_imports(buf: &mut CodeBuffer, component_imports: &[(Symbol, Symbol)]) {
    let mut combined: Vec<(Symbol, Symbol)> =
        Vec::with_capacity(RUNTIME_IMPORTS.len() + component_imports.len());

    let runtime_react: Vec<(Symbol, Symbol)> = RUNTIME_IMPORTS
        .iter()
        .filter(|(m, _)| *m == "react")
        .map(|(m, a)| (intern(m), intern(a)))
        .collect();
    let runtime_rest: Vec<(Symbol, Symbol)> = RUNTIME_IMPORTS
        .iter()
        .filter(|(m, _)| *m != "react")
        .map(|(m, a)| (intern(m), intern(a)))
        .collect();

    combined.extend(runtime_react);
    combined.extend_from_slice(component_imports);
    combined.extend(runtime_rest);

    emit_imports_grouped_by_module(buf, &combined);
}

fn emit_imports_grouped_by_module(
    buf: &mut CodeBuffer,
    imports: &[(Symbol, Symbol)],
) {
    // Imports are `(module, alias_spec)` pairs where alias_spec is the
    // string spliced inside `import { … }` — either a bare identifier
    // (`"useState"`) or a renamed one (`"Box as RadixThemesBox"`). We
    // group by module preserving first-seen order, and within each module
    // dedup the alias_spec list so the bridge can pass redundant entries
    // without producing `{ useState, useState }`.
    let mut modules: Vec<Symbol> = Vec::new();
    for (m, _) in imports {
        if !modules.contains(m) {
            modules.push(*m);
        }
    }
    for module in modules {
        let mut emitted: Vec<Symbol> = Vec::new();
        buf.write_str("import { ");
        let mut first = true;
        for (m, alias) in imports {
            if *m != module {
                continue;
            }
            if emitted.contains(alias) {
                continue;
            }
            emitted.push(*alias);
            if !first {
                buf.write_str(", ");
            }
            first = false;
            buf.write_str(resolve_unchecked(*alias));
        }
        buf.write_str(" } from ");
        buf.write_js_string(resolve_unchecked(module));
        buf.write_str(";\n");
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use reflex_arena::Arena;
    use reflex_ir::parse::test_helpers::tiny_page_bytes;
    use reflex_ir::parse_page;

    #[test]
    fn emits_page_module() {
        let arena = Arena::new();
        let bytes = tiny_page_bytes();
        let page = parse_page(&arena, &bytes).unwrap();
        let mut buf = CodeBuffer::new();
        emit_page(&mut buf, &page, "Index");
        let s = buf.as_str();
        assert!(s.contains("import { Fragment, useContext, useRef } from \"react\""));
        assert!(s.contains(
            "import { EventLoopContext, StateContexts } from \"$/utils/context\""
        ));
        assert!(s.contains("export default function Component()"));
        assert!(s.contains("const [addEvents, connectErrors] = useContext(EventLoopContext);"));
        assert!(s.contains("jsx(div, {id: x}, \"hello\")"));
        assert!(s.contains("export const __reflex_route = \"/index\""));
        assert!(s.contains("export const __reflex_route_ident = \"Index\""));
    }

    #[test]
    fn page_with_component_imports() {
        use reflex_ir::{Component, NodeId, Page as PageIR, SourceLoc};
        let arena = Arena::new();
        let text = arena.alloc(Component::Text {
            value: "x",
            id: NodeId(1),
            source_loc: SourceLoc::SYNTHETIC,
        });
        let imports = [(
            reflex_intern::intern("@radix-ui/themes"),
            reflex_intern::intern("Box as RadixThemesBox"),
        )];
        let bindings = [reflex_intern::intern(
            "reflex___state____state__demo____my_state",
        )];
        let page = PageIR {
            schema_version: 2,
            route: "/x",
            root: &*text,
            title: None,
            meta: &[],
            source_files: &[],
            component_imports: arena.bump().alloc_slice_copy(&imports),
            state_bindings: arena.bump().alloc_slice_copy(&bindings),
            needs_ref: true,
        };
        let mut buf = CodeBuffer::new();
        emit_page(&mut buf, &page, "X");
        let s = buf.as_str();
        assert!(
            s.contains("import { Box as RadixThemesBox } from \"@radix-ui/themes\""),
            "got:\n{s}"
        );
        assert!(s.contains(
            "const reflex___state____state__demo____my_state = useContext(StateContexts.reflex___state____state__demo____my_state);"
        ));
        assert!(s.contains("const ref_root = useRef(null); refs[\"ref_root\"] = ref_root;"));
    }

    #[test]
    fn runtime_imports_merge_with_component_imports() {
        // Regression: when VarData walks bring `$/utils/context` /
        // `$/utils/state` symbols into `component_imports`, the page emitter
        // must merge them with the baseline runtime imports rather than
        // emitting a second `import { ... } from "$/utils/context"` line that
        // re-declares `EventLoopContext` / `StateContexts`.
        use reflex_ir::{Component, NodeId, Page as PageIR, SourceLoc};
        let arena = Arena::new();
        let text = arena.alloc(Component::Text {
            value: "x",
            id: NodeId(1),
            source_loc: SourceLoc::SYNTHETIC,
        });
        let imports = [
            (
                reflex_intern::intern("$/utils/context"),
                reflex_intern::intern("EventLoopContext"),
            ),
            (
                reflex_intern::intern("$/utils/context"),
                reflex_intern::intern("StateContexts"),
            ),
            (
                reflex_intern::intern("$/utils/context"),
                reflex_intern::intern("ColorModeContext"),
            ),
            (
                reflex_intern::intern("$/utils/state"),
                reflex_intern::intern("ReflexEvent"),
            ),
            (
                reflex_intern::intern("$/utils/state"),
                reflex_intern::intern("applyEventActions"),
            ),
        ];
        let page = PageIR {
            schema_version: 2,
            route: "/x",
            root: &*text,
            title: None,
            meta: &[],
            source_files: &[],
            component_imports: arena.bump().alloc_slice_copy(&imports),
            state_bindings: &[],
            needs_ref: false,
        };
        let mut buf = CodeBuffer::new();
        emit_page(&mut buf, &page, "X");
        let s = buf.as_str();

        // Each runtime module appears exactly once.
        assert_eq!(
            s.matches("from \"$/utils/context\"").count(),
            1,
            "$/utils/context emitted more than once:\n{s}"
        );
        assert_eq!(
            s.matches("from \"$/utils/state\"").count(),
            1,
            "$/utils/state emitted more than once:\n{s}"
        );

        // The merged $/utils/context line carries baseline + the extra
        // ColorModeContext brought in by component_imports.
        assert!(
            s.contains(
                "import { EventLoopContext, StateContexts, ColorModeContext } from \"$/utils/context\";"
            ),
            "merged context import missing:\n{s}"
        );
        // The merged $/utils/state line carries baseline + applyEventActions
        // (first-seen order: component_imports come before the trailing
        // baseline aliases, so `refs` slots in after `applyEventActions`).
        assert!(
            s.contains(
                "import { ReflexEvent, applyEventActions, refs } from \"$/utils/state\";"
            ),
            "merged state import missing:\n{s}"
        );
    }

    #[test]
    fn source_map_records_non_synthetic_locs() {
        use reflex_ir::{Component, NodeId, Page as PageIR, PyFileId, SourceLoc};
        let arena = Arena::new();
        let real_loc = SourceLoc { file: PyFileId(7), line: 42, col: 11 };
        let text = arena.alloc(Component::Text {
            value: arena.alloc_str("hi"),
            id: NodeId(1),
            source_loc: real_loc,
        });
        let page = PageIR {
            schema_version: 2,
            route: "/r",
            root: &*text,
            title: None,
            meta: &[],
            source_files: &[],
            component_imports: &[],
            state_bindings: &[],
            needs_ref: false,
        };
        let mut buf = CodeBuffer::new();
        let mut map = crate::SourceMap::new();
        emit_page_with_map(&mut buf, &page, "R", &mut map);
        let s = buf.as_str();
        let pos = s.find("\"hi\"").expect(r#"the "hi" literal should be in the output"#);
        let mapped = map.lookup(pos as u32).expect("location recorded");
        assert_eq!(mapped.file.0, 7);
        assert_eq!(mapped.line, 42);
        assert_eq!(map.len(), 1);
    }
}
