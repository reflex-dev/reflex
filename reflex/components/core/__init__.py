"""Core Reflex components."""

from __future__ import annotations

from reflex.utils import lazy_loader

_SUBMODULES: set[str] = {"layout"}

_SUBMOD_ATTRS: dict[str, list[str]] = {
    "banner": [
        "ConnectionBanner",
        "ConnectionModal",
        "ConnectionPulser",
        "ConnectionToaster",
        "connection_banner",
        "connection_modal",
        "connection_toaster",
        "connection_pulser",
    ],
    "clipboard": ["Clipboard", "clipboard"],
    "colors": [
        "color",
    ],
    "cond": ["Cond", "color_mode_cond", "cond"],
    "debounce": ["DebounceInput", "debounce_input"],
    "foreach": [
        "foreach",
        "Foreach",
    ],
    "html": ["html", "Html"],
    "match": [
        "match",
        "Match",
    ],
    "breakpoints": ["breakpoints", "set_breakpoints"],
    "responsive": [
        "desktop_only",
        "mobile_and_tablet",
        "mobile_only",
        "tablet_and_desktop",
        "tablet_only",
    ],
    "upload": [
        "upload",
        "cancel_upload",
        "clear_selected_files",
        "get_upload_dir",
        "get_upload_url",
        "selected_files",
    ],
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
