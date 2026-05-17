//! Hand-rolled msgpack parser for the §4 wire format. See plan §3.4, D4, R1.
//!
//! Wire format is positional msgpack arrays. The parser borrows `&str`
//! directly from the input bytes where possible, copying into the arena only
//! when the lifetime must survive the input slice (e.g. ID strings stored in
//! VarData that the codegen will keep referencing). Spike measurement: 25×
//! faster than rmp-serde at 10k nodes.
//!
//! Schema versions:
//!   1 — current; per §4.1.
//!
//! Wire shapes (see RUST_REWRITE_PLAN.md §4 for the canonical definition):
//!
//! ```text
//! PageIR        = [v:u32, route:str, root:Component, title:str|nil,
//!                  meta:[Meta], source_files:[u32]]
//! Component     = [kind:u8, ...payload]   (payload depends on kind)
//!   Element(0)  = [0, tag:str, props:[[name:str, Value]], children:[Component],
//!                  events:[EventHandler], hooks:[Hook], id:u64, loc:[u32,u32,u32]]
//!   Text(1)     = [1, value:str, id:u64, loc]
//!   Foreach(2)  = [2, iter:Value, body:Component, id:u64, loc]
//!   Cond(3)     = [3, test:Value, then:Component, else:Component|nil, id:u64, loc]
//!   Match(4)    = [4, value:Value, arms:[MatchArm], default:Component|nil, id:u64, loc]
//!   Memoize(5)  = [5, inner:Component, key:u64, id:u64, loc]
//!   Fragment(6) = [6, children:[Component], id:u64, loc]
//!   Expr(7)     = [7, value:Value, id:u64, loc]
//! Value         = [kind:u8, ...payload]
//!   JsExpr(0)   = [0, expr:str, VarData]
//!   Literal(1)  = [1, Literal]
//!   Ref(2)      = [2, name:str]
//! Literal       = [kind:u8, ...payload]
//!   Null(0)     = [0]
//!   Bool(1)     = [1, bool]
//!   Int(2)      = [2, i64]
//!   Float(3)    = [3, f64]
//!   Str(4)      = [4, str]
//! VarData       = [hooks:[str], imports:[[module:str, name:str]],
//!                  state:str|nil, deps:[str], position:u8|nil, components:[str]]
//! EventHandler  = [trigger:str, expr:str, VarData]
//! Hook          = [code:str, deps:[str], position:u8]
//! MatchArm      = [case:Value, body:Component]
//! Meta          = [name:str, content:str]
//! SourceLoc     = [file_id:u32, line:u32, col:u32]
//! ```

use std::convert::TryFrom;

use reflex_arena::Arena;
use reflex_intern::{intern, Symbol};
use rmp::decode::{self, RmpRead};
use rmp::Marker;

use crate::{
    Component, ComputedVarDep, EventHandler, GlobalState, Hook, Literal, MatchArm, Meta, NodeId,
    Page, PluginEntry, PluginManifest, PyFileId, SourceLoc, Theme, Value, VarData,
};

pub const SCHEMA_VERSION: u32 = 2;

#[derive(Debug, thiserror::Error)]
pub enum ParseError {
    #[error("unsupported schema version {0}; this build accepts {SCHEMA_VERSION}")]
    UnsupportedVersion(u32),
    #[error("malformed msgpack: {0}")]
    Msgpack(String),
    #[error("invalid utf-8: {0}")]
    Utf8(#[from] std::str::Utf8Error),
    #[error("unknown component kind {0}")]
    UnknownComponentKind(u8),
    #[error("unknown value kind {0}")]
    UnknownValueKind(u8),
    #[error("unknown literal kind {0}")]
    UnknownLiteralKind(u8),
    #[error("expected array of length {expected}, got {actual}")]
    BadArrayLen { expected: u32, actual: u32 },
    #[error("integer overflow: {0}")]
    IntOverflow(&'static str),
}

type Result<T> = std::result::Result<T, ParseError>;

fn map_msgpack<E: std::fmt::Display>(e: E) -> ParseError {
    ParseError::Msgpack(e.to_string())
}

// ---- Primitive readers ------------------------------------------------------

#[inline]
fn read_array_len(buf: &mut &[u8]) -> Result<u32> {
    decode::read_array_len(buf).map_err(map_msgpack)
}

#[inline]
fn read_str_borrowed<'a>(buf: &mut &'a [u8]) -> Result<&'a str> {
    let len = decode::read_str_len(buf).map_err(map_msgpack)? as usize;
    if buf.len() < len {
        return Err(ParseError::Msgpack("short read on str".into()));
    }
    let (head, rest) = buf.split_at(len);
    *buf = rest;
    Ok(std::str::from_utf8(head)?)
}

#[inline]
fn read_bin_borrowed<'a>(buf: &mut &'a [u8]) -> Result<&'a [u8]> {
    let len = decode::read_bin_len(buf).map_err(map_msgpack)? as usize;
    if buf.len() < len {
        return Err(ParseError::Msgpack("short read on bin".into()));
    }
    let (head, rest) = buf.split_at(len);
    *buf = rest;
    Ok(head)
}

#[inline]
fn read_u32(buf: &mut &[u8]) -> Result<u32> {
    let n = decode::read_int::<i64, _>(buf).map_err(map_msgpack)?;
    u32::try_from(n).map_err(|_| ParseError::IntOverflow("u32"))
}

#[inline]
fn read_u64(buf: &mut &[u8]) -> Result<u64> {
    let raw: i128 = decode::read_int::<i128, _>(buf).map_err(map_msgpack)?;
    u64::try_from(raw).map_err(|_| ParseError::IntOverflow("u64"))
}

#[inline]
fn read_i64(buf: &mut &[u8]) -> Result<i64> {
    decode::read_int::<i64, _>(buf).map_err(map_msgpack)
}

#[inline]
fn read_f64(buf: &mut &[u8]) -> Result<f64> {
    decode::read_f64(buf).map_err(map_msgpack)
}

#[inline]
fn read_bool(buf: &mut &[u8]) -> Result<bool> {
    decode::read_bool(buf).map_err(map_msgpack)
}

#[inline]
fn read_u8(buf: &mut &[u8]) -> Result<u8> {
    buf.read_u8().map_err(map_msgpack)
}

/// Peek the next marker and consume it if it's `nil`. Returns `true` when nil
/// was consumed, `false` when the marker is something else (and the cursor is
/// unchanged).
#[inline]
fn try_read_nil(buf: &mut &[u8]) -> Result<bool> {
    if buf.is_empty() {
        return Err(ParseError::Msgpack("unexpected end while peeking nil".into()));
    }
    let m = Marker::from_u8(buf[0]);
    if matches!(m, Marker::Null) {
        *buf = &buf[1..];
        Ok(true)
    } else {
        Ok(false)
    }
}

#[inline]
fn read_str_or_nil_borrowed<'a>(buf: &mut &'a [u8]) -> Result<Option<&'a str>> {
    if try_read_nil(buf)? {
        Ok(None)
    } else {
        Ok(Some(read_str_borrowed(buf)?))
    }
}

#[inline]
fn read_u8_or_nil(buf: &mut &[u8]) -> Result<Option<u8>> {
    if try_read_nil(buf)? {
        Ok(None)
    } else {
        let n = decode::read_int::<u16, _>(buf).map_err(map_msgpack)?;
        u8::try_from(n)
            .map(Some)
            .map_err(|_| ParseError::IntOverflow("u8"))
    }
}

#[inline]
fn intern_str(s: &str) -> Symbol {
    intern(s)
}

// ---- Array-of-Symbol / array-of-strings / array-of-(Symbol,Symbol) ----------

#[inline]
fn read_symbol_array<'a>(arena: &'a Arena, buf: &mut &[u8]) -> Result<&'a [Symbol]> {
    let n = read_array_len(buf)? as usize;
    let mut tmp: bumpalo::collections::Vec<Symbol> =
        bumpalo::collections::Vec::with_capacity_in(n, arena.bump());
    for _ in 0..n {
        let s = read_str_borrowed(buf)?;
        tmp.push(intern_str(s));
    }
    Ok(tmp.into_bump_slice())
}

#[inline]
fn read_str_array_owned<'a>(arena: &'a Arena, buf: &mut &[u8]) -> Result<&'a [&'a str]> {
    let n = read_array_len(buf)? as usize;
    let mut tmp: bumpalo::collections::Vec<&'a str> =
        bumpalo::collections::Vec::with_capacity_in(n, arena.bump());
    for _ in 0..n {
        let s = read_str_borrowed(buf)?;
        tmp.push(arena.alloc_str(s));
    }
    Ok(tmp.into_bump_slice())
}

#[inline]
fn read_symbol_pair_array<'a>(
    arena: &'a Arena,
    buf: &mut &[u8],
) -> Result<&'a [(Symbol, Symbol)]> {
    let n = read_array_len(buf)? as usize;
    let mut tmp: bumpalo::collections::Vec<(Symbol, Symbol)> =
        bumpalo::collections::Vec::with_capacity_in(n, arena.bump());
    for _ in 0..n {
        let pair_len = read_array_len(buf)?;
        if pair_len != 2 {
            return Err(ParseError::BadArrayLen {
                expected: 2,
                actual: pair_len,
            });
        }
        let a = intern_str(read_str_borrowed(buf)?);
        let b = intern_str(read_str_borrowed(buf)?);
        tmp.push((a, b));
    }
    Ok(tmp.into_bump_slice())
}

// ---- Structured readers -----------------------------------------------------

fn read_source_loc(buf: &mut &[u8]) -> Result<SourceLoc> {
    let arr_len = read_array_len(buf)?;
    if arr_len != 3 {
        return Err(ParseError::BadArrayLen {
            expected: 3,
            actual: arr_len,
        });
    }
    let file = PyFileId(read_u32(buf)?);
    let line = read_u32(buf)?;
    let col = read_u32(buf)?;
    Ok(SourceLoc { file, line, col })
}

fn read_var_data<'a>(arena: &'a Arena, buf: &mut &[u8]) -> Result<VarData<'a>> {
    let arr_len = read_array_len(buf)?;
    if arr_len != 6 {
        return Err(ParseError::BadArrayLen {
            expected: 6,
            actual: arr_len,
        });
    }
    let hooks = read_str_array_owned(arena, buf)?;
    let imports = read_symbol_pair_array(arena, buf)?;
    let state = read_str_or_nil_borrowed(buf)?.map(intern_str);
    let deps = read_symbol_array(arena, buf)?;
    let position = read_u8_or_nil(buf)?;
    let components = read_symbol_array(arena, buf)?;
    Ok(VarData {
        hooks,
        imports,
        state,
        deps,
        position,
        components,
    })
}

fn read_literal<'a>(arena: &'a Arena, buf: &mut &[u8]) -> Result<Literal<'a>> {
    let arr_len = read_array_len(buf)?;
    let kind = read_u8(buf)?;
    match kind {
        0 => {
            if arr_len != 1 {
                return Err(ParseError::BadArrayLen {
                    expected: 1,
                    actual: arr_len,
                });
            }
            Ok(Literal::Null)
        }
        1 => {
            if arr_len != 2 {
                return Err(ParseError::BadArrayLen {
                    expected: 2,
                    actual: arr_len,
                });
            }
            Ok(Literal::Bool(read_bool(buf)?))
        }
        2 => {
            if arr_len != 2 {
                return Err(ParseError::BadArrayLen {
                    expected: 2,
                    actual: arr_len,
                });
            }
            Ok(Literal::Int(read_i64(buf)?))
        }
        3 => {
            if arr_len != 2 {
                return Err(ParseError::BadArrayLen {
                    expected: 2,
                    actual: arr_len,
                });
            }
            Ok(Literal::Float(read_f64(buf)?))
        }
        4 => {
            if arr_len != 2 {
                return Err(ParseError::BadArrayLen {
                    expected: 2,
                    actual: arr_len,
                });
            }
            let s = read_str_borrowed(buf)?;
            Ok(Literal::Str(arena.alloc_str(s)))
        }
        _ => Err(ParseError::UnknownLiteralKind(kind)),
    }
}

fn read_value<'a>(arena: &'a Arena, buf: &mut &[u8]) -> Result<Value<'a>> {
    let arr_len = read_array_len(buf)?;
    let kind = read_u8(buf)?;
    match kind {
        0 => {
            if arr_len != 3 {
                return Err(ParseError::BadArrayLen {
                    expected: 3,
                    actual: arr_len,
                });
            }
            let expr = arena.alloc_str(read_str_borrowed(buf)?);
            let var_data = read_var_data(arena, buf)?;
            Ok(Value::JsExpr { expr, var_data })
        }
        1 => {
            if arr_len != 2 {
                return Err(ParseError::BadArrayLen {
                    expected: 2,
                    actual: arr_len,
                });
            }
            Ok(Value::Literal(read_literal(arena, buf)?))
        }
        2 => {
            if arr_len != 2 {
                return Err(ParseError::BadArrayLen {
                    expected: 2,
                    actual: arr_len,
                });
            }
            Ok(Value::Ref(intern_str(read_str_borrowed(buf)?)))
        }
        _ => Err(ParseError::UnknownValueKind(kind)),
    }
}

fn read_event_handler<'a>(arena: &'a Arena, buf: &mut &[u8]) -> Result<EventHandler<'a>> {
    let arr_len = read_array_len(buf)?;
    if arr_len != 3 {
        return Err(ParseError::BadArrayLen {
            expected: 3,
            actual: arr_len,
        });
    }
    let trigger = intern_str(read_str_borrowed(buf)?);
    let expr = arena.alloc_str(read_str_borrowed(buf)?);
    let var_data = read_var_data(arena, buf)?;
    Ok(EventHandler {
        trigger,
        expr,
        var_data,
    })
}

fn read_hook<'a>(arena: &'a Arena, buf: &mut &[u8]) -> Result<Hook<'a>> {
    let arr_len = read_array_len(buf)?;
    if arr_len != 3 {
        return Err(ParseError::BadArrayLen {
            expected: 3,
            actual: arr_len,
        });
    }
    let code = arena.alloc_str(read_str_borrowed(buf)?);
    let deps = read_symbol_array(arena, buf)?;
    let n = decode::read_int::<u16, _>(buf).map_err(map_msgpack)?;
    let position = u8::try_from(n).map_err(|_| ParseError::IntOverflow("u8"))?;
    Ok(Hook {
        code,
        deps,
        position,
    })
}

fn read_match_arm<'a>(arena: &'a Arena, buf: &mut &[u8]) -> Result<MatchArm<'a>> {
    let arr_len = read_array_len(buf)?;
    if arr_len != 2 {
        return Err(ParseError::BadArrayLen {
            expected: 2,
            actual: arr_len,
        });
    }
    let case = read_value(arena, buf)?;
    let body = arena.alloc(read_component(arena, buf)?);
    Ok(MatchArm { case, body: &*body })
}

fn read_meta<'a>(arena: &'a Arena, buf: &mut &[u8]) -> Result<Meta<'a>> {
    let arr_len = read_array_len(buf)?;
    if arr_len != 2 {
        return Err(ParseError::BadArrayLen {
            expected: 2,
            actual: arr_len,
        });
    }
    let name = intern_str(read_str_borrowed(buf)?);
    let content = arena.alloc_str(read_str_borrowed(buf)?);
    Ok(Meta { name, content })
}

fn read_component<'a>(arena: &'a Arena, buf: &mut &[u8]) -> Result<Component<'a>> {
    let arr_len = read_array_len(buf)?;
    let kind = read_u8(buf)?;
    match kind {
        0 => {
            if arr_len != 8 {
                return Err(ParseError::BadArrayLen {
                    expected: 8,
                    actual: arr_len,
                });
            }
            let tag = intern_str(read_str_borrowed(buf)?);

            let n_props = read_array_len(buf)? as usize;
            let mut props: bumpalo::collections::Vec<(Symbol, Value<'a>)> =
                bumpalo::collections::Vec::with_capacity_in(n_props, arena.bump());
            for _ in 0..n_props {
                let pair_len = read_array_len(buf)?;
                if pair_len != 2 {
                    return Err(ParseError::BadArrayLen {
                        expected: 2,
                        actual: pair_len,
                    });
                }
                let name = intern_str(read_str_borrowed(buf)?);
                let value = read_value(arena, buf)?;
                props.push((name, value));
            }

            let n_children = read_array_len(buf)? as usize;
            let mut children: bumpalo::collections::Vec<Component<'a>> =
                bumpalo::collections::Vec::with_capacity_in(n_children, arena.bump());
            for _ in 0..n_children {
                children.push(read_component(arena, buf)?);
            }

            let n_events = read_array_len(buf)? as usize;
            let mut events: bumpalo::collections::Vec<EventHandler<'a>> =
                bumpalo::collections::Vec::with_capacity_in(n_events, arena.bump());
            for _ in 0..n_events {
                events.push(read_event_handler(arena, buf)?);
            }

            let n_hooks = read_array_len(buf)? as usize;
            let mut hooks: bumpalo::collections::Vec<Hook<'a>> =
                bumpalo::collections::Vec::with_capacity_in(n_hooks, arena.bump());
            for _ in 0..n_hooks {
                hooks.push(read_hook(arena, buf)?);
            }

            let id = NodeId(read_u64(buf)?);
            let source_loc = read_source_loc(buf)?;
            Ok(Component::Element {
                tag,
                props: props.into_bump_slice(),
                children: children.into_bump_slice(),
                event_handlers: events.into_bump_slice(),
                hooks: hooks.into_bump_slice(),
                id,
                source_loc,
            })
        }
        1 => {
            if arr_len != 4 {
                return Err(ParseError::BadArrayLen {
                    expected: 4,
                    actual: arr_len,
                });
            }
            let value = arena.alloc_str(read_str_borrowed(buf)?);
            let id = NodeId(read_u64(buf)?);
            let source_loc = read_source_loc(buf)?;
            Ok(Component::Text {
                value,
                id,
                source_loc,
            })
        }
        2 => {
            if arr_len != 5 {
                return Err(ParseError::BadArrayLen {
                    expected: 5,
                    actual: arr_len,
                });
            }
            let iter = read_value(arena, buf)?;
            let body = arena.alloc(read_component(arena, buf)?);
            let id = NodeId(read_u64(buf)?);
            let source_loc = read_source_loc(buf)?;
            Ok(Component::Foreach {
                iter,
                body: &*body,
                id,
                source_loc,
            })
        }
        3 => {
            if arr_len != 6 {
                return Err(ParseError::BadArrayLen {
                    expected: 6,
                    actual: arr_len,
                });
            }
            let test = read_value(arena, buf)?;
            let then = arena.alloc(read_component(arena, buf)?);
            let else_ = if try_read_nil(buf)? {
                None
            } else {
                Some(&*arena.alloc(read_component(arena, buf)?))
            };
            let id = NodeId(read_u64(buf)?);
            let source_loc = read_source_loc(buf)?;
            Ok(Component::Cond {
                test,
                then: &*then,
                else_,
                id,
                source_loc,
            })
        }
        4 => {
            if arr_len != 6 {
                return Err(ParseError::BadArrayLen {
                    expected: 6,
                    actual: arr_len,
                });
            }
            let value = read_value(arena, buf)?;
            let n_arms = read_array_len(buf)? as usize;
            let mut arms: bumpalo::collections::Vec<MatchArm<'a>> =
                bumpalo::collections::Vec::with_capacity_in(n_arms, arena.bump());
            for _ in 0..n_arms {
                arms.push(read_match_arm(arena, buf)?);
            }
            let default = if try_read_nil(buf)? {
                None
            } else {
                Some(&*arena.alloc(read_component(arena, buf)?))
            };
            let id = NodeId(read_u64(buf)?);
            let source_loc = read_source_loc(buf)?;
            Ok(Component::Match {
                value,
                arms: arms.into_bump_slice(),
                default,
                id,
                source_loc,
            })
        }
        5 => {
            if arr_len != 5 {
                return Err(ParseError::BadArrayLen {
                    expected: 5,
                    actual: arr_len,
                });
            }
            let inner = arena.alloc(read_component(arena, buf)?);
            let key = NodeId(read_u64(buf)?);
            let id = NodeId(read_u64(buf)?);
            let source_loc = read_source_loc(buf)?;
            Ok(Component::Memoize {
                inner: &*inner,
                key,
                id,
                source_loc,
            })
        }
        6 => {
            if arr_len != 4 {
                return Err(ParseError::BadArrayLen {
                    expected: 4,
                    actual: arr_len,
                });
            }
            let n_children = read_array_len(buf)? as usize;
            let mut children: bumpalo::collections::Vec<Component<'a>> =
                bumpalo::collections::Vec::with_capacity_in(n_children, arena.bump());
            for _ in 0..n_children {
                children.push(read_component(arena, buf)?);
            }
            let id = NodeId(read_u64(buf)?);
            let source_loc = read_source_loc(buf)?;
            Ok(Component::Fragment {
                children: children.into_bump_slice(),
                id,
                source_loc,
            })
        }
        7 => {
            if arr_len != 4 {
                return Err(ParseError::BadArrayLen {
                    expected: 4,
                    actual: arr_len,
                });
            }
            let value = read_value(arena, buf)?;
            let id = NodeId(read_u64(buf)?);
            let source_loc = read_source_loc(buf)?;
            Ok(Component::Expr {
                value,
                id,
                source_loc,
            })
        }
        _ => Err(ParseError::UnknownComponentKind(kind)),
    }
}

// ---- Public entry points ----------------------------------------------------

/// Parse a `PageIR` msgpack blob into an arena-allocated `Page<'a>`.
///
/// Wire format (v2 positional array):
///
/// ```text
/// [v=2, route, root, title|nil, meta, source_files,
///  component_imports, state_bindings, needs_ref]
/// ```
pub fn parse_page<'a>(arena: &'a Arena, bytes: &[u8]) -> Result<Page<'a>> {
    let mut buf: &[u8] = bytes;
    let arr_len = read_array_len(&mut buf)?;
    if arr_len != 9 {
        return Err(ParseError::BadArrayLen {
            expected: 9,
            actual: arr_len,
        });
    }
    let version = read_u32(&mut buf)?;
    if version != SCHEMA_VERSION {
        return Err(ParseError::UnsupportedVersion(version));
    }
    let route = arena.alloc_str(read_str_borrowed(&mut buf)?);
    let root = arena.alloc(read_component(arena, &mut buf)?);
    let title = match read_str_or_nil_borrowed(&mut buf)? {
        None => None,
        Some(s) => Some(&*arena.alloc_str(s)),
    };

    let n_meta = read_array_len(&mut buf)? as usize;
    let mut meta: bumpalo::collections::Vec<Meta<'a>> =
        bumpalo::collections::Vec::with_capacity_in(n_meta, arena.bump());
    for _ in 0..n_meta {
        meta.push(read_meta(arena, &mut buf)?);
    }

    let n_files = read_array_len(&mut buf)? as usize;
    let mut files: bumpalo::collections::Vec<PyFileId> =
        bumpalo::collections::Vec::with_capacity_in(n_files, arena.bump());
    for _ in 0..n_files {
        files.push(PyFileId(read_u32(&mut buf)?));
    }

    let component_imports = read_symbol_pair_array(arena, &mut buf)?;
    let state_bindings = read_symbol_array(arena, &mut buf)?;
    let needs_ref = read_bool(&mut buf)?;

    Ok(Page {
        schema_version: version,
        route,
        root: &*root,
        title,
        meta: meta.into_bump_slice(),
        source_files: files.into_bump_slice(),
        component_imports,
        state_bindings,
        needs_ref,
    })
}

// ---- Theme / GlobalState / PluginManifest parsers ---------------------------

pub fn parse_theme<'a>(arena: &'a Arena, bytes: &[u8]) -> Result<Theme<'a>> {
    let mut buf: &[u8] = bytes;
    let arr_len = read_array_len(&mut buf)?;
    if arr_len != 4 {
        return Err(ParseError::BadArrayLen {
            expected: 4,
            actual: arr_len,
        });
    }
    let version = read_u32(&mut buf)?;
    if version != SCHEMA_VERSION {
        return Err(ParseError::UnsupportedVersion(version));
    }
    let n_tokens = read_array_len(&mut buf)? as usize;
    let mut tokens: bumpalo::collections::Vec<(Symbol, &'a str)> =
        bumpalo::collections::Vec::with_capacity_in(n_tokens, arena.bump());
    for _ in 0..n_tokens {
        let pair_len = read_array_len(&mut buf)?;
        if pair_len != 2 {
            return Err(ParseError::BadArrayLen {
                expected: 2,
                actual: pair_len,
            });
        }
        let name = intern_str(read_str_borrowed(&mut buf)?);
        let value = arena.alloc_str(read_str_borrowed(&mut buf)?);
        tokens.push((name, value));
    }
    let global_style = arena.alloc_str(read_str_borrowed(&mut buf)?);
    let appearance = arena.alloc_str(read_str_borrowed(&mut buf)?);
    Ok(Theme {
        schema_version: version,
        tokens: tokens.into_bump_slice(),
        global_style,
        appearance,
    })
}

pub fn parse_global_state<'a>(arena: &'a Arena, bytes: &[u8]) -> Result<GlobalState<'a>> {
    let mut buf: &[u8] = bytes;
    let arr_len = read_array_len(&mut buf)?;
    if arr_len != 4 {
        return Err(ParseError::BadArrayLen {
            expected: 4,
            actual: arr_len,
        });
    }
    let version = read_u32(&mut buf)?;
    if version != SCHEMA_VERSION {
        return Err(ParseError::UnsupportedVersion(version));
    }
    let initial_state_json = arena.alloc_slice_copy(read_bin_borrowed(&mut buf)?);
    let client_storage_json = arena.alloc_slice_copy(read_bin_borrowed(&mut buf)?);
    let n_deps = read_array_len(&mut buf)? as usize;
    let mut deps: bumpalo::collections::Vec<ComputedVarDep<'a>> =
        bumpalo::collections::Vec::with_capacity_in(n_deps, arena.bump());
    for _ in 0..n_deps {
        let pair_len = read_array_len(&mut buf)?;
        if pair_len != 2 {
            return Err(ParseError::BadArrayLen {
                expected: 2,
                actual: pair_len,
            });
        }
        let var = intern_str(read_str_borrowed(&mut buf)?);
        let depends_on = read_symbol_array(arena, &mut buf)?;
        deps.push(ComputedVarDep { var, depends_on });
    }
    Ok(GlobalState {
        schema_version: version,
        initial_state_json: &*initial_state_json,
        client_storage_json: &*client_storage_json,
        computed_var_deps: deps.into_bump_slice(),
    })
}

pub fn parse_plugin_manifest<'a>(arena: &'a Arena, bytes: &[u8]) -> Result<PluginManifest<'a>> {
    let mut buf: &[u8] = bytes;
    let arr_len = read_array_len(&mut buf)?;
    if arr_len != 2 {
        return Err(ParseError::BadArrayLen {
            expected: 2,
            actual: arr_len,
        });
    }
    let version = read_u32(&mut buf)?;
    if version != SCHEMA_VERSION {
        return Err(ParseError::UnsupportedVersion(version));
    }
    let n_plugins = read_array_len(&mut buf)? as usize;
    let mut plugins: bumpalo::collections::Vec<PluginEntry<'a>> =
        bumpalo::collections::Vec::with_capacity_in(n_plugins, arena.bump());
    for _ in 0..n_plugins {
        let plug_len = read_array_len(&mut buf)?;
        if plug_len != 3 {
            return Err(ParseError::BadArrayLen {
                expected: 3,
                actual: plug_len,
            });
        }
        let name = intern_str(read_str_borrowed(&mut buf)?);
        let n_assets = read_array_len(&mut buf)? as usize;
        let mut assets: bumpalo::collections::Vec<(Symbol, &'a [u8])> =
            bumpalo::collections::Vec::with_capacity_in(n_assets, arena.bump());
        for _ in 0..n_assets {
            let asset_len = read_array_len(&mut buf)?;
            if asset_len != 2 {
                return Err(ParseError::BadArrayLen {
                    expected: 2,
                    actual: asset_len,
                });
            }
            let path = intern_str(read_str_borrowed(&mut buf)?);
            let body = arena.alloc_slice_copy(read_bin_borrowed(&mut buf)?);
            assets.push((path, &*body));
        }
        let stylesheet_imports = read_symbol_array(arena, &mut buf)?;
        plugins.push(PluginEntry {
            name,
            static_assets: assets.into_bump_slice(),
            stylesheet_imports,
        });
    }
    Ok(PluginManifest {
        schema_version: version,
        plugins: plugins.into_bump_slice(),
    })
}

// ---- Helpers for tests ------------------------------------------------------

#[doc(hidden)]
pub mod test_helpers {
    /// Build a minimal Page msgpack blob (v2): a single Element with one
    /// prop, one Text child, no component imports, no state bindings.
    pub fn tiny_page_bytes() -> Vec<u8> {
        use rmp::encode::*;
        let mut out = Vec::new();
        // PageIR v2 = [v, route, root, title|nil, meta, source_files,
        //              component_imports, state_bindings, needs_ref]
        write_array_len(&mut out, 9).unwrap();
        write_u32(&mut out, 2).unwrap();
        write_str(&mut out, "/index").unwrap();
        // Root: Element(0) = [0, tag, props, children, events, hooks, id, loc]
        write_array_len(&mut out, 8).unwrap();
        write_uint(&mut out, 0).unwrap();
        write_str(&mut out, "div").unwrap();
        // props: one prop ("id", JsExpr "x")
        write_array_len(&mut out, 1).unwrap();
        write_array_len(&mut out, 2).unwrap();
        write_str(&mut out, "id").unwrap();
        // Value JsExpr(0) = [0, expr, var_data]
        write_array_len(&mut out, 3).unwrap();
        write_uint(&mut out, 0).unwrap();
        write_str(&mut out, "x").unwrap();
        // VarData empty
        write_array_len(&mut out, 6).unwrap();
        write_array_len(&mut out, 0).unwrap(); // hooks
        write_array_len(&mut out, 0).unwrap(); // imports
        write_nil(&mut out).unwrap(); // state
        write_array_len(&mut out, 0).unwrap(); // deps
        write_nil(&mut out).unwrap(); // position
        write_array_len(&mut out, 0).unwrap(); // components
                                               // children: one Text
        write_array_len(&mut out, 1).unwrap();
        write_array_len(&mut out, 4).unwrap();
        write_uint(&mut out, 1).unwrap(); // kind=Text
        write_str(&mut out, "hello").unwrap();
        write_uint(&mut out, 42).unwrap(); // id
        write_array_len(&mut out, 3).unwrap();
        write_uint(&mut out, 0).unwrap();
        write_uint(&mut out, 0).unwrap();
        write_uint(&mut out, 0).unwrap();
        // events: empty
        write_array_len(&mut out, 0).unwrap();
        // hooks: empty
        write_array_len(&mut out, 0).unwrap();
        // id
        write_uint(&mut out, 7).unwrap();
        // loc
        write_array_len(&mut out, 3).unwrap();
        write_uint(&mut out, 0).unwrap();
        write_uint(&mut out, 0).unwrap();
        write_uint(&mut out, 0).unwrap();
        // title: nil
        write_nil(&mut out).unwrap();
        // meta: empty
        write_array_len(&mut out, 0).unwrap();
        // source_files: empty
        write_array_len(&mut out, 0).unwrap();
        // component_imports: empty
        write_array_len(&mut out, 0).unwrap();
        // state_bindings: empty
        write_array_len(&mut out, 0).unwrap();
        // needs_ref: false
        write_bool(&mut out, false).unwrap();
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::IrVisitor;

    #[test]
    fn parses_tiny_page() {
        let arena = Arena::new();
        let bytes = test_helpers::tiny_page_bytes();
        let page = parse_page(&arena, &bytes).expect("parse ok");
        assert_eq!(page.schema_version, SCHEMA_VERSION);
        assert_eq!(page.route, "/index");
        match page.root {
            Component::Element { tag, children, .. } => {
                assert_eq!(reflex_intern::resolve(*tag).unwrap(), "div");
                assert_eq!(children.len(), 1);
                match &children[0] {
                    Component::Text { value, id, .. } => {
                        assert_eq!(*value, "hello");
                        assert_eq!(id.0, 42);
                    }
                    _ => panic!("expected Text"),
                }
            }
            _ => panic!("expected Element"),
        }
    }

    #[test]
    fn rejects_wrong_version() {
        use rmp::encode::*;
        let arena = Arena::new();
        let mut bytes = Vec::new();
        write_array_len(&mut bytes, 9).unwrap();
        write_u32(&mut bytes, 9999).unwrap();
        let err = parse_page(&arena, &bytes).unwrap_err();
        assert!(matches!(err, ParseError::UnsupportedVersion(9999)));
    }

    #[test]
    fn visitor_walks_parsed_tree() {
        struct Counter(usize);
        impl<'a> IrVisitor<'a> for Counter {
            fn visit_component(&mut self, c: &Component<'a>) {
                self.0 += 1;
                crate::walk_component(self, c);
            }
        }
        let arena = Arena::new();
        let bytes = test_helpers::tiny_page_bytes();
        let page = parse_page(&arena, &bytes).unwrap();
        let mut c = Counter(0);
        c.visit_component(page.root);
        assert_eq!(c.0, 2);
    }
}
