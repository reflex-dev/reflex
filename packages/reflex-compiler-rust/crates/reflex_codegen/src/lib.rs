//! IR → JS/JSX/CSS codegen. See plan §3, D8/D10, R6.
//!
//! All output goes through a single growable `CodeBuffer` (`Vec<u8>`). No
//! intermediate `String`s, no `format!` in per-node paths — use `write_*`
//! methods that append bytes directly.

#![forbid(unsafe_code)]

pub mod app_root;
pub mod app_root_module;
pub mod buffer;
pub mod context;
pub mod context_module;
pub mod diagnostic;
pub mod document_root_module;
pub mod jsx;
pub mod memo;
pub mod page;
pub mod sourcemap;
pub mod static_artifacts;
pub mod theme;
pub mod vite;

pub use app_root::emit_app_root;
pub use app_root_module::emit_app_root_module;
pub use buffer::CodeBuffer;
pub use context::emit_context;
pub use context_module::emit_context_module;
pub use diagnostic::{Diagnostic, Severity};
pub use document_root_module::emit_document_root_module;
pub use jsx::{emit_component, emit_component_with_map, emit_value};
pub use memo::{emit_memo_index, emit_memo_module};
pub use page::{emit_page, emit_page_with_extras, emit_page_with_map};
pub use sourcemap::SourceMap;
pub use static_artifacts::{emit_stateful_pages_json, emit_styles_root, emit_theme_module};
pub use theme::emit_theme;
pub use vite::emit_vite_config;
