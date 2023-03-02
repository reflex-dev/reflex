"""Import all the components."""
from __future__ import annotations

from typing import TYPE_CHECKING

from pynecone import utils

from .component import Component
from .datadisplay import *
from .disclosure import *
from .feedback import *
from .forms import *
from .graphing import *
from .layout import *
from .media import *
from .navigation import *
from .overlay import *
from .typography import *

if TYPE_CHECKING:
    from typing import Any

# Add the convenience methods for all the components.
# locals().update(
#     {
#         utils.to_snake_case(name): value.create
#         for name, value in locals().items()
#         if isinstance(value, type) and issubclass(value, Component)
#     }
# )

component = Component.create
badge = Badge.create
code = Code.create
code_block = CodeBlock.create
data_table = DataTable.create
divider = Divider.create
list = List.create
list_item = ListItem.create
ordered_list = OrderedList.create
unordered_list = UnorderedList.create
stat = Stat.create
stat_arrow = StatArrow.create
stat_group = StatGroup.create
stat_help_text = StatHelpText.create
stat_label = StatLabel.create
stat_number = StatNumber.create
table = Table.create
table_caption = TableCaption.create
table_container = TableContainer.create
tbody = Tbody.create
td = Td.create
tfoot = Tfoot.create
th = Th.create
thead = Thead.create
tr = Tr.create
accordion = Accordion.create
accordion_button = AccordionButton.create
accordion_icon = AccordionIcon.create
accordion_item = AccordionItem.create
accordion_panel = AccordionPanel.create
tab = Tab.create
tab_list = TabList.create
tab_panel = TabPanel.create
tab_panels = TabPanels.create
tabs = Tabs.create
visually_hidden = VisuallyHidden.create
alert = Alert.create
alert_description = AlertDescription.create
alert_icon = AlertIcon.create
alert_title = AlertTitle.create
circular_progress = CircularProgress.create
circular_progress_label = CircularProgressLabel.create
progress = Progress.create
skeleton = Skeleton.create
skeleton_circle = SkeletonCircle.create
skeleton_text = SkeletonText.create
spinner = Spinner.create
button = Button.create
button_group = ButtonGroup.create
checkbox = Checkbox.create
checkbox_group = CheckboxGroup.create
copy_to_clipboard = CopyToClipboard.create
editable = Editable.create
editable_input = EditableInput.create
editable_preview = EditablePreview.create
editable_textarea = EditableTextarea.create
form_control = FormControl.create
form_error_message = FormErrorMessage.create
form_helper_text = FormHelperText.create
form_label = FormLabel.create
icon_button = IconButton.create
input = Input.create
input_group = InputGroup.create
input_left_addon = InputLeftAddon.create
input_right_addon = InputRightAddon.create
number_decrement_stepper = NumberDecrementStepper.create
number_increment_stepper = NumberIncrementStepper.create
number_input = NumberInput.create
number_input_field = NumberInputField.create
number_input_stepper = NumberInputStepper.create
option = Option.create
password = Password.create
pin_input = PinInput.create
pin_input_field = PinInputField.create
radio = Radio.create
radio_group = RadioGroup.create
range_slider = RangeSlider.create
range_slider_filled_track = RangeSliderFilledTrack.create
range_slider_thumb = RangeSliderThumb.create
range_slider_track = RangeSliderTrack.create
select = Select.create
slider = Slider.create
slider_filled_track = SliderFilledTrack.create
slider_mark = SliderMark.create
slider_thumb = SliderThumb.create
slider_track = SliderTrack.create
switch = Switch.create
text_area = TextArea.create
upload = Upload.create
area = Area.create
bar = Bar.create
box_plot = BoxPlot.create
candlestick = Candlestick.create
chart = Chart.create
chart_group = ChartGroup.create
chart_stack = ChartStack.create
error_bar = ErrorBar.create
histogram = Histogram.create
line = Line.create
pie = Pie.create
plotly = Plotly.create
polar = Polar.create
scatter = Scatter.create
voronoi = Voronoi.create
box = Box.create
center = Center.create
circle = Circle.create
container = Container.create
flex = Flex.create
foreach = Foreach.create
fragment = Fragment.create
grid = Grid.create
grid_item = GridItem.create
hstack = Hstack.create
html = Html.create
responsive_grid = ResponsiveGrid.create
spacer = Spacer.create
square = Square.create
stack = Stack.create
vstack = Vstack.create
wrap = Wrap.create
wrap_item = WrapItem.create
avatar = Avatar.create
avatar_badge = AvatarBadge.create
avatar_group = AvatarGroup.create
icon = Icon.create
image = Image.create
breadcrumb = Breadcrumb.create
breadcrumb_item = BreadcrumbItem.create
breadcrumb_link = BreadcrumbLink.create
breadcrumb_separator = BreadcrumbSeparator.create
link = Link.create
link_box = LinkBox.create
link_overlay = LinkOverlay.create
next_link = NextLink.create
alert_dialog = AlertDialog.create
alert_dialog_body = AlertDialogBody.create
alert_dialog_content = AlertDialogContent.create
alert_dialog_footer = AlertDialogFooter.create
alert_dialog_header = AlertDialogHeader.create
alert_dialog_overlay = AlertDialogOverlay.create
drawer = Drawer.create
drawer_body = DrawerBody.create
drawer_close_button = DrawerCloseButton.create
drawer_content = DrawerContent.create
drawer_footer = DrawerFooter.create
drawer_header = DrawerHeader.create
drawer_overlay = DrawerOverlay.create
menu = Menu.create
menu_button = MenuButton.create
menu_divider = MenuDivider.create
menu_group = MenuGroup.create
menu_item = MenuItem.create
menu_item_option = MenuItemOption.create
menu_list = MenuList.create
menu_option_group = MenuOptionGroup.create
modal = Modal.create
modal_body = ModalBody.create
modal_close_button = ModalCloseButton.create
modal_content = ModalContent.create
modal_footer = ModalFooter.create
modal_header = ModalHeader.create
modal_overlay = ModalOverlay.create
popover = Popover.create
popover_anchor = PopoverAnchor.create
popover_arrow = PopoverArrow.create
popover_body = PopoverBody.create
popover_close_button = PopoverCloseButton.create
popover_content = PopoverContent.create
popover_footer = PopoverFooter.create
popover_header = PopoverHeader.create
popover_trigger = PopoverTrigger.create
tooltip = Tooltip.create
heading = Heading.create
markdown = Markdown.create
span = Span.create
text = Text.create


# Add responsive styles shortcuts.
def mobile_only(*children, **props):
    """Create a component that is only visible on mobile.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["block", "none", "none", "none"])


def tablet_only(*children, **props):
    """Create a component that is only visible on tablet.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["none", "block", "block", "none"])


def desktop_only(*children, **props):
    """Create a component that is only visible on desktop.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["none", "none", "none", "block"])


def tablet_and_desktop(*children, **props):
    """Create a component that is only visible on tablet and desktop.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["none", "block", "block", "block"])


def mobile_and_tablet(*children, **props):
    """Create a component that is only visible on mobile and tablet.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["block", "block", "block", "none"])


def cond(condition: Any, c1: Any, c2: Any = None):
    """Create a conditional component or Prop.

    Args:
        condition: The cond to determine which component to render.
        c1: The component or prop to render if the cond_var is true.
        c2: The component or prop to render if the cond_var is false.

    Returns:
        The conditional component.

    Raises:
        ValueError: If the arguments are invalid.
    """
    # Import here to avoid circular imports.
    from pynecone.var import BaseVar, Var

    # Convert the condition to a Var.
    cond_var = Var.create(condition)
    assert cond_var is not None, "The condition must be set."

    # If the first component is a component, create a Cond component.
    if isinstance(c1, Component):
        assert c2 is None or isinstance(
            c2, Component
        ), "Both arguments must be components."
        return Cond.create(cond_var, c1, c2)

    # Otherwise, create a conditionl Var.
    # Check that the second argument is valid.
    if isinstance(c2, Component):
        raise ValueError("Both arguments must be props.")
    if c2 is None:
        raise ValueError("For conditional vars, the second argument must be set.")

    # Create the conditional var.
    return BaseVar(
        name=utils.format_cond(
            cond=cond_var.full_name,
            true_value=c1,
            false_value=c2,
            is_prop=True,
        ),
        type_=c1.type_ if isinstance(c1, BaseVar) else type(c1),
    )
