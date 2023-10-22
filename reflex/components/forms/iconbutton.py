"""An icon button component."""

from reflex.components.component import Component
from reflex.components.typography.text import Text
from reflex.utils import imports
from reflex.vars import Var


class IconButton(Text):
    """A button with an icon."""

    tag = "IconButton"

    # The type of button.
    type: Var[str]

    #  A label that describes the button
    aria_label: Var[str]

    # The icon to be used in the button.
    icon: Var[Component]

    # If true, the button will be styled in its active state.
    is_active: Var[bool]

    # If true, the button will be disabled.
    is_disabled: Var[bool]

    # If true, the button will show a spinner.
    is_loading: Var[bool]

    # If true, the button will be perfectly round. Else, it'll be slightly round
    is_round: Var[bool]

    # Replace the spinner component when isLoading is set to true
    spinner: Var[str]

    _props_import = {}

    def _get_imports(self) -> imports.ImportDict:
        return imports.merge_imports(
            super()._get_imports(),
            self._props_import,
        )

    @classmethod
    def create(cls, *children, **props):
        """Create an IconButton component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Raises:
            ValueError: Raise an error if invalid value is provided.

        Returns:
            The IconButton component.
        """
        comp = super().create(*children, **props)
        if "icon" in props:
            icon = props.get("icon")
            if isinstance(icon, Component):
                comp._props_import = icon._get_imports()
            else:
                raise ValueError(
                    "The `icon` props only accept statically defined Components, not State vars."
                )
        return comp
