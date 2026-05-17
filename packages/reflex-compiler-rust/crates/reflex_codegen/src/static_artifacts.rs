//! Mechanical ports of the small static-artifact templates that
//! ``rust_pipeline.py`` needs to write into ``.web/``.
//!
//! Each function streams output through a generic ``Write`` so the
//! PyO3 binding can hand it a ``BufWriter<File>`` and skip any
//! intermediate ``String`` allocation. Unit tests pass ``&mut Vec<u8>``
//! and compare against the legacy Python templates in
//! ``packages/reflex-base/src/reflex_base/compiler/templates.py``.

use std::io::{self, Write};

/// Emit ``.web/styles/styles.css``.
///
/// Ports ``styles_template`` —
/// ``"@layer __reflex_base;\n" + "\n".join(f"@import url('{s}');", ...)``.
///
/// Args:
///     stylesheets: stylesheet URLs/paths spliced into ``@import`` lines.
///     w: byte sink.
pub fn emit_styles_root<W: Write>(stylesheets: &[&str], w: &mut W) -> io::Result<()> {
    w.write_all(b"@layer __reflex_base;\n")?;
    for (i, sheet) in stylesheets.iter().enumerate() {
        if i > 0 {
            w.write_all(b"\n")?;
        }
        w.write_all(b"@import url('")?;
        w.write_all(sheet.as_bytes())?;
        w.write_all(b"');")?;
    }
    Ok(())
}

/// Emit ``.web/utils/theme.js``.
///
/// Ports ``theme_template`` — ``f"export default {theme}"``. ``theme``
/// is already a JS object literal (the legacy compiler runs
/// ``LiteralVar.create(theme)`` before passing it in).
///
/// Args:
///     theme_js: the JS expression that becomes the default export.
///     w: byte sink.
pub fn emit_theme_module<W: Write>(theme_js: &str, w: &mut W) -> io::Result<()> {
    w.write_all(b"export default ")?;
    w.write_all(theme_js.as_bytes())
}

/// Write ``.web/backend/stateful_pages.json``.
///
/// Mirrors ``App._write_stateful_pages_marker`` — emits a JSON array of
/// route strings the backend treats as stateful. The Python side
/// computes the route list (it requires a state walk we haven't ported
/// yet); Rust just serializes and writes.
///
/// Args:
///     routes: stateful route strings.
///     w: byte sink.
pub fn emit_stateful_pages_json<W: Write>(routes: &[&str], w: &mut W) -> io::Result<()> {
    w.write_all(b"[")?;
    for (i, route) in routes.iter().enumerate() {
        if i > 0 {
            w.write_all(b", ")?;
        }
        write_json_string(w, route)?;
    }
    w.write_all(b"]")
}

/// Write a JSON-escaped string literal (with surrounding quotes).
///
/// Matches Python's ``json.dumps`` for ASCII inputs: backslash, quote,
/// and control bytes are escaped; everything else is passed through
/// verbatim. Route strings are URL paths so this is sufficient — full
/// Unicode JSON escaping isn't needed here.
fn write_json_string<W: Write>(w: &mut W, s: &str) -> io::Result<()> {
    w.write_all(b"\"")?;
    let bytes = s.as_bytes();
    let mut start = 0;
    for (i, &b) in bytes.iter().enumerate() {
        let escaped: &[u8] = match b {
            b'"' => b"\\\"",
            b'\\' => b"\\\\",
            b'\n' => b"\\n",
            b'\r' => b"\\r",
            b'\t' => b"\\t",
            0x08 => b"\\b",
            0x0c => b"\\f",
            0x00..=0x1f => {
                // Rare control byte; fall back to the \uXXXX form.
                w.write_all(&bytes[start..i])?;
                write!(w, "\\u{:04x}", b)?;
                start = i + 1;
                continue;
            }
            _ => continue,
        };
        w.write_all(&bytes[start..i])?;
        w.write_all(escaped)?;
        start = i + 1;
    }
    w.write_all(&bytes[start..])?;
    w.write_all(b"\"")
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
    fn styles_root_matches_legacy_template() {
        // `styles_template(["a.css", "b.css"])` =
        // "@layer __reflex_base;\n@import url('a.css');\n@import url('b.css');"
        let out = render(|w| emit_styles_root(&["a.css", "b.css"], w));
        assert_eq!(
            out,
            "@layer __reflex_base;\n@import url('a.css');\n@import url('b.css');"
        );
    }

    #[test]
    fn styles_root_empty_list_keeps_layer_header() {
        // `styles_template([])` = "@layer __reflex_base;\n" + "" = "@layer __reflex_base;\n"
        let out = render(|w| emit_styles_root(&[], w));
        assert_eq!(out, "@layer __reflex_base;\n");
    }

    #[test]
    fn theme_module_matches_legacy_template() {
        // `theme_template("{accentColor: 'tomato'}")` =
        // "export default {accentColor: 'tomato'}"
        let out = render(|w| emit_theme_module("{accentColor: 'tomato'}", w));
        assert_eq!(out, "export default {accentColor: 'tomato'}");
    }

    #[test]
    fn stateful_pages_empty_list() {
        let out = render(|w| emit_stateful_pages_json(&[], w));
        assert_eq!(out, "[]");
    }

    #[test]
    fn stateful_pages_with_routes() {
        let out =
            render(|w| emit_stateful_pages_json(&["index", "about", "blog/post-1"], w));
        assert_eq!(out, r#"["index", "about", "blog/post-1"]"#);
    }

    #[test]
    fn stateful_pages_escapes_special_chars() {
        let out = render(|w| emit_stateful_pages_json(&["a/\"b\""], w));
        assert_eq!(out, r#"["a/\"b\""]"#);
    }
}
