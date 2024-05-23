"""Data grid components."""

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"components", "layout", "typography"},
    submod_attrs={
        "code": [
            "CodeBlock",
            "code_block",
            "theme",
            "theme_panel",
            "LiteralCodeBlockTheme",
            "LiteralCodeLanguage",
        ],
        "dataeditor": ["data_editor", "data_editor_theme", "DataEditorTheme"],
        "logo": ["logo"],
    },
)
