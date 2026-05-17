//! Six aggregator walks over IR. See plan §3 / D7.
//!
//! The current Python compiler runs six independent tree walks
//! (`_get_all_hooks`, `_get_all_imports`, `_get_all_dynamic_imports`,
//! `_get_all_custom_code`, `_get_all_refs`, `_get_all_hooks_internal`). The
//! Rust port collapses them into a **single walk** that fills all six
//! collectors simultaneously — there's no good reason to walk the same tree
//! six times. Output is deduped while preserving first-seen order.
//!
//! Three of the six (`dynamic_imports`, `custom_code`, `refs`) depend on IR
//! fields that the §4 v1 schema doesn't carry explicitly. They're plumbed as
//! collectors today and return empty (or partial) sets — adding the schema
//! fields is a v2 task and the public API doesn't change.

#![forbid(unsafe_code)]

use reflex_intern::Symbol;
use reflex_ir::{Component, IrVisitor, Page, Value, VarData};

/// Result of one full aggregator walk. Each collection is deduped.
#[derive(Default, Debug)]
pub struct Aggregated<'a> {
    /// Hook fragments hoisted to the top of the render function. Includes
    /// `Hook.code` from each Element (position > 0) and `VarData.hooks` from
    /// each `Value`.
    pub hooks: Vec<&'a str>,
    /// `(module, name)` imports required by any rendered expression.
    pub imports: Vec<(Symbol, Symbol)>,
    /// Dynamic imports — schema-v2 placeholder.
    pub dynamic_imports: Vec<Symbol>,
    /// Custom JS code blocks — schema-v2 placeholder.
    pub custom_code: Vec<&'a str>,
    /// Component refs (`React.useRef`) — schema-v2 placeholder, surfaces
    /// `Value::Ref` symbols for now.
    pub refs: Vec<Symbol>,
    /// Hooks tagged as "internal" (Hook.position == 0). Distinct from `hooks`
    /// because the renderer ordering differs (state/theme hooks come first).
    pub internal_hooks: Vec<&'a str>,
}

impl<'a> Aggregated<'a> {
    pub fn new() -> Self {
        Self::default()
    }

    fn add_hook(&mut self, code: &'a str, position: u8) {
        let target = if position == 0 {
            &mut self.internal_hooks
        } else {
            &mut self.hooks
        };
        if !target.iter().any(|s| *s == code) {
            target.push(code);
        }
    }

    fn add_var_hook(&mut self, code: &'a str) {
        if !self.hooks.iter().any(|s| *s == code) {
            self.hooks.push(code);
        }
    }

    fn add_import(&mut self, module: Symbol, name: Symbol) {
        if !self.imports.iter().any(|p| *p == (module, name)) {
            self.imports.push((module, name));
        }
    }

    fn add_ref(&mut self, sym: Symbol) {
        if !self.refs.contains(&sym) {
            self.refs.push(sym);
        }
    }
}

/// Run all six aggregator walks in one pass over `page`. The returned
/// `Aggregated<'a>` borrows from the same arena `page` borrows from.
pub fn aggregate<'a>(page: &Page<'a>) -> Aggregated<'a> {
    let mut agg = Aggregated::new();
    let mut visitor = AggregateVisitor { agg: &mut agg };
    visitor.visit_page(page);
    agg
}

struct AggregateVisitor<'r, 'a> {
    agg: &'r mut Aggregated<'a>,
}

impl<'r, 'a> IrVisitor<'a> for AggregateVisitor<'r, 'a> {
    #[inline]
    fn visit_var_data(&mut self, vd: &VarData<'a>) {
        for hook in vd.hooks {
            self.agg.add_var_hook(hook);
        }
        for (m, n) in vd.imports {
            self.agg.add_import(*m, *n);
        }
    }

    #[inline]
    fn visit_component(&mut self, component: &Component<'a>) {
        if let Component::Element { hooks, .. } = component {
            for h in *hooks {
                self.agg.add_hook(h.code, h.position);
            }
        }
        reflex_ir::walk_component(self, component);
    }

    #[inline]
    fn visit_value(&mut self, v: &Value<'a>) {
        if let Value::Ref(sym) = v {
            self.agg.add_ref(*sym);
        }
        reflex_ir::walk_value(self, v);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use reflex_arena::Arena;
    use reflex_ir::parse::test_helpers::tiny_page_bytes;
    use reflex_ir::parse_page;

    #[test]
    fn empty_page_has_no_aggregates() {
        let arena = Arena::new();
        let bytes = tiny_page_bytes();
        let page = parse_page(&arena, &bytes).unwrap();
        let agg = aggregate(&page);
        assert!(agg.hooks.is_empty());
        assert!(agg.imports.is_empty());
        assert!(agg.refs.is_empty());
    }
}
