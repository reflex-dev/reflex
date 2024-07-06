"""Default mixin for all app mixins."""

from reflex.base import Base


class AppMixin(Base):
    """Define the base class for all app mixins."""

    def _init_mixin(self):
        """Initialize the mixin.

        Any App mixin can override this method to perform any initialization.
        """
        ...
