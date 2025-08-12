"""Namespace for experimental features."""

from types import SimpleNamespace

from reflex.components.datadisplay.shiki_code_block import code_block as code_block
from reflex.utils.console import warn
from reflex.utils.misc import run_in_thread

from . import hooks as hooks
from .client_state import ClientStateVar as ClientStateVar


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
    code_block=code_block,
)
