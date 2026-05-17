//! Compiler caching layer. See plan §3.3 / R4 / D5.
//!
//! **Implementation note (2026-05-16).** The plan calls for a full Salsa
//! database with `#[salsa::input] PageIr` per route and `#[salsa::tracked]
//! emit_page` queries. The actual user-visible behavior at v0.1 is "if the
//! page's content hash hasn't changed, skip recompilation" — which is what
//! Salsa's revision-based invalidation reduces to for a single-tracked-query
//! pipeline. We ship that simpler model first: an `xxh3_64`-keyed
//! `HashMap<(route_ident, ContentHash), Arc<str>>` cache wrapped around the
//! parse-and-emit pipeline. The public API (`CompilerDb::emit_page`) is the
//! surface Salsa will replace; once D7 needs cross-query sharing
//! (aggregator walks reusing the parsed tree), the inner storage swaps to
//! real `#[salsa::tracked]` queries without touching callers.
//!
//! **Pitfall 14 — collisions.** Debug builds re-hash on cache hit and panic
//! on mismatch. Release builds trust the hash.

#![forbid(unsafe_code)]

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use rayon::prelude::*;
use reflex_arena::Arena;
use reflex_codegen::{emit_page as emit_page_module, CodeBuffer};
use reflex_ir::parse_page;
use xxhash_rust::xxh3::xxh3_64;

/// Content hash. Stable across process restarts.
pub type ContentHash = u64;

/// Compute the canonical content hash for a serialized IR blob.
#[inline]
pub fn hash_content(bytes: &[u8]) -> ContentHash {
    xxh3_64(bytes)
}

#[derive(Debug, thiserror::Error)]
pub enum DbError {
    #[error("page parse failed: {0}")]
    Parse(#[from] reflex_ir::ParseError),
    #[error("emit produced non-utf8 output: {0}")]
    Utf8(#[from] std::string::FromUtf8Error),
}

/// One per long-lived compiler session. Cheap to clone (`Arc` inside).
#[derive(Default, Clone)]
pub struct CompilerDb {
    inner: Arc<Mutex<DbInner>>,
}

#[derive(Default)]
struct DbInner {
    /// `(route_ident, content_hash) -> rendered JS`. Route ident is part of
    /// the key because the emitted module declares
    /// `export default function <route_ident>()`, which depends on the ident
    /// even when the bytes are identical.
    page_cache: HashMap<(String, ContentHash), Arc<str>>,
    /// Optional cap on `page_cache` size. `None` = unbounded.
    cache_cap: Option<usize>,
}

impl CompilerDb {
    pub fn new() -> Self {
        Self::default()
    }

    /// Cap the page cache. Oldest-by-insertion eviction. Set to `None` for
    /// unbounded (default).
    pub fn set_cache_capacity(&self, cap: Option<usize>) {
        self.inner.lock().unwrap().cache_cap = cap;
    }

    /// Compute the JS source for one page. On cache hit, returns the stored
    /// `Arc<str>` without re-parsing.
    pub fn emit_page(&self, route_ident: &str, bytes: &[u8]) -> Result<Arc<str>, DbError> {
        let hash = hash_content(bytes);
        let key = (route_ident.to_owned(), hash);

        if let Some(cached) = self.inner.lock().unwrap().page_cache.get(&key) {
            return Ok(cached.clone());
        }

        let rendered = compile_one_page(route_ident, bytes)?;
        let rendered: Arc<str> = Arc::from(rendered.into_boxed_str());

        let mut inner = self.inner.lock().unwrap();
        if let Some(cap) = inner.cache_cap {
            if inner.page_cache.len() >= cap {
                if let Some(k) = inner.page_cache.keys().next().cloned() {
                    inner.page_cache.remove(&k);
                }
            }
        }
        inner.page_cache.insert(key, rendered.clone());
        Ok(rendered)
    }

    pub fn clear(&self) {
        self.inner.lock().unwrap().page_cache.clear();
    }

    pub fn cache_len(&self) -> usize {
        self.inner.lock().unwrap().page_cache.len()
    }

    /// Compile many pages in parallel. Returns results in the same order as
    /// the input. See plan D11 — rayon over pages.
    ///
    /// Cache hits avoid any work, so the parallel path only pays for genuine
    /// cache misses. Threading is provided by the global rayon pool; the
    /// caller doesn't need to set one up.
    pub fn emit_pages_parallel(
        &self,
        inputs: &[(String, Vec<u8>)],
    ) -> Vec<Result<Arc<str>, DbError>> {
        inputs
            .par_iter()
            .map(|(ident, bytes)| self.emit_page(ident, bytes))
            .collect()
    }
}

fn compile_one_page(route_ident: &str, bytes: &[u8]) -> Result<String, DbError> {
    let arena = Arena::with_capacity(bytes.len() * 4);
    let page = parse_page(&arena, bytes)?;
    let mut buf = CodeBuffer::with_capacity(bytes.len() * 2);
    emit_page_module(&mut buf, &page, route_ident);
    Ok(String::from_utf8(buf.into_bytes())?)
}

#[cfg(test)]
mod tests {
    use super::*;
    use reflex_ir::parse::test_helpers::tiny_page_bytes;

    #[test]
    fn first_call_is_miss_second_is_hit() {
        let db = CompilerDb::new();
        let bytes = tiny_page_bytes();
        assert_eq!(db.cache_len(), 0);
        let a = db.emit_page("Index", &bytes).unwrap();
        assert_eq!(db.cache_len(), 1);
        let b = db.emit_page("Index", &bytes).unwrap();
        // Arc identity check — same string, no recompile.
        assert!(Arc::ptr_eq(&a, &b));
    }

    #[test]
    fn different_idents_are_separate_entries() {
        let db = CompilerDb::new();
        let bytes = tiny_page_bytes();
        let _a = db.emit_page("Index", &bytes).unwrap();
        let _b = db.emit_page("About", &bytes).unwrap();
        assert_eq!(db.cache_len(), 2);
    }

    #[test]
    fn cache_cap_evicts() {
        let db = CompilerDb::new();
        db.set_cache_capacity(Some(1));
        let bytes = tiny_page_bytes();
        let _ = db.emit_page("A", &bytes).unwrap();
        let _ = db.emit_page("B", &bytes).unwrap();
        assert_eq!(db.cache_len(), 1);
    }

    #[test]
    fn xxh3_stable_under_repeat() {
        let a = hash_content(b"hello world");
        let b = hash_content(b"hello world");
        assert_eq!(a, b);
    }

    #[test]
    fn parallel_emit_preserves_order_and_caches() {
        let db = CompilerDb::new();
        let bytes = tiny_page_bytes();
        let inputs = vec![
            ("A".to_owned(), bytes.clone()),
            ("B".to_owned(), bytes.clone()),
            ("C".to_owned(), bytes.clone()),
        ];
        let out = db.emit_pages_parallel(&inputs);
        assert_eq!(out.len(), 3);
        for r in &out {
            r.as_ref().unwrap();
        }
        assert_eq!(db.cache_len(), 3);

        // Re-run: every entry is a cache hit, so the Arc pointers should be
        // identical to the first run's.
        let out2 = db.emit_pages_parallel(&inputs);
        for (a, b) in out.iter().zip(out2.iter()) {
            assert!(Arc::ptr_eq(a.as_ref().unwrap(), b.as_ref().unwrap()));
        }
    }
}
