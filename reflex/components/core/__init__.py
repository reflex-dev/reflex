"""Core Reflex components."""
import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"layout"},
    submod_attrs={
        "banner": [
            "ConnectionBanner",
            "ConnectionModal",
            "ConnectionPulser",
            "ConnectionToaster",
            "connection_banner",
            "connection_modal",
            "connection_toaster",
            "connection_pulser"
        ],
        "colors": [
            "color",
        ],
        "cond": [
            "Cond",
            "color_mode_cond",
            "cond"
        ],
        "debounce": [
            "DebounceInput",
            "debounce_input"
        ],
        "foreach": [
            "foreach",
            "Foreach",
        ],
        "html": [
            "html",
            "Html"
        ],
        "match": [
            "match",
            "Match",
        ],
        "responsive": [
            "desktop_only",
            "mobile_and_tablet",
            "mobile_only",
            "tablet_and_desktop",
            "tablet_only"
        ],
        "upload": [
            "upload",
            "cancel_upload",
            "clear_selected_files",
            "get_upload_dir",
            "get_upload_url",
            "selected_files",
        ],
    },
)
