//! Port of `app_root_template` (the legacy `.web/app/root.jsx`
//! template), distinct from the IR-based `emit_app_root` in `app_root.rs`.
//!
//! The legacy template lays out the React-Router root: providers
//! (state, theme, event loop), an `AppWrap` shell that runs hooks +
//! renders the app-wrap-composed Component tree, the document Layout
//! wrap, and the EmbedLayout fallback used when `mount_target` is set.
//!
//! Phase-1 port: Python still does the dynamic rendering (component
//! → JSX, hooks → JS, imports → import lines) — those depend on the
//! legacy `_RenderUtils.render` walk. Rust assembles the static
//! template + splices the pre-rendered strings. Phase 2 will move
//! the renderers to Rust too.

use std::io::{self, Write};

/// Emit `.web/app/root.jsx`.
///
/// Mirrors `app_root_template` in
/// `packages/reflex-base/src/reflex_base/compiler/templates.py`. The
/// rendered output starts with a leading newline to match the legacy
/// f-string's `\n{imports_str}...` opening.
///
/// Args:
///     imports_str: rendered `import { … } from "…"` lines, joined
///         with `\n` by the caller.
///     dynamic_imports_str: rendered dynamic-import statements, joined
///         with `\n` by the caller.
///     custom_code_str: any user-contributed top-level code, joined
///         with `\n`.
///     hooks_str: rendered hook body (already includes its leading
///         indentation), or empty.
///     render_str: rendered JSX expression for the app-wrap chain — the
///         expression spliced inside `return (…)` in `AppWrap`.
///     import_window_libraries: rendered
///         `import * as <alias> from "…"` lines for window libraries.
///     window_imports_str: rendered `"<path>": <alias>,` entries that
///         populate the global `window["__reflex"]` mapping.
///     w: byte sink.
pub fn emit_app_root_module<W: Write>(
    imports_str: &str,
    dynamic_imports_str: &str,
    custom_code_str: &str,
    hooks_str: &str,
    render_str: &str,
    import_window_libraries: &str,
    window_imports_str: &str,
    w: &mut W,
) -> io::Result<()> {
    w.write_all(b"\n")?;
    w.write_all(imports_str.as_bytes())?;
    w.write_all(b"\n")?;
    w.write_all(dynamic_imports_str.as_bytes())?;
    w.write_all(
        b"\nimport { EventLoopProvider, StateProvider, defaultColorMode } from \"$/utils/context\";\n",
    )?;
    w.write_all(b"import { ThemeProvider } from '$/utils/react-theme';\n")?;
    w.write_all(b"import { Layout as AppLayout } from './_document';\n")?;
    w.write_all(b"import { Outlet } from 'react-router';\n")?;
    w.write_all(import_window_libraries.as_bytes())?;
    w.write_all(b"\n\n")?;
    w.write_all(custom_code_str.as_bytes())?;
    w.write_all(b"\n\nfunction ReflexProviders({children}) {\n")?;
    w.write_all(b"  useEffect(() => {\n")?;
    w.write_all(b"    // Make contexts and state objects available globally for dynamic eval'd components\n")?;
    w.write_all(b"    let windowImports = {\n      ")?;
    w.write_all(window_imports_str.as_bytes())?;
    w.write_all(b"\n    };\n    window[\"__reflex\"] = windowImports;\n  }, []);\n\n")?;
    w.write_all(
        b"  return jsx(ThemeProvider, {defaultTheme: defaultColorMode, attribute: \"class\"},\n",
    )?;
    w.write_all(b"    jsx(StateProvider, {},\n      jsx(EventLoopProvider, {},\n        jsx(AppWrap, {}, children)\n      )\n    )\n  );\n}\n\n\n")?;
    w.write_all(b"function AppWrap({children}) {\n")?;
    w.write_all(hooks_str.as_bytes())?;
    w.write_all(b"\nreturn (")?;
    w.write_all(render_str.as_bytes())?;
    w.write_all(b")\n}\n\n")?;
    w.write_all(b"export function Layout({children}) {\n")?;
    w.write_all(b"  return jsx(AppLayout, {}, jsx(ReflexProviders, {}, children));\n")?;
    w.write_all(b"}\n\n")?;
    w.write_all(b"// Used by entry.client.js when mount_target is configured: skips the document\n")?;
    w.write_all(b"// shell (which renders react-router's <Meta>/<Scripts>/<Links> and requires a\n")?;
    w.write_all(b"// framework router context) but keeps the runtime providers.\n")?;
    w.write_all(b"export function EmbedLayout({children}) {\n")?;
    w.write_all(b"  return jsx(ReflexProviders, {}, children);\n")?;
    w.write_all(b"}\n\n")?;
    w.write_all(b"export default function App() {\n  return jsx(Outlet, {});\n}\n\n")?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn render<F>(f: F) -> String
    where
        F: FnOnce(&mut Vec<u8>) -> io::Result<()>,
    {
        let mut buf = Vec::new();
        f(&mut buf).unwrap();
        String::from_utf8(buf).unwrap()
    }

    #[test]
    fn includes_react_router_outlet_default() {
        let out = render(|w| emit_app_root_module("", "", "", "", "null", "", "", w));
        assert!(out.contains("export default function App()"));
        assert!(out.contains("return jsx(Outlet, {});"));
    }

    #[test]
    fn splices_render_string_into_appwrap() {
        let out = render(|w| {
            emit_app_root_module(
                "import {Foo} from \"bar\";",
                "",
                "// custom",
                "  // hooks",
                "jsx(MyApp, {})",
                "",
                "",
                w,
            )
        });
        assert!(out.contains("import {Foo} from \"bar\";"));
        assert!(out.contains("// custom"));
        assert!(out.contains("// hooks"));
        assert!(out.contains("return (jsx(MyApp, {}))"));
    }
}
