//! IR enum types. See plan §3.2, §4.
//!
//! Every variant is `Copy`. Slices and string refs borrow the arena (`'a`).
//! Public field access is allowed within the workspace; the plan's R4
//! corollary (Salsa-tracked accessors) wraps these reads in `reflex_db`, but
//! the underlying enum has to be matchable for the visitor pattern in `D6`.
//!
//! Wire-format compatibility: enum discriminants are explicitly assigned so
//! the msgpack parser in `reflex_py` can read a `u8` kind byte and `match`
//! straight into a constructor without lookup tables.

#![forbid(unsafe_code)]

use reflex_intern::Symbol;

pub mod parse;
pub mod visitor;

pub use parse::{parse_global_state, parse_page, parse_plugin_manifest, parse_theme, ParseError};
pub use visitor::{walk_component, walk_event_handler, walk_match_arm, walk_page, walk_value, IrVisitor};

/// Stable hash of a node's canonical bytes. Used as the Salsa cache key and as
/// the React `key=` value for memoized subtrees.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Default)]
pub struct NodeId(pub u64);

/// Per-`CompilerSession` interned Python source file. Survives revisions.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Default)]
pub struct PyFileId(pub u32);

/// Source location for diagnostics. `line` and `col` are 1-based; `(0, 0)`
/// means "synthetic / no source location" (e.g. generated Fragment wrappers).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct SourceLoc {
    pub file: PyFileId,
    pub line: u32,
    pub col: u32,
}

impl SourceLoc {
    pub const SYNTHETIC: SourceLoc = SourceLoc {
        file: PyFileId(0),
        line: 0,
        col: 0,
    };
}

/// VarData carries the hidden state that travels with a JS expression so the
/// IR consumer can hoist imports, register hooks, and order computed-var
/// dependencies. Strings live in the arena.
#[derive(Clone, Copy, Debug)]
pub struct VarData<'a> {
    /// Hook source fragments this expression depends on (raw JS strings).
    pub hooks: &'a [&'a str],
    /// `(module, name)` imports this expression requires.
    pub imports: &'a [(Symbol, Symbol)],
    /// Owning state class name, if any (`State`, `MySubState`, …).
    pub state: Option<Symbol>,
    /// Vars this var depends on (interned `_js_expr` strings).
    pub deps: &'a [Symbol],
    /// Position hint for hoisting (`None` = no constraint, else 0-based).
    pub position: Option<u8>,
    /// Component memoization wrappers this expression needs at hoist time.
    pub components: &'a [Symbol],
}

impl<'a> VarData<'a> {
    pub const EMPTY: VarData<'static> = VarData {
        hooks: &[],
        imports: &[],
        state: None,
        deps: &[],
        position: None,
        components: &[],
    };
}

/// A JS-expressible value embedded in IR. `JsExpr` is the dominant case —
/// Python pre-bakes the JS source and ships it along with VarData.
#[derive(Clone, Copy, Debug)]
pub enum Value<'a> {
    /// Pre-baked JS source string + the metadata needed to hoist its
    /// imports/hooks. The string is the literal text spliced into JSX.
    JsExpr {
        expr: &'a str,
        var_data: VarData<'a>,
    },
    /// Compile-time literal (no JS evaluation needed at render time).
    Literal(Literal<'a>),
    /// Reference to another named symbol (e.g. a state class identifier).
    Ref(Symbol),
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Literal<'a> {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    /// Already-JSON-quoted string (the Python emitter handled escaping).
    Str(&'a str),
}

/// A single `onClick`-style binding.
#[derive(Clone, Copy, Debug)]
pub struct EventHandler<'a> {
    /// Event trigger name (`"on_click"`, `"on_change"`, …).
    pub trigger: Symbol,
    /// JS expression bound to the trigger.
    pub expr: &'a str,
    pub var_data: VarData<'a>,
}

/// A React-hook fragment hoisted to the top of the page render function.
#[derive(Clone, Copy, Debug)]
pub struct Hook<'a> {
    /// Raw JS source for the hook body.
    pub code: &'a str,
    /// Vars this hook depends on (for ordering).
    pub deps: &'a [Symbol],
    /// Position bucket (`0` = useState/useEffect setup, `1` = derived, …).
    pub position: u8,
}

/// A single `rx.match(...)` arm.
#[derive(Clone, Copy, Debug)]
pub struct MatchArm<'a> {
    pub case: Value<'a>,
    pub body: &'a Component<'a>,
}

/// The Component IR tree.
///
/// `#[repr(C, u8)]` pins the discriminant to a `u8` and gives the layout a
/// stable shape so the Salsa cache and msgpack decoder can rely on it. The
/// remaining payload is laid out C-style, which trades a small amount of
/// padding for predictable pointer-stride into slices of `Component`.
#[repr(C, u8)]
#[derive(Clone, Copy, Debug)]
pub enum Component<'a> {
    Element {
        tag: Symbol,
        props: &'a [(Symbol, Value<'a>)],
        children: &'a [Component<'a>],
        event_handlers: &'a [EventHandler<'a>],
        hooks: &'a [Hook<'a>],
        id: NodeId,
        source_loc: SourceLoc,
    } = 0,
    Text {
        value: &'a str,
        id: NodeId,
        source_loc: SourceLoc,
    } = 1,
    Foreach {
        iter: Value<'a>,
        body: &'a Component<'a>,
        id: NodeId,
        source_loc: SourceLoc,
    } = 2,
    Cond {
        test: Value<'a>,
        then: &'a Component<'a>,
        else_: Option<&'a Component<'a>>,
        id: NodeId,
        source_loc: SourceLoc,
    } = 3,
    Match {
        value: Value<'a>,
        arms: &'a [MatchArm<'a>],
        default: Option<&'a Component<'a>>,
        id: NodeId,
        source_loc: SourceLoc,
    } = 4,
    Memoize {
        inner: &'a Component<'a>,
        key: NodeId,
        id: NodeId,
        source_loc: SourceLoc,
    } = 5,
    Fragment {
        children: &'a [Component<'a>],
        id: NodeId,
        source_loc: SourceLoc,
    } = 6,
    /// JSX value inline (e.g. `{state.title}`) — emits as a single expression
    /// with no surrounding tag. Distinct from `Text`, which double-quotes.
    Expr {
        value: Value<'a>,
        id: NodeId,
        source_loc: SourceLoc,
    } = 7,
}

impl<'a> Component<'a> {
    #[inline]
    pub fn id(&self) -> NodeId {
        match self {
            Component::Element { id, .. }
            | Component::Text { id, .. }
            | Component::Foreach { id, .. }
            | Component::Cond { id, .. }
            | Component::Match { id, .. }
            | Component::Memoize { id, .. }
            | Component::Fragment { id, .. }
            | Component::Expr { id, .. } => *id,
        }
    }

    #[inline]
    pub fn source_loc(&self) -> SourceLoc {
        match self {
            Component::Element { source_loc, .. }
            | Component::Text { source_loc, .. }
            | Component::Foreach { source_loc, .. }
            | Component::Cond { source_loc, .. }
            | Component::Match { source_loc, .. }
            | Component::Memoize { source_loc, .. }
            | Component::Fragment { source_loc, .. }
            | Component::Expr { source_loc, .. } => *source_loc,
        }
    }

    /// Wire-format discriminant. Matches the `kind` field in the msgpack
    /// schema (§4.1).
    #[inline]
    pub fn kind(&self) -> u8 {
        match self {
            Component::Element { .. } => 0,
            Component::Text { .. } => 1,
            Component::Foreach { .. } => 2,
            Component::Cond { .. } => 3,
            Component::Match { .. } => 4,
            Component::Memoize { .. } => 5,
            Component::Fragment { .. } => 6,
            Component::Expr { .. } => 7,
        }
    }
}

/// Top-level page IR. The unit of Salsa input granularity (§3.3 / D5).
///
/// **Schema v2 additions** (`component_imports`, `state_bindings`,
/// `needs_ref`): the Reflex React runtime expects the page module to
/// import its component classes, wire `useContext(StateContexts.*)` for
/// each state class used by the page, and (for any element with an `id`
/// prop) wire `useRef`. The bridge harvests these from the Component
/// tree; the Rust codegen emits the corresponding boilerplate.
#[derive(Clone, Copy, Debug)]
pub struct Page<'a> {
    /// Wire schema version (`PageIR.v`).
    pub schema_version: u32,
    pub route: &'a str,
    pub root: &'a Component<'a>,
    pub title: Option<&'a str>,
    pub meta: &'a [Meta<'a>],
    /// Python source files this page depends on (drives source-map back-mapping).
    pub source_files: &'a [PyFileId],
    /// Component-class imports required at module scope:
    /// `import { <name_in_module> as <local_alias> } from "<module>";`.
    /// Encoded as `(module, alias)` pairs where `module` is the JS module
    /// specifier and `alias` is the component identifier used inside JSX.
    pub component_imports: &'a [(Symbol, Symbol)],
    /// State-context identifiers needed via
    /// `useContext(StateContexts.<binding>)`. Each one becomes a `const`
    /// binding at the top of the render function.
    pub state_bindings: &'a [Symbol],
    /// Whether the page references any `id` prop, requiring a `useRef`
    /// setup at the top of the render function.
    pub needs_ref: bool,
}

#[derive(Clone, Copy, Debug)]
pub struct Meta<'a> {
    pub name: Symbol,
    pub content: &'a str,
}

/// Theme IR (§4.2).
#[derive(Clone, Copy, Debug)]
pub struct Theme<'a> {
    pub schema_version: u32,
    pub tokens: &'a [(Symbol, &'a str)],
    pub global_style: &'a str,
    pub appearance: &'a str,
}

/// GlobalState IR (§4.3).
///
/// `initial_state` and `client_storage` are kept as raw msgpack-encoded blobs
/// because their shape is recursive `Any` — Rust never inspects them; it
/// just splices them into the emitted JS shell as JSON literals.
#[derive(Clone, Copy, Debug)]
pub struct GlobalState<'a> {
    pub schema_version: u32,
    /// Pre-JSON-encoded initial state.
    pub initial_state_json: &'a [u8],
    /// Pre-JSON-encoded client storage config.
    pub client_storage_json: &'a [u8],
    pub computed_var_deps: &'a [ComputedVarDep<'a>],
}

#[derive(Clone, Copy, Debug)]
pub struct ComputedVarDep<'a> {
    pub var: Symbol,
    pub depends_on: &'a [Symbol],
}

/// Manifest of installed plugins. The plugin protocol is three-phase (§4.7);
/// the manifest is all Rust ever sees — actual `pre_compile`/`enter_leave`/
/// `post_build` code stays in Python.
#[derive(Clone, Copy, Debug)]
pub struct PluginManifest<'a> {
    pub schema_version: u32,
    pub plugins: &'a [PluginEntry<'a>],
}

#[derive(Clone, Copy, Debug)]
pub struct PluginEntry<'a> {
    pub name: Symbol,
    pub static_assets: &'a [(Symbol, &'a [u8])],
    pub stylesheet_imports: &'a [Symbol],
}

#[cfg(test)]
mod tests {
    use super::*;

    fn assert_copy<T: Copy>() {}
    fn assert_no_drop<T>() {
        assert!(!std::mem::needs_drop::<T>());
    }

    #[test]
    fn component_is_copy() {
        assert_copy::<Component<'_>>();
        assert_copy::<Value<'_>>();
        assert_copy::<EventHandler<'_>>();
        assert_copy::<Hook<'_>>();
        assert_copy::<VarData<'_>>();
        assert_copy::<MatchArm<'_>>();
        assert_copy::<Page<'_>>();
        assert_copy::<Theme<'_>>();
        assert_copy::<GlobalState<'_>>();
        assert_copy::<PluginManifest<'_>>();
    }

    #[test]
    fn r2_no_drop() {
        assert_no_drop::<Component<'_>>();
        assert_no_drop::<Value<'_>>();
        assert_no_drop::<EventHandler<'_>>();
        assert_no_drop::<Hook<'_>>();
        assert_no_drop::<VarData<'_>>();
        assert_no_drop::<MatchArm<'_>>();
        assert_no_drop::<Page<'_>>();
    }

    #[test]
    fn component_kind_matches_discriminant() {
        let id = NodeId(0);
        let loc = SourceLoc::SYNTHETIC;
        let text = Component::Text { value: "hi", id, source_loc: loc };
        let frag = Component::Fragment { children: &[], id, source_loc: loc };
        assert_eq!(text.kind(), 1);
        assert_eq!(frag.kind(), 6);
    }
}
