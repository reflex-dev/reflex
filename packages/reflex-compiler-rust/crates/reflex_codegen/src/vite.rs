//! Vite config emission. See plan §4.5 (artifact #8), D10.
//!
//! The config is a JS module that exports the default Vite config object.
//! For v1 we emit a minimal config — Reflex's existing Vite config has more
//! options but they're conditionally toggled and depend on Reflex's
//! configuration system, which lives in Python. We expose hooks so the
//! Python side can splice in plugin-specific blocks.

use crate::buffer::CodeBuffer;

/// Emit a minimal `vite.config.js` to `buf`.
///
/// `extra_plugins_js` is a free-form JS array body (e.g.
/// `"reflexPlugin(), tsconfigPaths()"`) that the Python side composes from
/// the plugin manifest. The emitter splices it verbatim — it's the Python
/// side's responsibility to ensure the snippet is valid JS.
pub fn emit_vite_config(buf: &mut CodeBuffer, extra_plugins_js: &str) {
    buf.write_str("import { defineConfig } from \"vite\";\n");
    buf.write_str("import react from \"@vitejs/plugin-react\";\n\n");

    buf.write_str("export default defineConfig({\n");
    buf.write_str("  plugins: [react()");
    if !extra_plugins_js.is_empty() {
        buf.write_str(", ");
        buf.write_str(extra_plugins_js);
    }
    buf.write_str("],\n");
    buf.write_str("  build: { outDir: \"dist\", emptyOutDir: true },\n");
    buf.write_str("  resolve: {\n");
    buf.write_str("    alias: {\n");
    buf.write_str("      \"$\": \"/src\",\n");
    buf.write_str("    },\n");
    buf.write_str("  },\n");
    buf.write_str("});\n");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn minimal_config() {
        let mut buf = CodeBuffer::new();
        emit_vite_config(&mut buf, "");
        let s = buf.as_str();
        assert!(s.contains("defineConfig"));
        assert!(s.contains("plugins: [react()],"));
    }

    #[test]
    fn config_with_extra_plugins() {
        let mut buf = CodeBuffer::new();
        emit_vite_config(&mut buf, "reflexPlugin()");
        let s = buf.as_str();
        assert!(s.contains("plugins: [react(), reflexPlugin()],"));
    }
}
