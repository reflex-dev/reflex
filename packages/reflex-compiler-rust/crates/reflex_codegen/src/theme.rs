//! Theme CSS emission. See plan §4.2, D10.
//!
//! The Python theme (`ThemeIR`) ships a `(token_name, token_value)` table
//! plus a raw `global_style` CSS chunk and an `appearance` setting. We emit
//! a `:root { --token: value; ... }` block followed by the global CSS,
//! returning one self-contained stylesheet string.
//!
//! Token names are emitted as CSS custom properties: `tokenName` →
//! `--token-name`. Reflex's convention matches Emotion's output.

use reflex_intern::resolve_unchecked;
use reflex_ir::Theme;

use crate::buffer::CodeBuffer;

pub fn emit_theme(buf: &mut CodeBuffer, theme: &Theme<'_>) {
    if !theme.tokens.is_empty() {
        buf.write_str(":root {\n");
        for (name, value) in theme.tokens {
            buf.write_str("  --");
            write_kebab(buf, resolve_unchecked(*name));
            buf.write_str(": ");
            buf.write_str(value);
            buf.write_str(";\n");
        }
        buf.write_str("}\n\n");
    }

    if !theme.global_style.is_empty() {
        buf.write_str(theme.global_style);
        if !theme.global_style.ends_with('\n') {
            buf.write_byte(b'\n');
        }
    }
}

/// camelCase / snake_case → kebab-case for CSS custom property names.
fn write_kebab(buf: &mut CodeBuffer, name: &str) {
    let mut first = true;
    for &b in name.as_bytes() {
        match b {
            b'_' => {
                buf.write_byte(b'-');
                first = false;
            }
            b'A'..=b'Z' => {
                if !first {
                    buf.write_byte(b'-');
                }
                buf.write_byte(b.to_ascii_lowercase());
                first = false;
            }
            _ => {
                buf.write_byte(b);
                first = false;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use reflex_arena::Arena;
    use reflex_intern::intern;
    use reflex_ir::Theme;

    #[test]
    fn emits_tokens_and_global_css() {
        let arena = Arena::new();
        let tokens: Vec<(reflex_intern::Symbol, &str)> = vec![
            (intern("accentColor"), "#ff0080"),
            (intern("radiusMd"), "8px"),
        ];
        let theme = Theme {
            schema_version: 1,
            tokens: arena.bump().alloc_slice_copy(&tokens),
            global_style: "body { margin: 0; }",
            appearance: "light",
        };
        let mut buf = CodeBuffer::new();
        emit_theme(&mut buf, &theme);
        let s = buf.as_str();
        assert!(s.contains(":root {"));
        assert!(s.contains("--accent-color: #ff0080;"));
        assert!(s.contains("--radius-md: 8px;"));
        assert!(s.contains("body { margin: 0; }"));
    }

    #[test]
    fn empty_tokens_omit_root_block() {
        let theme = Theme {
            schema_version: 1,
            tokens: &[],
            global_style: "body { color: red; }",
            appearance: "light",
        };
        let mut buf = CodeBuffer::new();
        emit_theme(&mut buf, &theme);
        let s = buf.as_str();
        assert!(!s.contains(":root"));
        assert!(s.contains("body { color: red; }"));
    }

    #[test]
    fn empty_theme_emits_nothing() {
        let theme = Theme {
            schema_version: 1,
            tokens: &[],
            global_style: "",
            appearance: "light",
        };
        let mut buf = CodeBuffer::new();
        emit_theme(&mut buf, &theme);
        assert!(buf.is_empty());
    }
}
