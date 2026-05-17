//! Output buffer. Single growable `Vec<u8>` per emit (R6).
//!
//! The buffer is allocated upfront with a capacity hint from the IR size
//! estimate (caller-supplied). Every `write_*` method appends raw bytes —
//! there are no per-node `format!` or `String::new()` allocations.

use std::fmt;

pub struct CodeBuffer {
    buf: Vec<u8>,
}

impl CodeBuffer {
    #[inline]
    pub fn new() -> Self {
        Self { buf: Vec::new() }
    }

    #[inline]
    pub fn with_capacity(cap: usize) -> Self {
        Self {
            buf: Vec::with_capacity(cap),
        }
    }

    #[inline(always)]
    pub fn write_byte(&mut self, b: u8) {
        self.buf.push(b);
    }

    #[inline(always)]
    pub fn write_bytes(&mut self, bytes: &[u8]) {
        self.buf.extend_from_slice(bytes);
    }

    #[inline(always)]
    pub fn write_str(&mut self, s: &str) {
        self.buf.extend_from_slice(s.as_bytes());
    }

    /// Emit a JS string literal with double quotes. Escapes the few JS-special
    /// characters; assumes input is otherwise already-encoded JS source.
    pub fn write_js_string(&mut self, s: &str) {
        self.buf.push(b'"');
        for &b in s.as_bytes() {
            match b {
                b'"' => self.buf.extend_from_slice(b"\\\""),
                b'\\' => self.buf.extend_from_slice(b"\\\\"),
                b'\n' => self.buf.extend_from_slice(b"\\n"),
                b'\r' => self.buf.extend_from_slice(b"\\r"),
                b'\t' => self.buf.extend_from_slice(b"\\t"),
                0x00..=0x1F => {
                    self.buf.extend_from_slice(b"\\u00");
                    self.buf.push(hex_nibble(b >> 4));
                    self.buf.push(hex_nibble(b & 0x0F));
                }
                _ => self.buf.push(b),
            }
        }
        self.buf.push(b'"');
    }

    /// Append a decimal integer.
    pub fn write_u64(&mut self, n: u64) {
        let mut tmp = itoa::Buffer::new();
        self.buf.extend_from_slice(tmp.format(n).as_bytes());
    }

    pub fn write_i64(&mut self, n: i64) {
        let mut tmp = itoa::Buffer::new();
        self.buf.extend_from_slice(tmp.format(n).as_bytes());
    }

    pub fn write_f64(&mut self, n: f64) {
        let mut tmp = ryu::Buffer::new();
        self.buf.extend_from_slice(tmp.format(n).as_bytes());
    }

    #[inline]
    pub fn len(&self) -> usize {
        self.buf.len()
    }

    #[inline]
    pub fn is_empty(&self) -> bool {
        self.buf.is_empty()
    }

    #[inline]
    pub fn as_bytes(&self) -> &[u8] {
        &self.buf
    }

    pub fn into_bytes(self) -> Vec<u8> {
        self.buf
    }

    pub fn as_str(&self) -> &str {
        // All `write_*` paths emit UTF-8 bytes (we accept `&str` inputs and
        // never split multi-byte sequences). If a caller writes raw bytes
        // that aren't valid UTF-8, this will panic — that's a programmer
        // error in codegen, not user input.
        std::str::from_utf8(&self.buf).expect("CodeBuffer must contain UTF-8")
    }
}

impl Default for CodeBuffer {
    fn default() -> Self {
        Self::new()
    }
}

impl fmt::Debug for CodeBuffer {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("CodeBuffer")
            .field("len", &self.buf.len())
            .finish()
    }
}

#[inline(always)]
fn hex_nibble(n: u8) -> u8 {
    match n {
        0..=9 => b'0' + n,
        10..=15 => b'a' + (n - 10),
        _ => unreachable!(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn writes_string_unescaped_when_safe() {
        let mut b = CodeBuffer::new();
        b.write_js_string("hello world");
        assert_eq!(b.as_str(), "\"hello world\"");
    }

    #[test]
    fn escapes_double_quotes() {
        let mut b = CodeBuffer::new();
        b.write_js_string(r#"say "hi""#);
        assert_eq!(b.as_str(), r#""say \"hi\"""#);
    }

    #[test]
    fn escapes_newlines() {
        let mut b = CodeBuffer::new();
        b.write_js_string("a\nb");
        assert_eq!(b.as_str(), r#""a\nb""#);
    }

    #[test]
    fn writes_decimal_int() {
        let mut b = CodeBuffer::new();
        b.write_u64(12345);
        assert_eq!(b.as_str(), "12345");
    }

    #[test]
    fn writes_negative_int() {
        let mut b = CodeBuffer::new();
        b.write_i64(-42);
        assert_eq!(b.as_str(), "-42");
    }
}
