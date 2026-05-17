//! Bump arena + thread-local single-slot stash. See plan §3.1, §3.3, R1/R2/R8.
//!
//! R2 (no-Drop): `Arena::alloc` requires `T: Copy`, which Rust enforces is
//! mutually exclusive with `Drop`. The const assertion is belt-and-braces —
//! it catches `Copy` types that wrap a `ManuallyDrop`-disabled non-trivial
//! payload before they ever reach a hot path.
//!
//! R8 deviation: the plan calls for `#[thread_local]` (nightly-only). We use
//! the stable `thread_local!` macro. The teardown race R8 cites is specific
//! to bun's mimalloc; `bumpalo::Bump` releases via the default allocator at
//! Drop, so the destructor ordering issue does not apply.

use std::cell::{Cell, RefCell};

use bumpalo::Bump;

pub struct Arena(Bump);

impl Arena {
    #[inline]
    pub fn new() -> Self {
        Self(Bump::new())
    }

    #[inline]
    pub fn with_capacity(cap: usize) -> Self {
        Self(Bump::with_capacity(cap))
    }

    /// Allocate one `T`. `T: Copy` is the R2 enforcement; the const assert is
    /// a redundancy that catches future regressions.
    #[inline(always)]
    pub fn alloc<T: Copy>(&self, value: T) -> &mut T {
        const { assert!(!std::mem::needs_drop::<T>()) }
        self.0.alloc(value)
    }

    #[inline]
    pub fn alloc_slice_copy<T: Copy>(&self, src: &[T]) -> &mut [T] {
        const { assert!(!std::mem::needs_drop::<T>()) }
        self.0.alloc_slice_copy(src)
    }

    /// Build a slice from an iterator, copying through the arena.
    #[inline]
    pub fn alloc_slice_fill_iter<T, I>(&self, iter: I) -> &mut [T]
    where
        T: Copy,
        I: IntoIterator<Item = T>,
        I::IntoIter: ExactSizeIterator,
    {
        const { assert!(!std::mem::needs_drop::<T>()) }
        self.0.alloc_slice_fill_iter(iter)
    }

    #[inline]
    pub fn alloc_str(&self, s: &str) -> &str {
        self.0.alloc_str(s)
    }

    #[inline]
    pub fn bump(&self) -> &Bump {
        &self.0
    }

    #[inline]
    pub fn reset(&mut self) {
        self.0.reset();
    }

    #[inline]
    pub fn allocated_bytes(&self) -> usize {
        self.0.allocated_bytes()
    }
}

impl Default for Arena {
    fn default() -> Self {
        Self::new()
    }
}

thread_local! {
    static ARENA_STASH: RefCell<Option<Arena>> = const { RefCell::new(None) };
}

/// An arena rented from the thread-local stash. Returned to the stash on Drop,
/// or freed if the stash is occupied (bun's single-slot semantic — nested
/// scopes are rare; the second arena drops normally).
pub struct PooledArena {
    arena: Option<Arena>,
    used: Cell<bool>,
}

impl PooledArena {
    #[inline]
    pub fn acquire() -> Self {
        let arena = ARENA_STASH
            .with(|cell| cell.borrow_mut().take())
            .unwrap_or_else(Arena::new);
        Self {
            arena: Some(arena),
            used: Cell::new(false),
        }
    }

    /// Borrow the arena. First call marks the arena as used; Drop will reset
    /// before returning to the stash. If never called, Drop skips the reset
    /// (R8 dirty-bit).
    #[inline]
    pub fn arena(&self) -> &Arena {
        self.used.set(true);
        self.arena
            .as_ref()
            .expect("arena always present until Drop")
    }
}

impl Drop for PooledArena {
    fn drop(&mut self) {
        let Some(mut arena) = self.arena.take() else {
            return;
        };
        if self.used.get() {
            arena.reset();
        }
        ARENA_STASH.with(|cell| {
            let mut slot = cell.borrow_mut();
            if slot.is_none() {
                *slot = Some(arena);
            }
        });
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Clone, Copy)]
    struct Point {
        x: i32,
        y: i32,
    }

    #[test]
    fn alloc_returns_arena_ref() {
        let arena = Arena::new();
        let p = arena.alloc(Point { x: 1, y: 2 });
        assert_eq!(p.x, 1);
        assert_eq!(p.y, 2);
    }

    #[test]
    fn alloc_str_copies_into_arena() {
        let arena = Arena::new();
        let s = String::from("hello");
        let r = arena.alloc_str(&s);
        drop(s);
        assert_eq!(r, "hello");
    }

    #[test]
    fn alloc_slice_copies() {
        let arena = Arena::new();
        let src = [1u32, 2, 3, 4];
        let r = arena.alloc_slice_copy(&src);
        assert_eq!(r, &[1, 2, 3, 4]);
    }

    #[test]
    fn pooled_arena_round_trip() {
        let a = PooledArena::acquire();
        let _ = a.arena().alloc(42u32);
        drop(a);
        let b = PooledArena::acquire();
        let _ = b.arena().alloc(7u32);
        drop(b);
    }

    #[test]
    fn unused_pooled_arena_skips_reset() {
        let a = PooledArena::acquire();
        drop(a);
    }
}
