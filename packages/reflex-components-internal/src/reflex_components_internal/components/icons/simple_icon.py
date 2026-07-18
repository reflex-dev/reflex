"""Simple Icon component wrapper for @icons-pack/react-simple-icons."""

import reflex as rx
from reflex.utils.imports import ImportVar


class SimpleIcon(rx.Component):
    """Simple Icon component wrapper for @icons-pack/react-simple-icons."""

    library = "@icons-pack/react-simple-icons@13.8.0"

    tag = "SiReact"

    # The color of the icon
    color: rx.Var[str]

    # The size of the icon
    size: rx.Var[int | str]

    @classmethod
    def create(cls, icon_name: str, **props):
        """Create a SimpleIcon component.

        Args:
            icon_name: The icon component name (e.g., "SiReact", "SiGithub", "SiPython")
            **props: Additional props like size, color

        Returns:
            The component instance.
        """
        instance = super().create(**props)
        instance.tag = icon_name
        return instance

    def add_imports(self):
        """Add the specific icon import.

        Returns:
            The component.
        """
        return {
            self.library: ImportVar(
                tag=self.tag,
                is_default=False,
            )
        }


simple_icon = SimpleIcon.create
