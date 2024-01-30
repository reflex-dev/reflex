"""Radix themes components."""

from .alertdialog import (
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogRoot,
    AlertDialogTitle,
    AlertDialogTrigger,
)
from .aspectratio import AspectRatio
from .avatar import Avatar
from .badge import Badge
from .button import Button
from .callout import Callout, CalloutIcon, CalloutRoot, CalloutText
from .card import Card
from .checkbox import Checkbox, HighLevelCheckbox
from .contextmenu import (
    ContextMenuContent,
    ContextMenuItem,
    ContextMenuRoot,
    ContextMenuSeparator,
    ContextMenuSub,
    ContextMenuSubContent,
    ContextMenuSubTrigger,
    ContextMenuTrigger,
)
from .dialog import (
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogRoot,
    DialogTitle,
    DialogTrigger,
)
from .dropdownmenu import (
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuRoot,
    DropdownMenuSeparator,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
    DropdownMenuTrigger,
)
from .hovercard import HoverCardContent, HoverCardRoot, HoverCardTrigger
from .iconbutton import IconButton
from .icons import Icon
from .inset import Inset
from .popover import PopoverClose, PopoverContent, PopoverRoot, PopoverTrigger
from .radiogroup import HighLevelRadioGroup, RadioGroupItem, RadioGroupRoot
from .scrollarea import ScrollArea
from .select import (
    HighLevelSelect,
    SelectContent,
    SelectGroup,
    SelectItem,
    SelectLabel,
    SelectRoot,
    SelectSeparator,
    SelectTrigger,
)
from .separator import Separator
from .slider import Slider
from .switch import Switch
from .table import (
    TableBody,
    TableCell,
    TableColumnHeaderCell,
    TableHeader,
    TableRoot,
    TableRow,
    TableRowHeaderCell,
)
from .tabs import TabsContent, TabsList, TabsRoot, TabsTrigger
from .textarea import TextArea
from .textfield import Input, TextFieldInput, TextFieldRoot, TextFieldSlot
from .tooltip import Tooltip

# Alert Dialog
alertdialog_root = AlertDialogRoot.create
alertdialog_trigger = AlertDialogTrigger.create
alertdialog_content = AlertDialogContent.create
alertdialog_title = AlertDialogTitle.create
alertdialog_description = AlertDialogDescription.create
alertdialog_action = AlertDialogAction.create
alertdialog_cancel = AlertDialogCancel.create

# Aspect Ratio
aspect_ratio = AspectRatio.create

# Avatar
avatar = Avatar.create

# Badge
badge = Badge.create

# Button
button = Button.create

# Callout
callout_root = CalloutRoot.create
callout_icon = CalloutIcon.create
callout_text = CalloutText.create
callout = Callout.create

# Card
card = Card.create

# Checkbox
checkbox = Checkbox.create
checkbox_hl = HighLevelCheckbox.create

# Context Menu
contextmenu_root = ContextMenuRoot.create
contextmenu_sub = ContextMenuSub.create
contextmenu_trigger = ContextMenuTrigger.create
contextmenu_content = ContextMenuContent.create
contextmenu_sub_content = ContextMenuSubContent.create
contextmenu_sub_trigger = ContextMenuSubTrigger.create
contextmenu_item = ContextMenuItem.create
contextmenu_separator = ContextMenuSeparator.create


# Dialog
dialog_root = DialogRoot.create
dialog_trigger = DialogTrigger.create
dialog_content = DialogContent.create
dialog_title = DialogTitle.create
dialog_description = DialogDescription.create
dialog_close = DialogClose.create

# Dropdown Menu
dropdownmenu_root = DropdownMenuRoot.create
dropdownmenu_trigger = DropdownMenuTrigger.create
dropdownmenu_content = DropdownMenuContent.create
dropdownmenu_sub = DropdownMenuSub.create
dropdownmenu_sub_content = DropdownMenuSubContent.create
dropdownmenu_sub_trigger = DropdownMenuSubTrigger.create
dropdownmenu_item = DropdownMenuItem.create
dropdownmenu_separator = DropdownMenuSeparator.create

# Hover Card
hovercard_root = HoverCardRoot.create
hovercard_trigger = HoverCardTrigger.create
hovercard_content = HoverCardContent.create

# Icon
icon = Icon.create

# Icon Button
icon_button = IconButton.create

# Inset
inset = Inset.create

# Popover
popover_root = PopoverRoot.create
popover_trigger = PopoverTrigger.create
popover_content = PopoverContent.create
popover_close = PopoverClose.create

# Radio Group
radio_group_root = RadioGroupRoot.create
radio_group_item = RadioGroupItem.create
radio_group = HighLevelRadioGroup.create

# Scroll Area
scroll_area = ScrollArea.create

# Select
select_root = SelectRoot.create
select_trigger = SelectTrigger.create
select_content = SelectContent.create
select_item = SelectItem.create
select_separator = SelectSeparator.create
select_group = SelectGroup.create
select_label = SelectLabel.create
select = HighLevelSelect.create

# Separator
separator = Separator.create

# Slider
slider = Slider.create

# Switch
switch = Switch.create

# Table
table_root = TableRoot.create
table_header = TableHeader.create
table_body = TableBody.create
table_row = TableRow.create
table_cell = TableCell.create
table_column_header_cell = TableColumnHeaderCell.create
table_row_header_cell = TableRowHeaderCell.create

# Tabs
tabs_root = TabsRoot.create
tabs_list = TabsList.create
tabs_trigger = TabsTrigger.create
tabs_content = TabsContent.create

# Text Area
textarea = TextArea.create

# Text Field
textfield_root = TextFieldRoot.create
textfield_input = TextFieldInput.create
textfield_slot = TextFieldSlot.create
input = Input.create

# Tooltip
tooltip = Tooltip.create
