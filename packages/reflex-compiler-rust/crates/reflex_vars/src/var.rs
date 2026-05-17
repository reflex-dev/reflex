//! The `Var` base struct — final JS expression string + optional `VarData`.
//!
//! Mirrors the data shape of `Var` at
//! `packages/reflex-base/src/reflex_base/vars/base.py:400-525`. The full typed
//! hierarchy (`NumberVar`, `StringVar`, …) and operator overloads land in
//! follow-up iterations once the PyO3 boundary is wired up.

use crate::var_data::VarData;

/// A finalized JS expression plus its metadata.
///
/// On the Python side this carries a generic `VAR_TYPE` parameter that
/// participates in type narrowing. The Rust port keeps the type information
/// out for now — the typed hierarchy will be modeled as an enum tag in a
/// follow-up. `js_expr` is the canonical JS source that lands in emitted JSX.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Var {
    js_expr: String,
    var_data: Option<VarData>,
}

impl Var {
    /// Construct a `Var` with the given JS expression and no metadata.
    pub fn new(js_expr: impl Into<String>) -> Self {
        Self {
            js_expr: js_expr.into(),
            var_data: None,
        }
    }

    /// Construct a `Var` with the given JS expression and metadata.
    pub fn with_data(js_expr: impl Into<String>, var_data: VarData) -> Self {
        let var_data = if var_data.is_empty() {
            None
        } else {
            Some(var_data)
        };
        Self {
            js_expr: js_expr.into(),
            var_data,
        }
    }

    /// The literal JS source the codegen splices into the emitted module.
    pub fn js_expr(&self) -> &str {
        &self.js_expr
    }

    /// Metadata, if any — `None` for unmetered literal vars.
    pub fn var_data(&self) -> Option<&VarData> {
        self.var_data.as_ref()
    }

    /// Replace the `VarData` on this `Var`, returning a new value.
    ///
    /// The replacement is dropped to `None` when empty so two structurally
    /// equal Vars with empty metadata compare equal regardless of how they
    /// were constructed.
    pub fn with_var_data(mut self, var_data: VarData) -> Self {
        self.var_data = if var_data.is_empty() {
            None
        } else {
            Some(var_data)
        };
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_var_has_no_data() {
        let v = Var::new("1 + 2");
        assert_eq!(v.js_expr(), "1 + 2");
        assert!(v.var_data().is_none());
    }

    #[test]
    fn with_data_keeps_data() {
        let data = VarData {
            state: "S".into(),
            ..VarData::default()
        };
        let v = Var::with_data("getS().count", data.clone());
        assert_eq!(v.js_expr(), "getS().count");
        assert_eq!(v.var_data(), Some(&data));
    }

    #[test]
    fn with_data_drops_empty_var_data() {
        let v = Var::with_data("1", VarData::empty());
        assert!(v.var_data().is_none());
    }

    #[test]
    fn equality_includes_data() {
        let a = Var::new("x");
        let b = Var::new("x");
        let c = Var::with_data(
            "x",
            VarData {
                state: "S".into(),
                ..VarData::default()
            },
        );
        assert_eq!(a, b);
        assert_ne!(a, c);
    }

    #[test]
    fn vars_are_hashable() {
        let a = Var::new("x");
        let b = Var::new("x");
        let mut set = std::collections::HashSet::new();
        set.insert(a);
        assert!(set.contains(&b));
    }
}
