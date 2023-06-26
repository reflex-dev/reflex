"""An AutoComplete omponent."""

from reflex.components.component import Component
from reflex.vars import Callable, Dict, List, Var


class AutoComplete(Component):
    """An Accessible Autocomplete Utility for Chakra UI that composes Downshift ComboBox."""

    library = "chakra-ui-autocomplete"

    tag = "CUIAutoComplete"

    # An array of the items to be selected within the input field
    items: Var[List]

    # The placeholder for the input field
    placeholder: Var[str]

    # Input Form Label to describe the activity or process
    label: Var[str]

    # For accessibility, you can define a custom color for the highlight color
    # when user is typing also accept props like yellow.300 based on chakra theme provider
    highlightItemBg: Var[str]

    # Function to handle creating new Item
    onCreateItem: Var[Callable]

    # You can define a custom Function to handle filter logic
    optionFilterFunc: Var[Callable]

    # Custom Function that can either return a JSX Element or String,
    # in order to control how the list items within the Dropdown is rendered
    itemRender: Var[Callable]

    # Custom style props based on chakra-ui for labels,
    # Example `{{ bg: 'gray.100', pt: '4'}}
    labelStyleProps: Var[Dict]

    # Custom style props based on chakra-ui for input field,
    # Example`{{ bg: 'gray.100', pt: '4'}}
    inputStyleProps: Var[Dict]

    # Custom style props based on chakra-ui for toggle button,
    # Example `{{ bg: 'gray.100', pt: '4'}}
    toggleButtonStyleProps: Var[Dict]

    # Custom style props based on chakra-ui for multi option tags,
    # Example`{{ bg: 'gray.100', pt: '4'}}
    tagStyleProps: Var[Dict]

    # Custom style props based on chakra-ui for dropdown list,
    # Example `{{ bg: 'gray.100', pt: '4'}}
    listStyleProps: Var[Dict]

    # Custom style props based on chakra-ui for single list item in dropdown,
    # Example`{{ bg: 'gray.100', pt: '4'}}
    listItemStyleProps: Var[Dict]

    # Custom style props based on chakra-ui for the green tick icon in dropdown list,
    # Example `{{ bg: 'gray.100', pt: '4'}}
    selectedIconProps: Var[Dict]

    # hideToggleButton
    hideToggleButton: Var[bool]

    # Disable the "create new" list Item. Default is false
    disableCreateItem: Var[bool]

    # Custom Function that can either return a JSX Element or String,
    # in order to control how the create new item within the Dropdown is rendered.
    createItemRenderer: Var[Callable]

    # Custom function to render input from outside chakra-ui-autocomplete.
    # Receives input props for the input element and toggleButtonProps for the toggle button.
    renderCustomerInput: Var[Callable]
