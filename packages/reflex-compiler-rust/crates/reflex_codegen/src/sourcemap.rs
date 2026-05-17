//! Source-map recording during JSX emission. See plan §4.6.
//!
//! Every IR node carries a `SourceLoc` (`PyFileId`, line, col). When the
//! codegen emits that node's tokens it records the current `CodeBuffer`
//! byte offset alongside the `SourceLoc`. The resulting `SourceMap` lets a
//! diagnostic at byte N of the emitted module back-map to the Python source
//! that produced it.
//!
//! The format is intentionally simple — a sorted `Vec<(u32 offset, SourceLoc)>`.
//! Lookup is binary search. We don't emit JS-side source maps (`source-map`
//! v3) here because the consumer of these mappings is Reflex's own error
//! reporter, not the browser. If browser source maps are needed later, this
//! is the layer that converts.

use reflex_ir::SourceLoc;

#[derive(Debug, Clone, Default)]
pub struct SourceMap {
    entries: Vec<(u32, SourceLoc)>,
}

impl SourceMap {
    pub fn new() -> Self {
        Self::default()
    }

    /// Record `offset → loc`. `offset` should be the byte position in the
    /// surrounding `CodeBuffer` just before the token whose origin is `loc`.
    #[inline]
    pub fn record(&mut self, offset: u32, loc: SourceLoc) {
        // Skip synthetic locations — they don't help diagnostics and would
        // bloat the map.
        if loc.file.0 == 0 && loc.line == 0 && loc.col == 0 {
            return;
        }
        // Merge consecutive identical locations — they tend to cluster at
        // every prop/child of the same Element.
        if let Some((_, last)) = self.entries.last() {
            if *last == loc {
                return;
            }
        }
        self.entries.push((offset, loc));
    }

    /// Find the SourceLoc that covers `offset`. Returns `None` if `offset`
    /// precedes all recorded entries.
    pub fn lookup(&self, offset: u32) -> Option<SourceLoc> {
        if self.entries.is_empty() {
            return None;
        }
        match self.entries.binary_search_by_key(&offset, |(o, _)| *o) {
            Ok(idx) => Some(self.entries[idx].1),
            Err(0) => None,
            Err(idx) => Some(self.entries[idx - 1].1),
        }
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn entries(&self) -> &[(u32, SourceLoc)] {
        &self.entries
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use reflex_ir::PyFileId;

    fn loc(file: u32, line: u32) -> SourceLoc {
        SourceLoc {
            file: PyFileId(file),
            line,
            col: 1,
        }
    }

    #[test]
    fn skip_synthetic() {
        let mut m = SourceMap::new();
        m.record(10, SourceLoc::SYNTHETIC);
        assert!(m.is_empty());
    }

    #[test]
    fn merges_consecutive_duplicates() {
        let mut m = SourceMap::new();
        m.record(0, loc(1, 5));
        m.record(10, loc(1, 5));
        m.record(20, loc(1, 5));
        assert_eq!(m.len(), 1);
    }

    #[test]
    fn lookup_picks_floor() {
        let mut m = SourceMap::new();
        m.record(0, loc(1, 5));
        m.record(100, loc(1, 10));
        m.record(200, loc(2, 1));
        assert_eq!(m.lookup(0).unwrap().line, 5);
        assert_eq!(m.lookup(50).unwrap().line, 5);
        assert_eq!(m.lookup(100).unwrap().line, 10);
        assert_eq!(m.lookup(150).unwrap().line, 10);
        assert_eq!(m.lookup(200).unwrap().line, 1);
        assert_eq!(m.lookup(1000).unwrap().line, 1);
    }

    #[test]
    fn lookup_below_first_returns_none() {
        let mut m = SourceMap::new();
        m.record(100, loc(1, 5));
        assert!(m.lookup(0).is_none());
        assert!(m.lookup(99).is_none());
    }
}
