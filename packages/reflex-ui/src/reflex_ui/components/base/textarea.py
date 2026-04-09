"""Custom Textarea component."""

from reflex_components_core.el.elements.forms import Textarea as TextareaComponent

from reflex.components.component import Component
from reflex_ui.components.component import CoreComponent


class ClassNames:
    """Class names for textarea components."""

    ROOT = "outline-none bg-white dark:bg-secondary-3 shrink-0 border border-secondary-4 hover:border-secondary-a6 transition-[color,box-shadow] focus:shadow-[0px_0px_0px_2px_var(--primary-4)] focus:border-primary-a6 not-data-[invalid]:focus:hover:border-primary-a6 shadow-[0_1px_2px_0_rgba(0,0,0,0.02),0_1px_4px_0_rgba(0,0,0,0.02)] dark:shadow-none dark:border-secondary-5 disabled:border-secondary-4 disabled:bg-secondary-3 disabled:text-secondary-8 disabled:placeholder:text-secondary-8 disabled:cursor-not-allowed cursor-text has-data-[invalid]:border-destructive-10 has-data-[invalid]:focus:border-destructive-a11 has-data-[invalid]:focus:shadow-[0px_0px_0px_2px_var(--destructive-4)] has-data-[invalid]:hover:border-destructive-a11 text-secondary-12 placeholder:text-secondary-10 text-sm leading-normal w-full font-medium min-h-24 max-h-[15rem] resize-none overflow-y-auto px-2.5 py-1.5 rounded-ui-md"


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
