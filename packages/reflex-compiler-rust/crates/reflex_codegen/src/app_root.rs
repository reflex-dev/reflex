//! App-root wrapper emission. See plan §4.5 (artifact #5), D10.
//!
//! The app root is the top-level React component that wraps every page with
//! providers (state, theme, color-mode) plus error boundaries. The shape
//! mirrors Reflex's existing template, with imports gathered from the
//! `PluginManifest.stylesheet_imports` list.

use reflex_intern::resolve_unchecked;
use reflex_ir::PluginManifest;

use crate::buffer::CodeBuffer;

pub fn emit_app_root(buf: &mut CodeBuffer, manifest: &PluginManifest<'_>) {
    buf.write_str("import { jsx, Fragment } from \"react/jsx-runtime\";\n");
    buf.write_str("import { StateContext, ColorModeContext, initialState } from \"./context\";\n");
    buf.write_str("import { useState } from \"react\";\n");

    // Plugin stylesheets — `import "./some.css";` side-effect imports.
    let mut emitted = std::collections::HashSet::new();
    for plugin in manifest.plugins {
        for ss in plugin.stylesheet_imports {
            if !emitted.insert(*ss) {
                continue;
            }
            buf.write_str("import ");
            buf.write_js_string(resolve_unchecked(*ss));
            buf.write_str(";\n");
        }
    }

    buf.write_str("\nexport default function AppWrap({ children }) {\n");
    buf.write_str("  const [state, setState] = useState(initialState);\n");
    buf.write_str("  const [colorMode, setColorMode] = useState(\"system\");\n");
    buf.write_str("  return jsx(StateContext.Provider, { value: state }, ");
    buf.write_str("jsx(ColorModeContext.Provider, { value: colorMode }, children));\n");
    buf.write_str("}\n");
}

#[cfg(test)]
mod tests {
    use super::*;
    use reflex_ir::{PluginEntry, PluginManifest};

    #[test]
    fn emits_app_root_shell() {
        let manifest = PluginManifest {
            schema_version: 1,
            plugins: &[],
        };
        let mut buf = CodeBuffer::new();
        emit_app_root(&mut buf, &manifest);
        let s = buf.as_str();
        assert!(s.contains("export default function AppWrap"));
        assert!(s.contains("StateContext.Provider"));
    }

    #[test]
    fn emits_plugin_stylesheets() {
        let entry = PluginEntry {
            name: reflex_intern::intern("radix"),
            static_assets: &[],
            stylesheet_imports: &[reflex_intern::intern("@radix-ui/themes/styles.css")],
        };
        let manifest = PluginManifest {
            schema_version: 1,
            plugins: std::slice::from_ref(&entry),
        };
        let mut buf = CodeBuffer::new();
        emit_app_root(&mut buf, &manifest);
        assert!(buf.as_str().contains("import \"@radix-ui/themes/styles.css\""));
    }
}
