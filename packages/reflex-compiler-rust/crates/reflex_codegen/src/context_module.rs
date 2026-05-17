//! Port of `context_template` —
//! `packages/reflex-base/src/reflex_base/compiler/templates.py`.
//!
//! The legacy template takes the resolved state hierarchy + client-
//! storage config and emits the full `utils/context.js` module. We
//! port the static template assembly to Rust; the dynamic inputs
//! (initial-state JSON, client-storage JSON, default-color-mode JS
//! literal) are pre-serialized by the Python caller and spliced in
//! verbatim.
//!
//! Streams output through a `Write` so the PyO3 binding can drive a
//! `BufWriter<File>` and skip any intermediate `String` allocation.

use std::io::{self, Write};

/// Hardcoded constants from
/// `reflex_base.constants.compiler.CompileVars`. They're
/// implementation-defined and never change at runtime, so we keep them
/// in Rust instead of marshalling them across PyO3 every call.
const FRONTEND_EXCEPTION_STATE_FULL: &str =
    "reflex___state____state.reflex___state____frontend_event_exception_state";
const UPDATE_VARS_INTERNAL: &str =
    "reflex___state____update_vars_internal_state.update_vars_internal";
const ON_LOAD_INTERNAL: &str = "reflex___state____on_load_internal_state.on_load_internal";
const HYDRATE: &str = "hydrate";

/// Emit `.web/utils/context.js`.
///
/// Args:
///     is_dev_mode: emitted as `isDevMode = <bool>`.
///     default_color_mode_js: JS expression for the default color mode
///         — the legacy emitter passes either a quoted string like
///         `"system"` or the literal `"system"`, depending on app
///         config. Passed verbatim.
///     state_name: the root state's full dotted name (e.g.
///         `reflex___state____state`). `None` produces the no-state
///         fallback (`onLoadInternalEvent = () => []`).
///     state_keys: the state names whose contexts and stores we wire up.
///         Each gets `replace('.', '__')` applied for its JS identifier.
///     initial_state_json: the JSON-serialized initial state dict,
///         already produced by the Python caller via `json_dumps`.
///         If `state_keys` is empty this is normally `"{}"`.
///     client_storage_json: the JSON-serialized client storage config,
///         already produced by `json.dumps` (or `"{}"` if `None`).
///     w: byte sink.
pub fn emit_context_module<W: Write>(
    is_dev_mode: bool,
    default_color_mode_js: &str,
    state_name: Option<&str>,
    state_keys: &[&str],
    initial_state_json: &str,
    client_storage_json: &str,
    w: &mut W,
) -> io::Result<()> {
    // Header — imports + top-level constants.
    w.write_all(
        b"import { createContext, useContext, useMemo, useReducer, useState, createElement, useEffect } from \"react\"\n",
    )?;
    w.write_all(
        b"import { applyDelta, ReflexEvent, hydrateClientStorage, useEventLoop, refs } from \"$/utils/state\"\n",
    )?;
    w.write_all(b"import { jsx } from \"@emotion/react\";\n\n")?;

    // `export const initialState = { … }` — pre-serialized by Python.
    w.write_all(b"export const initialState = ")?;
    w.write_all(initial_state_json.as_bytes())?;
    w.write_all(b"\n\n")?;

    w.write_all(b"export const defaultColorMode = ")?;
    w.write_all(default_color_mode_js.as_bytes())?;
    w.write_all(
        b"\nexport const ColorModeContext = createContext({\n  \
              colorMode: defaultColorMode,\n  \
              resolvedColorMode: defaultColorMode === \"dark\" ? \"dark\" : \"light\",\n  \
              toggleColorMode: () => {},\n  \
              setColorMode: () => {},\n\
            });\n",
    )?;
    w.write_all(b"export const UploadFilesContext = createContext(null);\n")?;
    w.write_all(b"export const DispatchContext = createContext(null);\n")?;

    // `StateContexts = { foo: createContext(null), bar: ... };` —
    // concatenated with NO separator (matches the legacy template's
    // ''.join with each entry ending in ',').
    w.write_all(b"export const StateContexts = {")?;
    for key in state_keys {
        write_formatted_state_name(w, key)?;
        w.write_all(b": createContext(null),")?;
    }
    w.write_all(b"};\n")?;

    w.write_all(b"export const EventLoopContext = createContext(null);\n")?;
    w.write_all(b"export const clientStorage = ")?;
    w.write_all(client_storage_json.as_bytes())?;
    w.write_all(b"\n\n")?;

    // State block: either the rich version when a state root exists, or
    // a no-op fallback. Mirrors the conditional in the legacy template.
    match state_name {
        Some(sn) => emit_state_block_with_state(w, sn)?,
        None => emit_state_block_no_state(w)?,
    }
    // Legacy template puts an empty line between the state block (which
    // already ends with `\n    `) and the next `export`. That collapses
    // to `\n\n` after substitution.
    w.write_all(b"\n\n")?;

    w.write_all(b"export const isDevMode = ")?;
    w.write_all(if is_dev_mode { b"true" } else { b"false" })?;
    w.write_all(b";\n\n")?;

    // Trailing static helpers — providers + ClientSide wrapper.
    w.write_all(STATIC_PROVIDERS_PRELUDE)?;

    // `StateProvider` body — useReducer per state, dispatchers,
    // nested createElement scaffolding. Empty state_keys produces the
    // legacy empty-string output (the `\n`.join over an empty list).
    w.write_all(b"export function StateProvider({ children }) {\n  ")?;
    let mut first_store = true;
    for key in state_keys {
        if !first_store {
            w.write_all(b"\n")?;
        }
        first_store = false;
        w.write_all(b"const [")?;
        write_formatted_state_name(w, key)?;
        w.write_all(b", dispatch_")?;
        write_formatted_state_name(w, key)?;
        w.write_all(b"] = useReducer(applyDelta, initialState[\"")?;
        w.write_all(key.as_bytes())?;
        w.write_all(b"\"])")?;
    }
    w.write_all(b"\n  const dispatchers = useMemo(() => {\n    return {\n      ")?;
    let mut first_disp = true;
    for key in state_keys {
        if !first_disp {
            w.write_all(b"\n")?;
        }
        first_disp = false;
        w.write_all(b"\"")?;
        w.write_all(key.as_bytes())?;
        w.write_all(b"\": dispatch_")?;
        write_formatted_state_name(w, key)?;
        w.write_all(b",")?;
    }
    w.write_all(b"\n    }\n  }, [])\n\n  return (\n    ")?;

    let mut first_ctx = true;
    for key in state_keys {
        if !first_ctx {
            w.write_all(b"\n")?;
        }
        first_ctx = false;
        w.write_all(b"createElement(StateContexts.")?;
        write_formatted_state_name(w, key)?;
        w.write_all(b",{value: ")?;
        write_formatted_state_name(w, key)?;
        w.write_all(b"},")?;
    }
    w.write_all(b"\n    createElement(DispatchContext, {value: dispatchers}, children)\n    ")?;
    for _ in 0..state_keys.len() {
        w.write_all(b")")?;
    }
    w.write_all(b"\n  )\n}")?;
    Ok(())
}

/// Write a state name with dots replaced by double-underscore so it's
/// a valid JS identifier (matching `format_state_name` in
/// `reflex_base.utils.format`).
fn write_formatted_state_name<W: Write>(w: &mut W, name: &str) -> io::Result<()> {
    // Hot path: search for a dot before doing per-byte work.
    if !name.contains('.') {
        return w.write_all(name.as_bytes());
    }
    for b in name.bytes() {
        if b == b'.' {
            w.write_all(b"__")?;
        } else {
            w.write_all(std::slice::from_ref(&b))?;
        }
    }
    Ok(())
}

/// Emit the rich state block — populated when the app has a state root.
fn emit_state_block_with_state<W: Write>(w: &mut W, state_name: &str) -> io::Result<()> {
    w.write_all(b"\nexport const state_name = \"")?;
    w.write_all(state_name.as_bytes())?;
    w.write_all(b"\"\n\nexport const exception_state_name = \"")?;
    w.write_all(FRONTEND_EXCEPTION_STATE_FULL.as_bytes())?;
    w.write_all(b"\"\n\n")?;
    w.write_all(b"// These events are triggered on initial load and each page navigation.\n")?;
    w.write_all(b"export const onLoadInternalEvent = () => {\n")?;
    w.write_all(b"    const internal_events = [];\n\n")?;
    w.write_all(b"    // Get tracked cookie and local storage vars to send to the backend.\n")?;
    w.write_all(b"    const client_storage_vars = hydrateClientStorage(clientStorage);\n")?;
    w.write_all(b"    // But only send the vars if any are actually set in the browser.\n")?;
    w.write_all(b"    if (client_storage_vars && Object.keys(client_storage_vars).length !== 0) {\n")?;
    w.write_all(b"        internal_events.push(\n")?;
    w.write_all(b"            ReflexEvent(\n")?;
    w.write_all(b"                '")?;
    w.write_all(state_name.as_bytes())?;
    w.write_all(b".")?;
    w.write_all(UPDATE_VARS_INTERNAL.as_bytes())?;
    w.write_all(b"',\n")?;
    w.write_all(b"                {vars: client_storage_vars},\n")?;
    w.write_all(b"            ),\n")?;
    w.write_all(b"        );\n    }\n\n")?;
    w.write_all(b"    // `on_load_internal` triggers the correct on_load event(s) for the current page.\n")?;
    w.write_all(b"    // If the page does not define any on_load event, this will just set `is_hydrated = true`.\n")?;
    w.write_all(b"    internal_events.push(ReflexEvent('")?;
    w.write_all(state_name.as_bytes())?;
    w.write_all(b".")?;
    w.write_all(ON_LOAD_INTERNAL.as_bytes())?;
    w.write_all(b"'));\n\n    return internal_events;\n}\n\n")?;
    w.write_all(b"// The following events are sent when the websocket connects or reconnects.\n")?;
    w.write_all(b"export const initialEvents = () => [\n    ReflexEvent('")?;
    w.write_all(state_name.as_bytes())?;
    w.write_all(b".")?;
    w.write_all(HYDRATE.as_bytes())?;
    w.write_all(b"'),\n    ...onLoadInternalEvent()\n]\n    ")?;
    Ok(())
}

/// Emit the no-state fallback block.
fn emit_state_block_no_state<W: Write>(w: &mut W) -> io::Result<()> {
    w.write_all(
        b"\nexport const state_name = undefined\n\n\
          export const exception_state_name = undefined\n\n\
          export const onLoadInternalEvent = () => []\n\n\
          export const initialEvents = () => []\n",
    )
}

const STATIC_PROVIDERS_PRELUDE: &[u8] = b"export function UploadFilesProvider({ children }) {\n  \
const [filesById, setFilesById] = useState({})\n  \
refs[\"__clear_selected_files\"] = (id) => setFilesById(filesById => {\n    \
const newFilesById = {...filesById}\n    \
delete newFilesById[id]\n    \
return newFilesById\n  })\n  \
return createElement(\n    \
UploadFilesContext.Provider,\n    \
{ value: [filesById, setFilesById] },\n    \
children\n  );\n}\n\n\
export function ClientSide(component) {\n  \
return ({ children, ...props }) => {\n    \
const [Component, setComponent] = useState(null);\n    \
useEffect(() => {\n      \
async function load() {\n        \
const comp = await component();\n        \
setComponent(() => comp);\n      }\n      \
load();\n    }, []);\n    \
return Component ? jsx(Component, props, children) : null;\n  };\n}\n\n\
export function EventLoopProvider({ children }) {\n  \
const dispatch = useContext(DispatchContext)\n  \
const [addEvents, connectErrors] = useEventLoop(\n    \
dispatch,\n    \
initialEvents,\n    \
clientStorage,\n  )\n  \
return createElement(\n    \
EventLoopContext.Provider,\n    \
{ value: [addEvents, connectErrors] },\n    \
children\n  );\n}\n\n";

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
    fn format_state_name_replaces_dots() {
        let s = render(|w| write_formatted_state_name(w, "foo.bar.baz"));
        assert_eq!(s, "foo__bar__baz");
    }

    #[test]
    fn format_state_name_passthrough_when_no_dot() {
        let s = render(|w| write_formatted_state_name(w, "foo"));
        assert_eq!(s, "foo");
    }

    #[test]
    fn no_state_block_emits_undefined_fallbacks() {
        let s = render(|w| {
            emit_context_module(false, "\"system\"", None, &[], "{}", "{}", w)
        });
        assert!(s.contains("export const state_name = undefined"));
        assert!(s.contains("export const initialEvents = () => []"));
        assert!(s.contains("export const StateContexts = {};"));
    }

    #[test]
    fn with_state_emits_hydrate_event_path() {
        let s = render(|w| {
            emit_context_module(
                true,
                "\"system\"",
                Some("reflex___state____state"),
                &["reflex___state____state"],
                "{}",
                "{}",
                w,
            )
        });
        assert!(s.contains("export const isDevMode = true;"));
        assert!(
            s.contains("ReflexEvent('reflex___state____state.hydrate')"),
            "hydrate event missing:\n{s}"
        );
        assert!(
            s.contains("StateContexts.reflex___state____state"),
            "state context missing:\n{s}"
        );
    }
}
