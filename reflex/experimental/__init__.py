"""Namespace for experimental features."""

from types import SimpleNamespace

from reflex.components.datadisplay.shiki_code_block import code_block as code_block
from reflex.components.props import PropsBase
from reflex.components.radix.themes.components.progress import progress as progress
from reflex.components.sonner.toast import toast as toast

from ..utils.console import warn
from ..utils.misc import run_in_thread
from . import hooks as hooks
from .client_state import ClientStateVar as ClientStateVar
from .layout import layout as layout


class ExperimentalNamespace(SimpleNamespace):
    """Namespace for experimental features."""

    def __getattribute__(self, item: str):
        """Get attribute from the namespace.

        Args:
            item: attribute name.

        Returns:
            The attribute.
        """
        warn(
            "`rx._x` contains experimental features and might be removed at any time in the future.",
            dedupe=True,
        )
        return super().__getattribute__(item)

    @property
    def toast(self):
        """Temporary property returning the toast namespace.

        Remove this property when toast is fully promoted.

        Returns:
            The toast namespace.
        """
        self.register_component_warning("toast")
        return toast

    @property
    def progress(self):
        """Temporary property returning the progress component.

        Remove this property when progress is fully promoted.

        Returns:
            The progress component.
        """
        self.register_component_warning("progress")
        return progress

    @property
    def run_in_thread(self):
        """Temporary property returning the run_in_thread helper function.

        Remove this property when run_in_thread is fully promoted.

        Returns:
            The run_in_thread helper function.
        """
        self.register_component_warning("run_in_thread")
        return run_in_thread

    @staticmethod
    def register_component_warning(component_name: str):
        """Add component to emitted warnings and throw a warning if it
        doesn't exist.

        Args:
            component_name: name of the component.
        """
        warn(
            f"`rx._x.{component_name}` was promoted to `rx.{component_name}`.",
            dedupe=True,
        )


_x = ExperimentalNamespace(
    client_state=ClientStateVar.create,
    hooks=hooks,
    layout=layout,
    PropsBase=PropsBase,
    code_block=code_block,
)
