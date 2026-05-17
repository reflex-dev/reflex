//! Context file emission: the JS shell that wraps the Python-computed
//! initial state JSON and client-storage config. See plan §4.3, D10.
//!
//! The shape (verbatim Reflex convention):
//!
//! ```js
//! import { createContext } from "react";
//!
//! export const StateContext = createContext(null);
//! export const ColorModeContext = createContext(null);
//!
//! export const initialState = <initial_state_json>;
//! export const clientStorage = <client_storage_json>;
//! export const computedVarDeps = {<var>: [<dep>, ...], ...};
//! ```
//!
//! State *values* come from Python (Pydantic + async resolution); Rust just
//! emits the JS shell that splices them in. Rust never inspects the JSON.

use reflex_intern::resolve_unchecked;
use reflex_ir::GlobalState;

use crate::buffer::CodeBuffer;

pub fn emit_context(buf: &mut CodeBuffer, state: &GlobalState<'_>) {
    buf.write_str("import { createContext } from \"react\";\n\n");
    buf.write_str("export const StateContext = createContext(null);\n");
    buf.write_str("export const ColorModeContext = createContext(null);\n\n");

    buf.write_str("export const initialState = ");
    write_json_blob(buf, state.initial_state_json);
    buf.write_str(";\n");

    buf.write_str("export const clientStorage = ");
    write_json_blob(buf, state.client_storage_json);
    buf.write_str(";\n");

    buf.write_str("export const computedVarDeps = {");
    for (i, dep) in state.computed_var_deps.iter().enumerate() {
        if i > 0 {
            buf.write_str(", ");
        }
        buf.write_js_string(resolve_unchecked(dep.var));
        buf.write_str(": [");
        for (j, depend) in dep.depends_on.iter().enumerate() {
            if j > 0 {
                buf.write_str(", ");
            }
            buf.write_js_string(resolve_unchecked(*depend));
        }
        buf.write_str("]");
    }
    buf.write_str("};\n");
}

/// Write a pre-encoded JSON blob. If the blob isn't valid UTF-8 we fall back
/// to `null` — that means the Python side shipped garbage, which is a
/// programmer error, but we don't want to crash the emit pipeline.
fn write_json_blob(buf: &mut CodeBuffer, blob: &[u8]) {
    match std::str::from_utf8(blob) {
        Ok(s) if !s.is_empty() => buf.write_str(s),
        _ => buf.write_str("null"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use reflex_ir::{ComputedVarDep, GlobalState};

    #[test]
    fn emits_basic_shell() {
        let state = GlobalState {
            schema_version: 1,
            initial_state_json: b"{\"count\": 0}",
            client_storage_json: b"{}",
            computed_var_deps: &[],
        };
        let mut buf = CodeBuffer::new();
        emit_context(&mut buf, &state);
        let s = buf.as_str();
        assert!(s.contains("import { createContext } from \"react\";"));
        assert!(s.contains("export const initialState = {\"count\": 0};"));
        assert!(s.contains("export const clientStorage = {};"));
        assert!(s.contains("export const computedVarDeps = {};"));
    }

    #[test]
    fn empty_json_emits_null() {
        let state = GlobalState {
            schema_version: 1,
            initial_state_json: b"",
            client_storage_json: b"",
            computed_var_deps: &[],
        };
        let mut buf = CodeBuffer::new();
        emit_context(&mut buf, &state);
        let s = buf.as_str();
        assert!(s.contains("export const initialState = null;"));
    }

    #[test]
    fn emits_computed_var_deps() {
        let dep = ComputedVarDep {
            var: reflex_intern::intern("total"),
            depends_on: &[reflex_intern::intern("a"), reflex_intern::intern("b")],
        };
        let state = GlobalState {
            schema_version: 1,
            initial_state_json: b"null",
            client_storage_json: b"null",
            computed_var_deps: std::slice::from_ref(&dep),
        };
        let mut buf = CodeBuffer::new();
        emit_context(&mut buf, &state);
        let s = buf.as_str();
        assert!(s.contains("\"total\": [\"a\", \"b\"]"));
    }
}
