//! JSX emission for the Component tree. See plan §4.8.
//!
//! `emit_component(buf, component)` writes one JS expression that, when
//! evaluated, produces the React element described by the IR node.
//!
//! Source-map variant: every entry point has a `_with_map` sibling that
//! records `(byte_offset → SourceLoc)` tuples for back-mapping diagnostics.

use reflex_intern::resolve_unchecked;
use reflex_ir::{Component, EventHandler, Literal, MatchArm, Value};

use crate::buffer::CodeBuffer;
use crate::sourcemap::SourceMap;

/// Emit one Component as a JS expression (no source-map recording).
#[inline]
pub fn emit_component<'a>(buf: &mut CodeBuffer, component: &Component<'a>) {
    emit_component_with_map(buf, component, None)
}

/// Emit one Component as a JS expression. If `map` is `Some`, records the
/// byte offset of this node and threads the recorder through children.
pub fn emit_component_with_map<'a>(
    buf: &mut CodeBuffer,
    component: &Component<'a>,
    map: Option<&mut SourceMap>,
) {
    let offset = buf.len() as u32;
    let loc = component.source_loc();
    match map {
        Some(map) => {
            map.record(offset, loc);
            emit_component_inner(buf, component, Some(map));
        }
        None => {
            emit_component_inner(buf, component, None);
        }
    }
}

fn emit_component_inner<'a>(
    buf: &mut CodeBuffer,
    component: &Component<'a>,
    map: Option<&mut SourceMap>,
) {
    match component {
        Component::Element {
            tag,
            props,
            children,
            event_handlers,
            ..
        } => emit_element(buf, *tag, props, children, event_handlers, map),
        Component::Text { value, .. } => buf.write_js_string(value),
        Component::Foreach { iter, body, .. } => emit_foreach(buf, iter, body, map),
        Component::Cond {
            test, then, else_, ..
        } => emit_cond(buf, test, then, *else_, map),
        Component::Match {
            value,
            arms,
            default,
            ..
        } => emit_match(buf, value, arms, *default, map),
        Component::Memoize { inner, key, .. } => emit_memoize(buf, inner, key.0, map),
        Component::Fragment { children, .. } => emit_fragment(buf, children, map),
        Component::Expr { value, .. } => emit_value(buf, value),
    }
}

fn emit_element<'a>(
    buf: &mut CodeBuffer,
    tag: reflex_intern::Symbol,
    props: &'a [(reflex_intern::Symbol, Value<'a>)],
    children: &'a [Component<'a>],
    event_handlers: &'a [EventHandler<'a>],
    mut map: Option<&mut SourceMap>,
) {
    buf.write_str("jsx(");
    buf.write_str(resolve_unchecked(tag));
    buf.write_str(", {");
    let mut first = true;
    for (name, value) in props {
        if !first {
            buf.write_str(", ");
        }
        first = false;
        emit_prop_name(buf, *name);
        buf.write_str(": ");
        emit_value(buf, value);
    }
    for handler in event_handlers {
        if !first {
            buf.write_str(", ");
        }
        first = false;
        emit_prop_name(buf, handler.trigger);
        buf.write_str(": ");
        buf.write_str(handler.expr);
    }
    buf.write_str("}");
    for child in children {
        buf.write_str(", ");
        emit_component_with_map(buf, child, map.as_deref_mut());
    }
    buf.write_str(")");
}

fn emit_fragment<'a>(
    buf: &mut CodeBuffer,
    children: &'a [Component<'a>],
    mut map: Option<&mut SourceMap>,
) {
    buf.write_str("jsx(Fragment, {}");
    for child in children {
        buf.write_str(", ");
        emit_component_with_map(buf, child, map.as_deref_mut());
    }
    buf.write_str(")");
}

fn emit_foreach<'a>(
    buf: &mut CodeBuffer,
    iter: &Value<'a>,
    body: &Component<'a>,
    map: Option<&mut SourceMap>,
) {
    buf.write_str("(");
    emit_value(buf, iter);
    buf.write_str(").map((item, index) => ");
    emit_component_with_map(buf, body, map);
    buf.write_str(")");
}

fn emit_cond<'a>(
    buf: &mut CodeBuffer,
    test: &Value<'a>,
    then: &Component<'a>,
    else_: Option<&Component<'a>>,
    mut map: Option<&mut SourceMap>,
) {
    buf.write_str("((");
    emit_value(buf, test);
    buf.write_str(") ? ");
    emit_component_with_map(buf, then, map.as_deref_mut());
    buf.write_str(" : ");
    if let Some(e) = else_ {
        emit_component_with_map(buf, e, map);
    } else {
        buf.write_str("null");
    }
    buf.write_str(")");
}

fn emit_match<'a>(
    buf: &mut CodeBuffer,
    value: &Value<'a>,
    arms: &'a [MatchArm<'a>],
    default: Option<&Component<'a>>,
    mut map: Option<&mut SourceMap>,
) {
    buf.write_str("match_template((");
    emit_value(buf, value);
    buf.write_str("), [");
    for (i, arm) in arms.iter().enumerate() {
        if i > 0 {
            buf.write_str(", ");
        }
        buf.write_str("[");
        emit_value(buf, &arm.case);
        buf.write_str(", ");
        emit_component_with_map(buf, arm.body, map.as_deref_mut());
        buf.write_str("]");
    }
    buf.write_str("], ");
    if let Some(d) = default {
        emit_component_with_map(buf, d, map);
    } else {
        buf.write_str("null");
    }
    buf.write_str(")");
}

fn emit_memoize<'a>(
    buf: &mut CodeBuffer,
    inner: &Component<'a>,
    key: u64,
    map: Option<&mut SourceMap>,
) {
    buf.write_str("jsx(MemoWrapper, {key: \"");
    buf.write_u64(key);
    buf.write_str("\"}, ");
    emit_component_with_map(buf, inner, map);
    buf.write_str(")");
}

pub fn emit_value<'a>(buf: &mut CodeBuffer, value: &Value<'a>) {
    match value {
        Value::JsExpr { expr, .. } => buf.write_str(expr),
        Value::Literal(lit) => emit_literal(buf, lit),
        Value::Ref(sym) => buf.write_str(resolve_unchecked(*sym)),
    }
}

fn emit_literal<'a>(buf: &mut CodeBuffer, lit: &Literal<'a>) {
    match lit {
        Literal::Null => buf.write_str("null"),
        Literal::Bool(true) => buf.write_str("true"),
        Literal::Bool(false) => buf.write_str("false"),
        Literal::Int(n) => buf.write_i64(*n),
        Literal::Float(f) => buf.write_f64(*f),
        Literal::Str(s) => buf.write_js_string(s),
    }
}

/// Prop names emit unquoted when they're valid JS identifiers; otherwise
/// they emit as quoted string keys. Known Python-side names (snake_case
/// HTML attributes, event triggers) are converted to camelCase so the
/// emitted JSX matches what React expects.
fn emit_prop_name(buf: &mut CodeBuffer, sym: reflex_intern::Symbol) {
    let name = resolve_unchecked(sym);
    // React props are camelCase. Reflex authors declare them in
    // snake_case (Python convention); the legacy emitter runs every
    // prop name through `to_camel_case`. Match that behaviour so
    // ``remark_plugins`` → ``remarkPlugins`` etc.
    if name.contains('_') && is_js_identifier(name) {
        write_camel_case(buf, name);
        return;
    }
    if is_js_identifier(name) {
        buf.write_str(name);
    } else {
        buf.write_js_string(name);
    }
}

/// Convert ``snake_case`` to ``camelCase``: lowercase the first segment
/// and Title-case the rest. Mirrors
/// :func:`reflex_base.utils.format.to_camel_case`. The legacy helper
/// treats hyphens as underscores by default — but JS identifiers can't
/// contain hyphens anyway, so `is_js_identifier` already excludes that
/// case and we only need to handle ``_``.
fn write_camel_case(buf: &mut CodeBuffer, name: &str) {
    let mut after_underscore = false;
    for (i, ch) in name.char_indices() {
        if ch == '_' {
            if i > 0 {
                after_underscore = true;
            }
            continue;
        }
        if after_underscore {
            // ASCII uppercase covers every JS-identifier byte we care
            // about; non-ASCII passes through unchanged.
            for upper in ch.to_uppercase() {
                let mut tmp = [0; 4];
                buf.write_str(upper.encode_utf8(&mut tmp));
            }
            after_underscore = false;
        } else {
            let mut tmp = [0; 4];
            buf.write_str(ch.encode_utf8(&mut tmp));
        }
    }
}

fn is_js_identifier(s: &str) -> bool {
    let bytes = s.as_bytes();
    if bytes.is_empty() {
        return false;
    }
    let first = bytes[0];
    if !(first.is_ascii_alphabetic() || first == b'_' || first == b'$') {
        return false;
    }
    for &b in &bytes[1..] {
        if !(b.is_ascii_alphanumeric() || b == b'_' || b == b'$') {
            return false;
        }
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use reflex_arena::Arena;
    use reflex_ir::{parse::test_helpers::tiny_page_bytes, parse_page};

    #[test]
    fn emits_tiny_page() {
        let arena = Arena::new();
        let bytes = tiny_page_bytes();
        let page = parse_page(&arena, &bytes).unwrap();
        let mut buf = CodeBuffer::new();
        emit_component(&mut buf, page.root);
        assert_eq!(buf.as_str(), "jsx(div, {id: x}, \"hello\")");
    }

    #[test]
    fn js_identifier_recognition() {
        assert!(is_js_identifier("foo"));
        assert!(is_js_identifier("_x"));
        assert!(is_js_identifier("$id"));
        assert!(is_js_identifier("aria1"));
        assert!(!is_js_identifier(""));
        assert!(!is_js_identifier("1foo"));
        assert!(!is_js_identifier("aria-label"));
        assert!(!is_js_identifier("foo bar"));
    }

    #[test]
    fn map_recording_is_a_noop_for_synthetic_locs() {
        // The tiny page's nodes all use SourceLoc::SYNTHETIC, so the map
        // stays empty even with `Some(&mut map)`.
        let arena = Arena::new();
        let bytes = tiny_page_bytes();
        let page = parse_page(&arena, &bytes).unwrap();
        let mut buf = CodeBuffer::new();
        let mut map = SourceMap::new();
        emit_component_with_map(&mut buf, page.root, Some(&mut map));
        assert!(map.is_empty());
    }
}
