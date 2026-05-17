//! Pure-Rust string helpers shared by the reader.
//!
//! These live in their own module so they can be unit-tested with
//! `cargo test -p reflex_pyread --no-default-features` (the pyo3 dep is
//! optional — see `Cargo.toml` for why).

/// Decode a JS string literal of the form `"..."` to its content. Returns
/// `None` if `expr` is not a quoted string literal.
///
/// Mirrors the `expr.startswith('"') and expr.endswith('"')` branch in
/// `reflex.compiler.ir.bridge.component_to_ir`: tries strict JSON decoding
/// first (handles `\uXXXX`, `\n`, `\"`, …), falls back to stripping the
/// surrounding quotes verbatim on malformed input (matches bridge.py's
/// `json.JSONDecodeError` recovery).
pub fn decode_js_string_literal(expr: &str) -> Option<String> {
    let bytes = expr.as_bytes();
    if bytes.len() < 2 || bytes[0] != b'"' || bytes[bytes.len() - 1] != b'"' {
        return None;
    }
    Some(decode_json_string(expr).unwrap_or_else(|| expr[1..expr.len() - 1].to_owned()))
}

/// Decode a `"..."` JSON string. Returns `None` on malformed input so the
/// caller can fall back to the verbatim slice.
fn decode_json_string(literal: &str) -> Option<String> {
    let inner = &literal[1..literal.len() - 1];
    let mut out = String::with_capacity(inner.len());
    let mut chars = inner.chars();
    while let Some(c) = chars.next() {
        if c != '\\' {
            out.push(c);
            continue;
        }
        match chars.next()? {
            '"' => out.push('"'),
            '\\' => out.push('\\'),
            '/' => out.push('/'),
            'b' => out.push('\u{0008}'),
            'f' => out.push('\u{000C}'),
            'n' => out.push('\n'),
            'r' => out.push('\r'),
            't' => out.push('\t'),
            'u' => {
                let mut hex = String::with_capacity(4);
                for _ in 0..4 {
                    hex.push(chars.next()?);
                }
                let code = u32::from_str_radix(&hex, 16).ok()?;
                let ch = char::from_u32(code)?;
                out.push(ch);
            }
            _ => return None,
        }
    }
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn json_string_decoded() {
        assert_eq!(decode_js_string_literal(r#""hello""#).as_deref(), Some("hello"));
    }

    #[test]
    fn unicode_minus_decoded() {
        // `"−"` is the unicode-minus glyph wrapped as a JS literal.
        assert_eq!(decode_js_string_literal("\"−\"").as_deref(), Some("−"));
    }

    #[test]
    fn json_escapes_decoded() {
        assert_eq!(decode_js_string_literal(r#""a\nb""#).as_deref(), Some("a\nb"));
        assert_eq!(decode_js_string_literal(r#""é""#).as_deref(), Some("é"));
    }

    #[test]
    fn non_literal_returns_none() {
        assert_eq!(decode_js_string_literal("state.value"), None);
        assert_eq!(decode_js_string_literal(r#""unterminated"#), None);
    }

    #[test]
    fn malformed_escape_falls_back_verbatim() {
        // `"bad\z"` — quotes at both ends so we attempt to decode, but
        // `\z` isn't a valid JSON escape → decoder returns `None` → the
        // outer helper falls back to the verbatim inner slice.
        assert_eq!(
            decode_js_string_literal(r#""bad\z""#).as_deref(),
            Some("bad\\z"),
        );
    }
}
