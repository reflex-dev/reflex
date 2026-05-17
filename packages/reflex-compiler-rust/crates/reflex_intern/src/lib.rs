//! Symbol interning. See plan §3, R5.
//!
//! Every identifier and namespace string in the IR is a `Symbol(u32)`. Equality
//! and hashing of identifiers becomes `u32 == u32`; the string materializes
//! only at final byte-emit time.
//!
//! This iteration ships a single per-process interner behind a `Mutex`. The
//! plan's R5/R8 target is per-thread sharded interners with `#[thread_local]`,
//! deferred until profiling shows the lock matters. The public API
//! (`Symbol`, `intern`, `resolve`, `well_known`) is stable across that change.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

/// Interned string identifier.
///
/// `Symbol(0)` is reserved for the empty string so `Symbol::default()` is a
/// valid no-op. Other symbols are assigned in insertion order.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Symbol(pub u32);

impl Symbol {
    pub const EMPTY: Symbol = Symbol(0);

    #[inline]
    pub fn as_u32(self) -> u32 {
        self.0
    }
}

impl Default for Symbol {
    fn default() -> Self {
        Self::EMPTY
    }
}

struct Interner {
    /// Indexed by `Symbol.0 as usize`. Strings live forever (leaked into
    /// `'static` so callers don't pay a copy at resolve time).
    strings: Vec<&'static str>,
    lookup: HashMap<&'static str, Symbol>,
}

impl Interner {
    fn new() -> Self {
        let mut me = Self {
            strings: Vec::with_capacity(64),
            lookup: HashMap::with_capacity(64),
        };
        let s = me.intern_inner("");
        debug_assert_eq!(s, Symbol::EMPTY);
        for name in WELL_KNOWN {
            me.intern_inner(name);
        }
        me
    }

    fn intern_inner(&mut self, s: &str) -> Symbol {
        if let Some(&sym) = self.lookup.get(s) {
            return sym;
        }
        let leaked: &'static str = Box::leak(s.to_owned().into_boxed_str());
        let sym = Symbol(self.strings.len() as u32);
        self.strings.push(leaked);
        self.lookup.insert(leaked, sym);
        sym
    }

    fn resolve(&self, sym: Symbol) -> Option<&'static str> {
        self.strings.get(sym.0 as usize).copied()
    }
}

fn interner() -> &'static Mutex<Interner> {
    static IT: OnceLock<Mutex<Interner>> = OnceLock::new();
    IT.get_or_init(|| Mutex::new(Interner::new()))
}

/// Common identifiers pre-interned at startup so they get low IDs and are
/// already in the table when the first compile starts.
const WELL_KNOWN: &[&str] = &[
    "rx.",
    "$/",
    "reflex___state____",
    "__reflex_",
    "react",
    "useState",
    "useEffect",
    "useCallback",
    "useMemo",
    "useRef",
    "useContext",
    "useReducer",
    "jsx",
    "Fragment",
    "children",
    "key",
    "ref",
    "className",
    "style",
    "onClick",
    "onChange",
    "onSubmit",
];

/// Intern a string, returning its `Symbol`.
pub fn intern(s: &str) -> Symbol {
    interner().lock().unwrap().intern_inner(s)
}

/// Resolve a `Symbol` back to its string. Returns `None` if the symbol was
/// created by a different interner instance (shouldn't happen in normal use).
pub fn resolve(sym: Symbol) -> Option<&'static str> {
    interner().lock().unwrap().resolve(sym)
}

/// Resolve, panicking on unknown symbol. Use only when an unknown symbol is a
/// program bug, not a recoverable error.
pub fn resolve_unchecked(sym: Symbol) -> &'static str {
    resolve(sym).expect("symbol not in interner")
}

/// Look up the `Symbol` for a known-pre-interned string. Returns `None` if the
/// string was never interned. Useful for hot-path comparisons that want to
/// avoid `intern()`'s mutex.
pub fn well_known(s: &str) -> Option<Symbol> {
    interner().lock().unwrap().lookup.get(s).copied()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_is_symbol_zero() {
        assert_eq!(intern(""), Symbol::EMPTY);
    }

    #[test]
    fn same_string_same_symbol() {
        let a = intern("foo_bar");
        let b = intern("foo_bar");
        assert_eq!(a, b);
    }

    #[test]
    fn different_strings_different_symbols() {
        let a = intern("alpha");
        let b = intern("beta");
        assert_ne!(a, b);
    }

    #[test]
    fn resolve_round_trip() {
        let s = intern("hello_world");
        assert_eq!(resolve(s).unwrap(), "hello_world");
    }

    #[test]
    fn well_known_returns_some() {
        assert!(well_known("rx.").is_some());
        assert!(well_known("react").is_some());
    }
}
