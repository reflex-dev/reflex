"""Provides a feature-rich Select and some (not all) related components."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Union

from reflex.base import Base
from reflex.components.component import Component
from reflex.constants import EventTriggers
from reflex.vars import Var


class Option(Base):
    """An option component for the chakra-react-select Select."""

    # What is displayed to the user
    label: str

    # The value of the option, must be serializable
    value: Any

    # the variant of the option tag
    variant: Optional[str] = None

    # [not working yet]
    # Whether the option is disabled
    # is_disabled: Optional[bool] = None

    # [not working yet]
    # The visual color appearance of the component
    # options: "whiteAlpha" | "blackAlpha" | "gray" | "red" |
    #  "orange" | "yellow" | "green" | "teal" | "blue" | "cyan" |
    #  "purple" | "pink" | "linkedin" | "facebook" | "messenger" |
    #  "whatsapp" | "twitter" | "telegram"
    # default: "gray"
    # color_scheme: Optional[str] = None

    # [not working yet]
    # The icon of the option tag
    # icon: Optional[str] = None


class Select(Component):
    """The default chakra-react-select Select component.
    Not every available prop is listed here,
    for a complete overview check the react-select/chakra-react-select docs.
    Props added by chakra-react-select are marked with "[chakra]".
    """

    library = "chakra-react-select"
    tag = "Select"

    # Focus the control when it is mounted
    auto_focus: Var[bool]

    # Remove the currently focused option when the user presses backspace
    #  when Select isClearable or isMulti
    backspace_removes_value: Var[bool]

    # Remove focus from the input when the user selects an option
    # (handy for dismissing the keyboard on touch devices)
    blur_input_on_select: Var[bool]

    # When the user reaches the top/bottom of the menu,
    # prevent scroll on the scroll-parent
    capture_menu_scroll: Var[bool]

    # [chakra]
    # To use the chakraStyles prop, first,
    # check the documentation for the original styles prop from the react-select docs.
    # This package offers an identical API for the chakraStyles prop, however,
    # the provided and output style objects use Chakra's sx prop
    # instead of the default emotion styles the original package offers.
    # This allows you to both use the shorthand styling props you'd normally use
    # to style Chakra components, as well as tokens from your theme such as named colors.
    # All of the style keys offered in the original package can be used in the chakraStyles prop
    # except for menuPortal. Along with some other caveats, this is explained below.
    # Most of the components rendered by this package use the basic Chakra <Box /> component with a few exceptions.
    # Here are the style keys offered and the corresponding Chakra component that is rendered:
    # - clearIndicator - Box (uses theme styles for Chakra's CloseButton)
    # - container - Box
    # - control - Box (uses theme styles for Chakra's Input)
    # - dropdownIndicator - Box (uses theme styles for Chrakra's InputRightAddon)
    # - downChevron - Icon
    # - crossIcon - Icon
    # - group - Box
    # - groupHeading - Box (uses theme styles for Chakra's Menu group title)
    # - indicatorsContainer - Box
    # - indicatorSeparator - Divider
    # - input - chakra.input (wrapped in a Box)
    # - inputContainer - Box
    # - loadingIndicator - Spinner
    # - loadingMessage - Box
    # - menu - Box
    # - menuList - Box (uses theme styles for Chakra's Menu)
    # - multiValue - chakra.span (uses theme styles for Chakra's Tag)
    # - multiValueLabel - chakra.span (uses theme styles for Chakra's TagLabel)
    # - multiValueRemove - Box (uses theme styles for Chakra's TagCloseButton)
    # - noOptionsMessage - Box
    # - option - Box (uses theme styles for Chakra's MenuItem)
    # - placeholder - Box
    # - singleValue - Box
    # - valueContainer - Box
    chakra_styles: Var[str]

    # Close the select menu when the user selects an option
    close_menu_on_select: Var[bool]

    # If true, close the select menu when the user scrolls the document/body.
    close_menu_on_scroll: Var[bool]

    # [chakra]
    # The visual color appearance of the component
    # options: "whiteAlpha" | "blackAlpha" | "gray" | "red" |
    #  "orange" | "yellow" | "green" | "teal" | "blue" | "cyan" |
    #  "purple" | "pink" | "linkedin" | "facebook" | "messenger" |
    #  "whatsapp" | "twitter" | "telegram"
    # default: "gray"
    color_scheme: Var[str]

    # This complex object includes all the compositional components
    # that are used in react-select. If you wish to overwrite a component,
    # pass in an object with the appropriate namespace.
    # If you only wish to restyle a component,
    # we recommend using the styles prop instead.
    components: Var[Dict[str, Component]]

    # Whether the value of the select, e.g. SingleValue,
    # should be displayed in the control.
    control_should_render_value: Var[bool]

    # Delimiter used to join multiple values into a single HTML Input value
    delimiter: Var[str]

    # [chakra]
    # Colors the component border with the given chakra color string on error state
    # default: "red.500"
    error_border_color: Var[str]

    # Clear all values when the user presses escape AND the menu is closed
    escape_clears_value: Var[bool]

    # [chakra]
    # Colors the component border with the given chakra color string on focus
    # default: "blue.500"
    focus_border_color: Var[str]

    # Sets the form attribute on the input
    form: Var[str]

    # Hide the selected option from the menu
    hide_selected_options: Var[bool]

    # The id to set on the SelectContainer component.
    # id: Var[str]

    # The value of the search input
    input_value: Var[str]

    # The id of the search input
    input_id: Var[str]

    # Is the select value clearable
    is_clearable: Var[bool]

    # Is the select disabled
    is_disabled: Var[bool]

    # [chakra]
    # Style component in the chakra invalid style
    # default: False
    is_invalid: Var[bool]

    # Support multiple selected options
    is_multi: Var[bool]

    # [chakra]
    # Style component as disabled (chakra style)
    # default: False
    is_read_only: Var[bool]

    # Is the select direction right-to-left
    is_rtl: Var[bool]

    # Whether to enable search functionality
    is_searchable: Var[bool]

    # Minimum height of the menu before flipping
    min_menu_height: Var[int]

    # Maximum height of the menu before scrolling
    max_menu_height: Var[int]

    # Default placement of the menu in relation to the control.
    # 'auto' will flip when there isn't enough space below the control.
    # options: "bottom" | "auto" | "top"
    menu_placement: Var[str]

    # The CSS position value of the menu,
    #  when "fixed" extra layout management is required
    # options: "absolute" | "fixed"
    menu_position: Var[str]

    # Whether to block scroll events when the menu is open
    menu_should_block_scroll: Var[bool]

    # Whether the menu should be scrolled into view when it opens
    menu_should_scroll_into_view: Var[bool]

    # Name of the HTML Input (optional - without this, no input will be rendered)
    name: Var[str]

    # Allows control of whether the menu is opened when the Select is focused
    open_menu_on_focus: Var[bool]

    # Allows control of whether the menu is opened when the Select is clicked
    open_menu_on_click: Var[bool]

    # Array of options that populate the select menu
    options: Var[List[Dict]]

    # Number of options to jump in menu when page{up|down} keys are used
    page_size: Var[int]

    # Placeholder for the select value
    placeholder: Var[Optional[str]]

    # Marks the value-holding input as required for form validation
    required: Var[bool]

    # [chakra]
    # If you choose to stick with the default selectedOptionStyle="color",
    # you have one additional styling option.
    # If you do not like the default of blue for the highlight color,
    # you can pass the selectedOptionColorScheme prop to change it.
    # This prop will accept any named color from your theme's color palette,
    # and it will use the 500 value in light mode or the 300 value in dark mode.
    # This prop can only be used for named colors from your theme, not arbitrary hex/rgb colors.
    # If you would like to use a specific color for the background that's not a part of your theme,
    # use the chakraStyles prop to customize it.
    # default: "blue"
    selected_option_color_scheme: Var[str]

    # [chakra]
    # The default option "color" will style a selected option
    # similar to how react-select does it,
    # by highlighting the selected option in the color blue.
    # Alternatively, if you pass "check" for the value,
    # the selected option will be styled like the Chakra UI Menu component
    # and include a check icon next to the selected option(s).
    # If is_multi and selected_option_style="check" are passed,
    # space will only be added for the check marks
    # if hide_selected_options=False is also passed.
    # options: "color" | "check"
    # default: "color"
    selected_option_style: Var[str]

    # [chakra]
    # The size of the component.
    # options: "sm" | "md" | "lg"
    # default: "md"
    size: Var[str]

    # Sets the tabIndex attribute on the input
    tab_index: Var[int]

    # Select the currently focused option when the user presses tab
    tab_selects_value: Var[bool]

    # [chakra]
    # Variant of multi-select tags
    # options: "subtle" | "solid" | "outline"
    # default: "subtle"
    tag_variant: Var[str]

    # Remove all non-essential styles
    unstyled: Var[bool]

    # [chakra]
    # If this prop is passed,
    # the dropdown indicator at the right of the component will be styled
    # in the same way the original Chakra Select component is styled,
    # instead of being styled as an InputRightAddon.
    # The original purpose of styling it as an addon
    # was to create a visual separation between the dropdown indicator
    # and the button for clearing the selected options.
    # However, as this button only appears when isMulti is passed,
    # using this style could make more sense for a single select.
    # default: False
    use_basic_style: Var[bool]

    # [chakra]
    # The variant of the Select. If no variant is passed,
    # it will default to defaultProps.variant from the theme for Chakra's Input component.
    # If your component theme for Input is not modified, it will be outline.
    # options: "outline" | "filled" | "flushed" | "unstyled"
    # default: "outline"
    variant: Var[str]

    # How the options should be displayed in the menu.
    menu_position: Var[str] = "fixed"  # type: ignore

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: (
                lambda e0: [Var.create_safe(f"{e0}.map(e => e.value)", is_local=True)]
                if self.is_multi
                else lambda e0: [e0]
            ),
        }

    @classmethod
    def get_initial_props(cls) -> Set[str]:
        """Get the initial props to set for the component.

        Returns:
            The initial props to set.
        """
        return super().get_initial_props() | {"is_multi"}

    @classmethod
    def create(
        cls, options: List[Union[Option, str, int, float, bool]], **props
    ) -> Component:
        """Takes a list of options and additional properties, checks if each option is an
        instance of Option, and returns a Select component with the given options and
        properties. No children allowed.

        Args:
            options (List[Option | str | int | float | bool]): A list of values.
            **props: Additional properties to be passed to the Select component.

        Returns:
            The `create` method is returning an instance of the `Select` class.
        """
        converted_options: List[Option] = []
        for option in options:
            if not isinstance(option, Option):
                converted_options.append(Option(label=str(option), value=option))
            else:
                converted_options.append(option)
        props["options"] = [o.dict() for o in converted_options]
        return super().create(*[], **props)
