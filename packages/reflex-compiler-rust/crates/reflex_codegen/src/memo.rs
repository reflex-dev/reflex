//! Emit a per-memo module — `export const <name> = memo(({children}) => …)`.
//!
//! Mirrors `packages/reflex-base/src/reflex_base/compiler/templates.py`'s
//! `memo_single_component_template`. Most of the import + JSX-render
//! plumbing is shared with `emit_page`; this module just swaps the page
//! shell for the `memo(...)` shell.
//!
//! Used by phase 3 of the memoize port (plan §0b lever (b3)): once we've
//! decided to wrap a Component, pyread builds an IR with the wrapped
//! body (children replaced by a `{children}` placeholder expression),
//! and this function emits the standalone memo module that the page
//! module then imports.

use reflex_intern::{intern, resolve_unchecked, Symbol};
use reflex_ir::Page;

use crate::buffer::CodeBuffer;
use crate::jsx::emit_component_with_map;

/// Baseline runtime aliases every memo module needs. `memo` from React
/// plus `jsx` from Emotion — anything else the body refers to gets
/// pulled in via the harvested `component_imports`.
const MEMO_RUNTIME_IMPORTS: &[(&str, &str)] = &[
    ("react", "memo"),
    ("react", "useContext"),
    ("react", "useRef"),
    ("$/utils/context", "EventLoopContext"),
    ("$/utils/context", "StateContexts"),
    ("$/utils/state", "refs"),
    ("$/utils/state", "ReflexEvent"),
    ("@emotion/react", "jsx"),
];

/// Emit a memo wrapper module.
///
/// The `Page` IR is reused as the input shape because the body of a memo
/// is structurally a single JSX tree — same as a page. Title / meta on
/// `page` are ignored (memos don't carry document metadata); everything
/// else flows through.
///
/// Args:
///     buf: target buffer.
///     page: the wrapper body's IR. Pyread builds this from the
///         hole-substituted Component (`children = [Bare(Var("children"))]`).
///     name: exported memo identifier (`export const <name> = …`).
///     signature: parameter list spliced after `memo(`. Use `"{ children }"`
///         for passthrough wrappers, `"()"` for snapshot bodies that don't
///         receive children.
///     pre_hooks: pre-rendered hook block (e.g. `const { resolvedColorMode }
///         = useContext(ColorModeContext)`) the Python orchestrator harvested
///         via `body._get_all_hooks()`. Spliced between the state-context
///         hooks and `return` so memo bodies that reference hook-defined
///         identifiers (color mode, custom `_get_hooks_internal`, etc.) get
///         their declarations. Pass `""` if there are none.
pub fn emit_memo_module(
    buf: &mut CodeBuffer,
    page: &Page<'_>,
    name: &str,
    signature: &str,
    pre_hooks: &str,
) {
    emit_combined_imports(buf, page.component_imports);

    buf.write_str("\nexport const ");
    buf.write_str(name);
    buf.write_str(" = memo(");
    buf.write_str(signature);
    buf.write_str(" => {\n");

    if page.needs_ref {
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
    if !pre_hooks.is_empty() {
        buf.write_str("  ");
        buf.write_str(pre_hooks);
        if !pre_hooks.ends_with('\n') {
            buf.write_str("\n");
        }
    }

    buf.write_str("  return ");
    emit_component_with_map(buf, page.root, None);
    buf.write_str(";\n});\n");
}

/// Emit the memo index module — the small barrel file at
/// `.web/utils/components.jsx` that re-exports every `@rx.memo` custom
/// component so `root.jsx` can pull them in via `$/utils/components`.
///
/// Mirrors `memo_index_template` in
/// `packages/reflex-base/src/reflex_base/compiler/templates.py`.
///
/// Streams output directly to `w` — no intermediate `String` is
/// allocated. Tests pass a `&mut Vec<u8>`; the PyO3 binding passes a
/// `BufWriter<File>` so bytes flow straight to disk.
///
/// Args:
///     reexports: `(export_name, relative_module_specifier)` pairs. The
///         specifier is the path component after `$/utils/` —
///         e.g. `("Foo", "components/Foo")` produces
///         `export { Foo } from "components/Foo";`.
///     w: a writer the rendered module source is streamed into.
pub fn emit_memo_index<W: std::io::Write>(
    reexports: &[(&str, &str)],
    w: &mut W,
) -> std::io::Result<()> {
    if reexports.is_empty() {
        // Match the legacy template exactly — an empty reexport list
        // produces a single trailing newline (joining `[]` with `"\n"`
        // yields `""`, then the template appends `"\n"`).
        return w.write_all(b"\n");
    }
    for (name, specifier) in reexports {
        w.write_all(b"export { ")?;
        w.write_all(name.as_bytes())?;
        w.write_all(b" } from \"")?;
        w.write_all(specifier.as_bytes())?;
        w.write_all(b"\";\n")?;
    }
    Ok(())
}

fn emit_combined_imports(buf: &mut CodeBuffer, component_imports: &[(Symbol, Symbol)]) {
    // Same dedup-by-module logic as `emit_page`'s `emit_combined_imports`,
    // but seeded with the memo-specific runtime header (`memo` instead of
    // `Fragment`). We split runtime imports into `react` (top) + rest
    // (bottom) so the layout matches the legacy `memo_single_component_template`
    // output.
    let mut combined: Vec<(Symbol, Symbol)> =
        Vec::with_capacity(MEMO_RUNTIME_IMPORTS.len() + component_imports.len());

    let runtime_react: Vec<(Symbol, Symbol)> = MEMO_RUNTIME_IMPORTS
        .iter()
        .filter(|(m, _)| *m == "react")
        .map(|(m, a)| (intern(m), intern(a)))
        .collect();
    let runtime_rest: Vec<(Symbol, Symbol)> = MEMO_RUNTIME_IMPORTS
        .iter()
        .filter(|(m, _)| *m != "react")
        .map(|(m, a)| (intern(m), intern(a)))
        .collect();

    combined.extend(runtime_react);
    combined.extend_from_slice(component_imports);
    combined.extend(runtime_rest);

    emit_imports_grouped_by_module(buf, &combined);
}

fn emit_imports_grouped_by_module(buf: &mut CodeBuffer, imports: &[(Symbol, Symbol)]) {
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
            if !first {
                buf.write_str(", ");
            }
            first = false;
            buf.write_str(resolve_unchecked(*alias));
            emitted.push(*alias);
        }
        buf.write_str(" } from \"");
        buf.write_str(resolve_unchecked(module));
        buf.write_str("\";\n");
    }
}

#[cfg(test)]
mod tests {
    use super::emit_memo_index;

    fn render(reexports: &[(&str, &str)]) -> String {
        let mut buf = Vec::new();
        emit_memo_index(reexports, &mut buf).unwrap();
        String::from_utf8(buf).unwrap()
    }

    #[test]
    fn emits_one_reexport_per_entry() {
        let reexports = [
            ("Foo", "components/Foo"),
            ("BarBaz", "components/BarBaz"),
        ];
        assert_eq!(
            render(&reexports),
            "export { Foo } from \"components/Foo\";\nexport { BarBaz } from \"components/BarBaz\";\n"
        );
    }

    #[test]
    fn empty_reexports_match_legacy_template() {
        // Legacy `memo_index_template([])` returns `"\n"` because
        // `"\n".join([]) + "\n" == "\n"`. The Rust port matches.
        assert_eq!(render(&[]), "\n");
    }
}
