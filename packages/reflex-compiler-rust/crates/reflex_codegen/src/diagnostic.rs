//! User-facing diagnostics. See plan §4.6.
//!
//! A `Diagnostic` is the framework's structured error type: a severity,
//! a short message, a (file, line, col) location pulled from the IR's
//! `SourceLoc`, and optionally a longer help message. The struct mirrors
//! the data `miette` expects when rendering — we keep it deliberately small
//! and dependency-light because PyO3 has to ferry it back to Python where
//! `miette` itself isn't available.
//!
//! Once the consumer is happy with the structured form we can wire
//! `miette::Diagnostic` in a separate crate to render terminal-style spans.

use reflex_ir::SourceLoc;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Severity {
    Error,
    Warning,
    Note,
}

#[derive(Debug, Clone)]
pub struct Diagnostic {
    pub severity: Severity,
    pub code: &'static str,
    pub message: String,
    pub source_loc: SourceLoc,
    pub help: Option<String>,
}

impl Diagnostic {
    pub fn error(code: &'static str, message: impl Into<String>, loc: SourceLoc) -> Self {
        Self {
            severity: Severity::Error,
            code,
            message: message.into(),
            source_loc: loc,
            help: None,
        }
    }

    pub fn warning(code: &'static str, message: impl Into<String>, loc: SourceLoc) -> Self {
        Self {
            severity: Severity::Warning,
            code,
            message: message.into(),
            source_loc: loc,
            help: None,
        }
    }

    pub fn with_help(mut self, help: impl Into<String>) -> Self {
        self.help = Some(help.into());
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use reflex_ir::PyFileId;

    #[test]
    fn error_builder() {
        let d = Diagnostic::error(
            "E001",
            "unknown tag",
            SourceLoc { file: PyFileId(1), line: 10, col: 5 },
        )
        .with_help("try one of: div, span, p");
        assert_eq!(d.severity, Severity::Error);
        assert_eq!(d.code, "E001");
        assert_eq!(d.message, "unknown tag");
        assert_eq!(d.source_loc.line, 10);
        assert_eq!(d.help.unwrap(), "try one of: div, span, p");
    }
}
