"""Element classes."""

MAP = {
        "forms": [
            "button",
            "fieldset",
            "form",
            "input",
            "label",
            "legend",
            "meter",
            "optgroup",
            "option",
            "output",
            "progress",
            "select",
            "textarea"
        ],
        "inline": [
            "a",
            "A",
            "abbr",
            "Abbr",
            "b",
            "bdi",
            "bdo",
            "br",
            "cite",
            "code",
            "data",
            "dfn",
            "em",
            "i",
            "kbd",
            "mark",
            "q",
            "rp",
            "rt",
            "ruby",
            "s",
            "samp",
            "small",
            "span",
            "strong",
            "sub",
            "sup",
            "time",
            "u",
            "wbr"
        ],
        "media": [
            "area",
            "audio",
            "img",
            "map",
            "track",
            "video",
            "embed",
            "iframe",
            "object",
            "picture",
            "portal",
            "source",
            "svg",
            "path"
        ],
        "metadata": [
            "base",
            "head",
            "link",
            "meta",
            "title",
        ],
        "other": [
            "details",
            "dialog",
            "summary",
            "slot",
            "template",
            "math",
            "html"
        ],
        "scripts": [
            "canvas",
            "noscript",
            "script"
        ],
        "sectioning": [
            "address",
            "article",
            "aside",
            "body",
            "header",
            "footer",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "main",
            "nav",
            "section"
        ],
        "tables": [
            "caption",
            "col",
            "colgroup",
            "table",
            "td",
            "tfoot",
            "th",
            "thead",
            "tr"
        ],
        "typography": [
            "blockquote",
            "dd",
            "div",
            "dl",
            "dt",
            "figcaption",
            "hr",
            "ol",
            "li",
            "p",
            "pre",
            "ul",
            "ins",
            "del_",
            "Del"
        ],
    }
import lazy_loader as lazy

EXCLUDE = ["del_", "Del"]
for k, v in MAP.items():
    v.extend([a.capitalize() if not a in EXCLUDE else a for a in v])

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"base"},
    submod_attrs=MAP,
)