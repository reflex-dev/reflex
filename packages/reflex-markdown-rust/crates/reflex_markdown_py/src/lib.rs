//! pulldown-cmark Markdown → HTML, exposed as a Reflex acceleration wheel.
//!
//! Replaces the legacy mistletoe-based path on the Python side (see plan
//! §5: markdown is ~0.79s of the 10.1s docs-app baseline; pulldown-cmark
//! is consistently 15-30× faster on equivalent inputs).
//!
//! Exposed surface (all functions release the GIL during parse):
//!
//! * `markdown_to_html(text: str) -> str` — render with the default
//!   `Options::ENABLE_TABLES | ENABLE_FOOTNOTES | ENABLE_STRIKETHROUGH
//!   | ENABLE_TASKLISTS | ENABLE_SMART_PUNCTUATION` set, matching the
//!   subset Reflex docs use today.
//! * `markdown_to_html_with(text, options: int) -> str` — caller-controlled
//!   options bitmask. Constants exposed on the module: `OPT_TABLES`,
//!   `OPT_FOOTNOTES`, `OPT_STRIKETHROUGH`, `OPT_TASKLISTS`,
//!   `OPT_SMART_PUNCTUATION`, `OPT_HEADING_ATTRIBUTES`, `OPT_YAML_STYLE_METADATA_BLOCKS`.
//! * `event_count(text: str) -> int` — quick benchmark probe; counts pulldown
//!   events without rendering. Useful for perf comparisons.

use pulldown_cmark::{html, Options, Parser};
use pyo3::prelude::*;

const DEFAULT_OPTS: u32 = Options::ENABLE_TABLES.bits()
    | Options::ENABLE_FOOTNOTES.bits()
    | Options::ENABLE_STRIKETHROUGH.bits()
    | Options::ENABLE_TASKLISTS.bits()
    | Options::ENABLE_SMART_PUNCTUATION.bits();

#[pyfunction]
fn markdown_to_html(py: Python<'_>, text: &str) -> PyResult<String> {
    let owned = text.to_owned();
    Ok(py.allow_threads(move || render_html(&owned, Options::from_bits_truncate(DEFAULT_OPTS))))
}

#[pyfunction]
fn markdown_to_html_with(py: Python<'_>, text: &str, options: u32) -> PyResult<String> {
    let owned = text.to_owned();
    Ok(py.allow_threads(move || render_html(&owned, Options::from_bits_truncate(options))))
}

#[pyfunction]
fn event_count(py: Python<'_>, text: &str) -> PyResult<usize> {
    let owned = text.to_owned();
    Ok(py.allow_threads(move || {
        Parser::new_ext(&owned, Options::from_bits_truncate(DEFAULT_OPTS)).count()
    }))
}

fn render_html(text: &str, opts: Options) -> String {
    let parser = Parser::new_ext(text, opts);
    let mut out = String::with_capacity(text.len() * 2);
    html::push_html(&mut out, parser);
    out
}

#[pymodule]
fn _native(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(markdown_to_html, m)?)?;
    m.add_function(wrap_pyfunction!(markdown_to_html_with, m)?)?;
    m.add_function(wrap_pyfunction!(event_count, m)?)?;

    // Option constants — kept in sync with `pulldown_cmark::Options` bit
    // values. Python callers can OR these together and pass to
    // `markdown_to_html_with`. Bumping pulldown-cmark may shift these; the
    // version is pinned in workspace Cargo.toml so we'll notice.
    m.add("OPT_TABLES", Options::ENABLE_TABLES.bits())?;
    m.add("OPT_FOOTNOTES", Options::ENABLE_FOOTNOTES.bits())?;
    m.add("OPT_STRIKETHROUGH", Options::ENABLE_STRIKETHROUGH.bits())?;
    m.add("OPT_TASKLISTS", Options::ENABLE_TASKLISTS.bits())?;
    m.add("OPT_SMART_PUNCTUATION", Options::ENABLE_SMART_PUNCTUATION.bits())?;
    m.add("OPT_HEADING_ATTRIBUTES", Options::ENABLE_HEADING_ATTRIBUTES.bits())?;
    m.add(
        "OPT_YAML_STYLE_METADATA_BLOCKS",
        Options::ENABLE_YAML_STYLE_METADATA_BLOCKS.bits(),
    )?;
    m.add("DEFAULT_OPTS", DEFAULT_OPTS)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renders_basic_markdown() {
        let html = render_html("# Hello\n\nworld", Options::empty());
        assert!(html.contains("<h1>Hello</h1>"));
        assert!(html.contains("<p>world</p>"));
    }

    #[test]
    fn renders_tables_when_enabled() {
        let md = "| a | b |\n|---|---|\n| 1 | 2 |";
        let plain = render_html(md, Options::empty());
        let with_tables = render_html(md, Options::ENABLE_TABLES);
        assert!(!plain.contains("<table>"));
        assert!(with_tables.contains("<table>"));
    }

    #[test]
    fn counts_events() {
        let parser = Parser::new_ext("# hi\n\np", Options::empty());
        assert!(parser.count() > 0);
    }
}
