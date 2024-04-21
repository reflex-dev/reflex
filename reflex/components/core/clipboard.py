"""Component to register global paste event."""

from enum import StrEnum
from typing import Any, Dict

from reflex import EventHandler, Fragment, Var
from reflex.utils import format, imports


class FormatType(StrEnum):
    """Format types for clipboardData API."""

    PLAIN_TEXT = "text/plain"
    HTML_TEXT  = "text/html"
    PNG_IMAGE  = "image/png"



class ClipBoard(Fragment):
    """A component to register a global past event."""

    format_type : FormatType  = FormatType.PLAIN_TEXT
    prevent_default: bool = False

    on_paste: EventHandler

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        default_triggers  = super().get_event_triggers()
        default_triggers["on_paste"] = lambda ev : [Var.create_safe(f"{ev}?.clipboardData?.getData('{self.format_type}')")]
        return default_triggers

    def _get_hooks(self) -> str | None:
        return """
            useEffect(() => {
                const handle_paste = (_ev) => {
                        %s
                        %s
                }
                document.addEventListener("paste", handle_paste, false);
                return () => {
                    document.removeEventListener("paste", handle_paste, false);
                }
            })
            """ % (
            f"{'_ev.preventDefault()' if self.prevent_default else ''}",
            format.format_event_chain(
                self.event_triggers["on_paste"]
            ),
        )
    

    
    def _get_imports(self) -> imports.ImportDict:
        return imports.merge_imports(
            super()._get_imports(),
            {
                "react": {
                    imports.ImportVar(
                        tag="useEffect"
                    )
                }
            },
        )
    
    def render(self) -> str:
        """Return empty string as component has no visual element."""
        return ""
