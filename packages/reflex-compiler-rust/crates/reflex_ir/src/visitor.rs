//! Monomorphic IR visitor. See plan §3 / D6, R3.
//!
//! Every `visit_*` method has a default that calls the corresponding free
//! `walk_*` function. Visitors override only the nodes they care about. The
//! traversal is generic (no `&dyn Trait`) so each visitor monomorphizes its
//! own copy of the walk functions — match arms inline and the compiler can
//! kill the dead branches.

use crate::{Component, EventHandler, Hook, MatchArm, Meta, Page, Value, VarData};

pub trait IrVisitor<'a> {
    #[inline]
    fn visit_page(&mut self, page: &Page<'a>) {
        walk_page(self, page);
    }

    #[inline]
    fn visit_component(&mut self, component: &Component<'a>) {
        walk_component(self, component);
    }

    #[inline]
    fn visit_value(&mut self, value: &Value<'a>) {
        walk_value(self, value);
    }

    #[inline]
    fn visit_var_data(&mut self, _var_data: &VarData<'a>) {}

    #[inline]
    fn visit_event_handler(&mut self, handler: &EventHandler<'a>) {
        walk_event_handler(self, handler);
    }

    #[inline]
    fn visit_hook(&mut self, _hook: &Hook<'a>) {}

    #[inline]
    fn visit_match_arm(&mut self, arm: &MatchArm<'a>) {
        walk_match_arm(self, arm);
    }

    #[inline]
    fn visit_meta(&mut self, _meta: &Meta<'a>) {}
}

#[inline]
pub fn walk_page<'a, V: IrVisitor<'a> + ?Sized>(v: &mut V, page: &Page<'a>) {
    for meta in page.meta {
        v.visit_meta(meta);
    }
    v.visit_component(page.root);
}

#[inline]
pub fn walk_component<'a, V: IrVisitor<'a> + ?Sized>(v: &mut V, component: &Component<'a>) {
    match component {
        Component::Element {
            props,
            children,
            event_handlers,
            hooks,
            ..
        } => {
            for (_, value) in *props {
                v.visit_value(value);
            }
            for child in *children {
                v.visit_component(child);
            }
            for handler in *event_handlers {
                v.visit_event_handler(handler);
            }
            for hook in *hooks {
                v.visit_hook(hook);
            }
        }
        Component::Text { .. } => {}
        Component::Foreach { iter, body, .. } => {
            v.visit_value(iter);
            v.visit_component(body);
        }
        Component::Cond {
            test, then, else_, ..
        } => {
            v.visit_value(test);
            v.visit_component(then);
            if let Some(e) = else_ {
                v.visit_component(e);
            }
        }
        Component::Match {
            value,
            arms,
            default,
            ..
        } => {
            v.visit_value(value);
            for arm in *arms {
                v.visit_match_arm(arm);
            }
            if let Some(d) = default {
                v.visit_component(d);
            }
        }
        Component::Memoize { inner, .. } => {
            v.visit_component(inner);
        }
        Component::Fragment { children, .. } => {
            for child in *children {
                v.visit_component(child);
            }
        }
        Component::Expr { value, .. } => {
            v.visit_value(value);
        }
    }
}

#[inline]
pub fn walk_value<'a, V: IrVisitor<'a> + ?Sized>(v: &mut V, value: &Value<'a>) {
    if let Value::JsExpr { var_data, .. } = value {
        v.visit_var_data(var_data);
    }
}

#[inline]
pub fn walk_event_handler<'a, V: IrVisitor<'a> + ?Sized>(v: &mut V, handler: &EventHandler<'a>) {
    v.visit_var_data(&handler.var_data);
}

#[inline]
pub fn walk_match_arm<'a, V: IrVisitor<'a> + ?Sized>(v: &mut V, arm: &MatchArm<'a>) {
    v.visit_value(&arm.case);
    v.visit_component(arm.body);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{NodeId, SourceLoc};

    struct Counter {
        components: usize,
        values: usize,
    }

    impl<'a> IrVisitor<'a> for Counter {
        fn visit_component(&mut self, c: &Component<'a>) {
            self.components += 1;
            walk_component(self, c);
        }

        fn visit_value(&mut self, v: &Value<'a>) {
            self.values += 1;
            walk_value(self, v);
        }
    }

    #[test]
    fn counts_nested_components() {
        let loc = SourceLoc::SYNTHETIC;
        let inner_text = Component::Text {
            value: "hi",
            id: NodeId(1),
            source_loc: loc,
        };
        let root = Component::Fragment {
            children: std::slice::from_ref(&inner_text),
            id: NodeId(2),
            source_loc: loc,
        };
        let mut c = Counter { components: 0, values: 0 };
        c.visit_component(&root);
        assert_eq!(c.components, 2);
        assert_eq!(c.values, 0);
    }
}
