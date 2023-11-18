"""Import all the components."""
from __future__ import annotations

from .base import Script
from .component import Component
from .component import NoSSRComponent as NoSSRComponent
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

# Add the convenience methods for all the components.
# locals().update(
#     {
#         utils.to_snake_case(name): value.create
#         for name, value in locals().items()
#         if isinstance(value, type) and issubclass(value, Component)
#     }
# )

# Add the convenience methods for all the components manually.
# This is necessary for static type checking to work.
accordion = Accordion.create
accordion_button = AccordionButton.create
accordion_icon = AccordionIcon.create
accordion_item = AccordionItem.create
accordion_panel = AccordionPanel.create
alert = Alert.create
alert_description = AlertDescription.create
alert_dialog = AlertDialog.create
alert_dialog_body = AlertDialogBody.create
alert_dialog_content = AlertDialogContent.create
alert_dialog_footer = AlertDialogFooter.create
alert_dialog_header = AlertDialogHeader.create
alert_dialog_overlay = AlertDialogOverlay.create
alert_icon = AlertIcon.create
alert_title = AlertTitle.create
aspect_ratio = AspectRatio.create
audio = Audio.create
avatar = Avatar.create
avatar_badge = AvatarBadge.create
avatar_group = AvatarGroup.create
badge = Badge.create
box = Box.create
breadcrumb = Breadcrumb.create
breadcrumb_item = BreadcrumbItem.create
breadcrumb_link = BreadcrumbLink.create
breadcrumb_separator = BreadcrumbSeparator.create
button = Button.create
button_group = ButtonGroup.create
card = Card.create
card_body = CardBody.create
card_footer = CardFooter.create
card_header = CardHeader.create
center = Center.create
checkbox = Checkbox.create
checkbox_group = CheckboxGroup.create
circle = Circle.create
circular_progress = CircularProgress.create
circular_progress_label = CircularProgressLabel.create
code = Code.create
code_block = CodeBlock.create
collapse = Collapse.create
color_mode_button = ColorModeButton.create
color_mode_icon = ColorModeIcon.create
color_mode_switch = ColorModeSwitch.create
component = Component.create
connection_banner = ConnectionBanner.create
connection_modal = ConnectionModal.create
container = Container.create
data_editor = DataEditor.create
data_editor_theme = DataEditorTheme
data_table = DataTable.create
date_picker = DatePicker.create
date_time_picker = DateTimePicker.create
debounce_input = DebounceInput.create
divider = Divider.create
drawer = Drawer.create
drawer_body = DrawerBody.create
drawer_close_button = DrawerCloseButton.create
drawer_content = DrawerContent.create
drawer_footer = DrawerFooter.create
drawer_header = DrawerHeader.create
drawer_overlay = DrawerOverlay.create
editable = Editable.create
editable_input = EditableInput.create
editable_preview = EditablePreview.create
editable_textarea = EditableTextarea.create
editor = Editor.create
email = Email.create
fade = Fade.create
flex = Flex.create
foreach = Foreach.create
form = Form.create
form_control = FormControl.create
form_error_message = FormErrorMessage.create
form_helper_text = FormHelperText.create
form_label = FormLabel.create
fragment = Fragment.create
grid = Grid.create
grid_item = GridItem.create
heading = Heading.create
highlight = Highlight.create
hstack = Hstack.create
html = Html.create
icon = Icon.create
icon_button = IconButton.create
image = Image.create
input = Input.create
input_group = InputGroup.create
input_left_addon = InputLeftAddon.create
input_left_element = InputLeftElement.create
input_right_addon = InputRightAddon.create
input_right_element = InputRightElement.create
kbd = Kbd.create
link = Link.create
link_box = LinkBox.create
link_overlay = LinkOverlay.create
list = List.create
list_item = ListItem.create
markdown = Markdown.create
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
moment = Moment.create
multi_select = MultiSelect.create
multi_select_option = MultiSelectOption
next_link = NextLink.create
number_decrement_stepper = NumberDecrementStepper.create
number_increment_stepper = NumberIncrementStepper.create
number_input = NumberInput.create
number_input_field = NumberInputField.create
number_input_stepper = NumberInputStepper.create
option = Option.create
ordered_list = OrderedList.create
password = Password.create
pin_input = PinInput.create
pin_input_field = PinInputField.create
plotly = Plotly.create
popover = Popover.create
popover_anchor = PopoverAnchor.create
popover_arrow = PopoverArrow.create
popover_body = PopoverBody.create
popover_close_button = PopoverCloseButton.create
popover_content = PopoverContent.create
popover_footer = PopoverFooter.create
popover_header = PopoverHeader.create
popover_trigger = PopoverTrigger.create
progress = Progress.create
radio = Radio.create
radio_group = RadioGroup.create
range_slider = RangeSlider.create
range_slider_filled_track = RangeSliderFilledTrack.create
range_slider_thumb = RangeSliderThumb.create
range_slider_track = RangeSliderTrack.create
responsive_grid = ResponsiveGrid.create
scale_fade = ScaleFade.create
script = Script.create
select = Select.create
skeleton = Skeleton.create
skeleton_circle = SkeletonCircle.create
skeleton_text = SkeletonText.create
slide = Slide.create
slide_fade = SlideFade.create
slider = Slider.create
slider_filled_track = SliderFilledTrack.create
slider_mark = SliderMark.create
slider_thumb = SliderThumb.create
slider_track = SliderTrack.create
spacer = Spacer.create
span = Span.create
spinner = Spinner.create
square = Square.create
stack = Stack.create
stat = Stat.create
stat_arrow = StatArrow.create
stat_group = StatGroup.create
stat_help_text = StatHelpText.create
stat_label = StatLabel.create
stat_number = StatNumber.create
step = Step.create
step_description = StepDescription.create
step_icon = StepIcon.create
step_indicator = StepIndicator.create
step_number = StepNumber.create
step_separator = StepSeparator.create
step_status = StepStatus.create
step_title = StepTitle.create
stepper = Stepper.create
switch = Switch.create
tab = Tab.create
tab_list = TabList.create
tab_panel = TabPanel.create
tab_panels = TabPanels.create
table = Table.create
table_caption = TableCaption.create
table_container = TableContainer.create
tabs = Tabs.create
tag = Tag.create
tag_close_button = TagCloseButton.create
tag_label = TagLabel.create
tag_left_icon = TagLeftIcon.create
tag_right_icon = TagRightIcon.create
tbody = Tbody.create
td = Td.create
text = Text.create
text_area = TextArea.create
tfoot = Tfoot.create
th = Th.create
thead = Thead.create
tooltip = Tooltip.create
tr = Tr.create
unordered_list = UnorderedList.create
upload = Upload.create
video = Video.create
visually_hidden = VisuallyHidden.create
vstack = Vstack.create
wrap = Wrap.create
wrap_item = WrapItem.create
