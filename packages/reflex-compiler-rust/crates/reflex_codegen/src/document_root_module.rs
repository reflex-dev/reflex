//! Port of `document_root_template` (the legacy `.web/app/_document.js`
//! emitter).
//!
//! The document root provides React-Router's `<html>` / `<head>` /
//! `<body>` shell. The legacy template takes a pre-computed imports
//! list and a render dict; Phase-1 port has Python render both to
//! strings and Rust splice them into the layout fn.

use std::io::{self, Write};

/// Emit `.web/app/_document.js`.
///
/// Mirrors `document_root_template` in
/// `packages/reflex-base/src/reflex_base/compiler/templates.py`.
///
/// Args:
///     imports_str: rendered `import { … } from "…"` lines joined with
///         `\n` by the caller.
///     document_render_str: rendered JSX expression for the document
///         tree — splices verbatim into `return (…)`.
///     w: byte sink.
pub fn emit_document_root_module<W: Write>(
    imports_str: &str,
    document_render_str: &str,
    w: &mut W,
) -> io::Result<()> {
    w.write_all(imports_str.as_bytes())?;
    w.write_all(b"\n\nexport function Layout({children}) {\n  return (\n    ")?;
    w.write_all(document_render_str.as_bytes())?;
    w.write_all(b"\n  )\n}")?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn assembles_layout_with_render() {
        let mut buf = Vec::new();
        emit_document_root_module(
            "import { Foo } from \"bar\";",
            "jsx(Foo, {}, children)",
            &mut buf,
        )
        .unwrap();
        let out = String::from_utf8(buf).unwrap();
        assert_eq!(
            out,
            "import { Foo } from \"bar\";\n\nexport function Layout({children}) {\n  return (\n    jsx(Foo, {}, children)\n  )\n}"
        );
    }
}
