//! `VarData`, `ImportVar`, `HookPosition` — the metadata that travels with
//! every `Var`. Mirrors the Python dataclasses in
//! `packages/reflex-base/src/reflex_base/vars/base.py` and
//! `packages/reflex-base/src/reflex_base/utils/imports.py`.

use std::sync::Arc;

use crate::var::Var;

/// Where in the emitted component body a hook is allowed to live.
///
/// Matches `Hooks.HookPosition` at
/// `packages/reflex-base/src/reflex_base/constants/compiler.py:166`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum HookPosition {
    Internal,
    PreTrigger,
    PostTrigger,
}

impl HookPosition {
    /// The wire-format string used by the Python side (`Enum.value`).
    pub fn as_str(self) -> &'static str {
        match self {
            HookPosition::Internal => "internal",
            HookPosition::PreTrigger => "pre_trigger",
            HookPosition::PostTrigger => "post_trigger",
        }
    }
}

/// A single named import from a JS module.
///
/// Mirrors `ImportVar` at
/// `packages/reflex-base/src/reflex_base/utils/imports.py:106-141`.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct ImportVar {
    pub tag: Option<String>,
    pub is_default: bool,
    pub alias: Option<String>,
    pub install: bool,
    pub render: bool,
    pub package_path: String,
}

impl ImportVar {
    pub fn new(tag: impl Into<String>) -> Self {
        Self {
            tag: Some(tag.into()),
            is_default: false,
            alias: None,
            install: true,
            render: true,
            package_path: "/".to_owned(),
        }
    }

    /// The display name used in the emitted `import { name } from "lib"` line.
    ///
    /// Matches `ImportVar.name` at `imports.py:128-141`.
    pub fn name(&self) -> String {
        match (&self.alias, &self.tag) {
            (Some(alias), Some(tag)) => {
                if self.is_default && tag != "*" {
                    alias.clone()
                } else {
                    format!("{tag} as {alias}")
                }
            }
            (Some(alias), None) => alias.clone(),
            (None, Some(tag)) => tag.clone(),
            (None, None) => String::new(),
        }
    }
}

/// Metadata associated with a `Var` — imports it pulls in, hooks it needs, the
/// enclosing state, and so on. **Frozen / value-typed:** every mutation
/// produces a new `VarData`.
///
/// Mirrors `VarData` at `vars/base.py:116-322`.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Default)]
pub struct VarData {
    pub state: String,
    pub field_name: String,
    /// Ordered list of `(module, imports)` pairs — preserves first-seen order
    /// per the `ParsedImportTuple` shape on the Python side.
    pub imports: Vec<(String, Vec<ImportVar>)>,
    /// Ordered list of hook source lines, deduplicated by first occurrence.
    pub hooks: Vec<String>,
    /// `Arc` so cloning `VarData` is cheap even when many Vars share deps.
    pub deps: Vec<Arc<Var>>,
    pub position: Option<HookPosition>,
    /// Placeholder until `reflex_component` lands. Stored as opaque identifier
    /// strings (the Component's `id` / class name) so `VarData` keeps its
    /// `Hash`/`Eq` derives.
    pub components: Vec<String>,
}

impl VarData {
    /// True when every field is at its default value — matches `__bool__`
    /// semantics at `vars/base.py:272-286`.
    pub fn is_empty(&self) -> bool {
        self.state.is_empty()
            && self.field_name.is_empty()
            && self.imports.is_empty()
            && self.hooks.is_empty()
            && self.deps.is_empty()
            && self.position.is_none()
            && self.components.is_empty()
    }

    /// Convenience: the same shape as `VarData::default()` but spelled out so
    /// callers don't have to import `Default`.
    pub fn empty() -> Self {
        Self::default()
    }

    /// Merge a chain of `VarData` references into a single value.
    ///
    /// Semantics match `VarData.merge` at `vars/base.py:200-270`:
    ///
    /// * `state` / `field_name` come from the **first** non-empty entry.
    /// * `hooks` and `imports` are unioned, preserving first-seen order.
    /// * `deps` and `components` are concatenated in input order.
    /// * `position` collapses to the single non-`None` position, or `None`
    ///   when there is none. Returns `Err` when two entries disagree.
    ///
    /// `None` entries are filtered out. If everything is `None` (or empty
    /// after filtering), returns `Ok(None)`.
    pub fn merge<'a, I>(parts: I) -> Result<Option<VarData>, MergeError>
    where
        I: IntoIterator<Item = Option<&'a VarData>>,
    {
        let parts: Vec<&VarData> = parts.into_iter().flatten().collect();

        if parts.is_empty() {
            return Ok(None);
        }
        if parts.len() == 1 {
            return Ok(Some(parts[0].clone()));
        }

        let field_name = parts
            .iter()
            .map(|d| d.field_name.as_str())
            .find(|s| !s.is_empty())
            .unwrap_or("")
            .to_owned();

        let state = parts
            .iter()
            .map(|d| d.state.as_str())
            .find(|s| !s.is_empty())
            .unwrap_or("")
            .to_owned();

        // Hooks: dedup, preserve first-seen order.
        let mut hooks: Vec<String> = Vec::new();
        let mut seen_hooks: std::collections::HashSet<&str> = std::collections::HashSet::new();
        for d in &parts {
            for h in &d.hooks {
                if seen_hooks.insert(h.as_str()) {
                    hooks.push(h.clone());
                }
            }
        }

        // Imports: per-module dedup, preserve first-seen module order. Within
        // a module, dedup imports by full equality.
        let mut imports: Vec<(String, Vec<ImportVar>)> = Vec::new();
        for d in &parts {
            for (module, vars) in &d.imports {
                let slot = match imports.iter_mut().find(|(m, _)| m == module) {
                    Some(s) => &mut s.1,
                    None => {
                        imports.push((module.clone(), Vec::new()));
                        &mut imports.last_mut().unwrap().1
                    }
                };
                for v in vars {
                    if !slot.contains(v) {
                        slot.push(v.clone());
                    }
                }
            }
        }

        let deps: Vec<Arc<Var>> = parts.iter().flat_map(|d| d.deps.iter().cloned()).collect();

        let mut positions: Vec<HookPosition> = Vec::new();
        for d in &parts {
            if let Some(p) = d.position {
                if !positions.contains(&p) {
                    positions.push(p);
                }
            }
        }
        let position = match positions.len() {
            0 => None,
            1 => Some(positions[0]),
            _ => return Err(MergeError::ConflictingPositions(positions)),
        };

        let components: Vec<String> = parts
            .iter()
            .flat_map(|d| d.components.iter().cloned())
            .collect();

        Ok(Some(VarData {
            state,
            field_name,
            imports,
            hooks,
            deps,
            position,
            components,
        }))
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MergeError {
    ConflictingPositions(Vec<HookPosition>),
}

impl std::fmt::Display for MergeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MergeError::ConflictingPositions(ps) => {
                write!(f, "cannot merge var data with different positions: {ps:?}")
            }
        }
    }
}

impl std::error::Error for MergeError {}

#[cfg(test)]
mod tests {
    use super::*;

    fn import(module: &str, tag: &str) -> (String, Vec<ImportVar>) {
        (module.to_owned(), vec![ImportVar::new(tag)])
    }

    #[test]
    fn import_var_name_default() {
        let iv = ImportVar {
            tag: Some("Foo".into()),
            is_default: true,
            alias: Some("FooAlias".into()),
            ..ImportVar::new("Foo")
        };
        assert_eq!(iv.name(), "FooAlias");
    }

    #[test]
    fn import_var_name_aliased_named() {
        let iv = ImportVar {
            tag: Some("Foo".into()),
            is_default: false,
            alias: Some("FooAlias".into()),
            ..ImportVar::new("Foo")
        };
        assert_eq!(iv.name(), "Foo as FooAlias");
    }

    #[test]
    fn import_var_name_unaliased() {
        let iv = ImportVar::new("Foo");
        assert_eq!(iv.name(), "Foo");
    }

    #[test]
    fn empty_var_data_is_empty() {
        assert!(VarData::default().is_empty());
        assert!(VarData::empty().is_empty());
    }

    #[test]
    fn nonempty_var_data_is_not_empty() {
        let d = VarData {
            state: "MyState".into(),
            ..VarData::default()
        };
        assert!(!d.is_empty());
    }

    #[test]
    fn merge_empty_returns_none() {
        let result = VarData::merge(std::iter::empty::<Option<&VarData>>()).unwrap();
        assert!(result.is_none());

        let result = VarData::merge([None, None]).unwrap();
        assert!(result.is_none());
    }

    #[test]
    fn merge_single_returns_clone() {
        let d = VarData {
            state: "S".into(),
            field_name: "f".into(),
            ..VarData::default()
        };
        let merged = VarData::merge([Some(&d)]).unwrap().unwrap();
        assert_eq!(merged, d);
    }

    #[test]
    fn merge_picks_first_nonempty_state_and_field() {
        let a = VarData::default();
        let b = VarData {
            state: "FromB".into(),
            field_name: "fromB".into(),
            ..VarData::default()
        };
        let c = VarData {
            state: "FromC".into(),
            field_name: "fromC".into(),
            ..VarData::default()
        };
        let merged = VarData::merge([Some(&a), Some(&b), Some(&c)])
            .unwrap()
            .unwrap();
        assert_eq!(merged.state, "FromB");
        assert_eq!(merged.field_name, "fromB");
    }

    #[test]
    fn merge_hooks_dedupes_preserving_first_seen() {
        let a = VarData {
            hooks: vec!["h1".into(), "h2".into()],
            ..VarData::default()
        };
        let b = VarData {
            hooks: vec!["h2".into(), "h3".into()],
            ..VarData::default()
        };
        let merged = VarData::merge([Some(&a), Some(&b)]).unwrap().unwrap();
        assert_eq!(merged.hooks, vec!["h1", "h2", "h3"]);
    }

    #[test]
    fn merge_imports_dedupes_per_module() {
        let a = VarData {
            imports: vec![import("react", "useState"), import("react", "useEffect")],
            ..VarData::default()
        };
        let b = VarData {
            imports: vec![import("react", "useState"), import("./foo", "Foo")],
            ..VarData::default()
        };
        let merged = VarData::merge([Some(&a), Some(&b)]).unwrap().unwrap();
        assert_eq!(merged.imports.len(), 2);
        let react = &merged.imports[0];
        assert_eq!(react.0, "react");
        assert_eq!(react.1.len(), 2);
        let foo = &merged.imports[1];
        assert_eq!(foo.0, "./foo");
        assert_eq!(foo.1.len(), 1);
    }

    #[test]
    fn merge_position_unifies_when_compatible() {
        let a = VarData {
            position: Some(HookPosition::Internal),
            ..VarData::default()
        };
        let b = VarData {
            position: None,
            ..VarData::default()
        };
        let c = VarData {
            position: Some(HookPosition::Internal),
            ..VarData::default()
        };
        let merged = VarData::merge([Some(&a), Some(&b), Some(&c)])
            .unwrap()
            .unwrap();
        assert_eq!(merged.position, Some(HookPosition::Internal));
    }

    #[test]
    fn merge_position_errors_on_conflict() {
        let a = VarData {
            position: Some(HookPosition::Internal),
            ..VarData::default()
        };
        let b = VarData {
            position: Some(HookPosition::PreTrigger),
            ..VarData::default()
        };
        let err = VarData::merge([Some(&a), Some(&b)]).unwrap_err();
        assert!(matches!(err, MergeError::ConflictingPositions(_)));
    }

    #[test]
    fn var_data_round_trips_through_hash_set() {
        // Frozen-dataclass invariant on the Python side: VarData is hashable
        // and value-equal. The Rust analogue is `#[derive(Hash, Eq)]`.
        let d = VarData {
            state: "S".into(),
            hooks: vec!["h".into()],
            ..VarData::default()
        };
        let mut set = std::collections::HashSet::new();
        set.insert(d.clone());
        assert!(set.contains(&d));
    }
}
