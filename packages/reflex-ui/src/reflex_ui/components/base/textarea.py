"""Custom Textarea component."""

from reflex.components.el import Textarea as TextareaComponent

from reflex.components.component import Component
from reflex_ui.components.component import CoreComponent


class ClassNames:
    """Class names for textarea components."""

    ROOT = "focus:shadow-[0px_0px_0px_2px_var(--primary-4)] focus:border-primary-7 focus:hover:border-primary-7 bg-secondary-1 border border-secondary-a4 hover:border-secondary-a6 transition-[color,box-shadow] disabled:border-secondary-4 disabled:bg-secondary-3 disabled:text-secondary-8 disabled:cursor-not-allowed cursor-text min-h-24 rounded-ui-md text-secondary-12 placeholder:text-secondary-9 text-sm disabled:placeholder:text-secondary-8 w-full outline-none max-h-[15rem] resize-none overflow-y-auto px-3 py-2.5 font-medium"


class Textarea(TextareaComponent, CoreComponent):
    """Root component for Textarea."""

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the textarea component.

        Returns:
            The component.
        """
        props.setdefault(
            "custom_attrs",
            {
                "autoComplete": "off",
                "autoCapitalize": "none",
                "autoCorrect": "off",
                "spellCheck": "false",
            },
        )
        props["data-slot"] = "textarea"
        cls.set_class_name(ClassNames.ROOT, props)
        return super().create(*children, **props)


textarea = Textarea.create
