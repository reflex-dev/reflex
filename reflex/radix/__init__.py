"""Radix components."""
from .accordion import *
from .alert_dialog import *
from .aspect_ratio import *
from .avatar import *
from .checkbox import *
from .collapsible import *
from .context_menu import *
from .dialog import *
from .dropdown_menu import *
from .hover_card import *
from .label import *
from .menubar import *
from .navigation_menu import *
from .popover import *
from .progress import *
from .radio_group import *
from .select import *
from .separator import *
from .slider import *
from .switch import *
from .tabs import *
from .toast import *
from .toggle_group import *
from .toolbar import *
from .tooltip import *

accordion_root = AccordionRoot.create
accordion_item = AccordionItem.create
accordion_header = AccordionHeader.create
accordion_trigger = AccordionTrigger.create
accordion_content = AccordionContent.create

alert_dialog_root = AlertDialogRoot.create
alert_dialog_trigger = AlertDialogTrigger.create
alert_dialog_portal = AlertDialogPortal.create
alert_dialog_overlay = AlertDialogOverlay.create
alert_dialog_content = AlertDialogContent.create
alert_dialog_cancel = AlertDialogCancel.create
alert_dialog_title = AlertDialogTitle.create
alert_dialog_description = AlertDialogDescription.create
alert_dialog_action = AlertDialogAction.create

aspect_ratio = aspect_ratio_root = AspectRatioRoot.create

avatar_root = AvatarRoot.create
avatar_image = AvatarImage.create
avatar_fallback = AvatarFallback.create

checkbox_root = CheckboxRoot.create
checkbox_indicator = CheckboxIndicator.create

collapsible_root = CollapsibleRoot.create
collapsible_trigger = CollapsibleTrigger.create
collapsible_content = CollapsibleContent.create

context_menu_root = ContextMenuRoot.create
context_menu_trigger = ContextMenuTrigger.create
context_menu_portal = ContextMenuPortal.create
context_menu_content = ContextMenuContent.create
context_menu_arrow = ContextMenuArrow.create
context_menu_item = ContextMenuItem.create
context_menu_group = ContextMenuGroup.create
context_menu_label = ContextMenuLabel.create
context_menu_checkbox_item = ContextMenuCheckboxItem.create
context_menu_radio_group = ContextMenuRadioGroup.create
context_menu_radio_item = ContextMenuRadioItem.create
context_menu_item_indicator = ContextMenuItemIndicator.create
context_menu_separator = ContextMenuSeparator.create
context_menu_sub = ContextMenuSub.create
context_menu_sub_trigger = ContextMenuSubTrigger.create
context_menu_sub_content = ContextMenuSubContent.create

dialog_root = DialogRoot.create
dialog_trigger = DialogTrigger.create
dialog_portal = DialogPortal.create
dialog_overlay = DialogOverlay.create
dialog_content = DialogContent.create
dialog_close = DialogClose.create
dialog_title = DialogTitle.create
dialog_description = DialogDescription.create

dropdown_menu_root = DropdownMenuRoot.create
dropdown_menu_trigger = DropdownMenuTrigger.create
dropdown_menu_portal = DropdownMenuPortal.create
dropdown_menu_content = DropdownMenuContent.create
dropdown_menu_arrow = DropdownMenuArrow.create
dropdown_menu_item = DropdownMenuItem.create
dropdown_menu_group = DropdownMenuGroup.create
dropdown_menu_label = DropdownMenuLabel.create
dropdown_menu_checkbox_item = DropdownMenuCheckboxItem.create
dropdown_menu_radio_group = DropdownMenuRadioGroup.create
dropdown_menu_radio_item = DropdownMenuRadioItem.create
dropdown_menu_item_indicator = DropdownMenuItemIndicator.create
dropdown_menu_separator = DropdownMenuSeparator.create
dropdown_menu_sub = DropdownMenuSub.create
dropdown_menu_sub_trigger = DropdownMenuSubTrigger.create
dropdown_menu_sub_content = DropdownMenuSubContent.create

hover_card_root = HoverCardRoot.create
hover_card_trigger = HoverCardTrigger.create
hover_card_portal = HoverCardPortal.create
hover_card_content = HoverCardContent.create
hover_card_arrow = HoverCardArrow.create

label_root = LabelRoot.create

menubar_root = MenubarRoot.create
menubar_menu = MenubarMenu.create
menubar_trigger = MenubarTrigger.create
menubar_portal = MenubarPortal.create
menubar_content = MenubarContent.create
menubar_arrow = MenubarArrow.create
menubar_item = MenubarItem.create
menubar_group = MenubarGroup.create
menubar_label = MenubarLabel.create
menubar_checkbox_item = MenubarCheckboxItem.create
menubar_radio_group = MenubarRadioGroup.create
menubar_radio_item = MenubarRadioItem.create
menubar_item_indicator = MenubarItemIndicator.create
menubar_separator = MenubarSeparator.create
menubar_sub = MenubarSub.create
menubar_sub_trigger = MenubarSubTrigger.create
menubar_sub_content = MenubarSubContent.create

navigation_menu_root = NavigationMenuRoot.create
navigation_menu_sub = NavigationMenuSub.create
navigation_menu_list = NavigationMenuList.create
navigation_menu_item = NavigationMenuItem.create
navigation_menu_trigger = NavigationMenuTrigger.create
navigation_menu_content = NavigationMenuContent.create
navigation_menu_link = NavigationMenuLink.create
navigation_menu_indicator = NavigationMenuIndicator.create
navigation_menu_viewport = NavigationMenuViewport.create

popover_root = PopoverRoot.create
popover_trigger = PopoverTrigger.create
popover_anchor = PopoverAnchor.create
popover_portal = PopoverPortal.create
popover_content = PopoverContent.create
popover_arrow = PopoverArrow.create
popover_close = PopoverClose.create

progress_root = ProgressRoot.create
progress_indicator = ProgressIndicator.create

radio_group_root = RadioGroupRoot.create
radio_group_item = RadioGroupItem.create
radio_group_indicator = RadioGroupIndicator.create

select_root = SelectRoot.create
select_trigger = SelectTrigger.create
select_content = SelectContent.create
select_value = SelectValue.create
select_icon = SelectIcon.create
select_portal = SelectPortal.create
select_viewport = SelectViewport.create
select_group = SelectGroup.create
select_item = SelectItem.create
select_label = SelectLabel.create
select_separator = SelectSeparator.create
select_item_text = SelectItemText.create
select_item_indicator = SelectItemIndicator.create
select_scroll_up_button = SelectScrollUpButton.create
select_scroll_down_button = SelectScrollDownButton.create
select_arrow = SelectArrow.create

separator = separator_root = Separator.create

slider_root = SliderRoot.create
slider_track = SliderTrack.create
slider_range = SliderRange.create
slider_thumb = SliderThumb.create

switch_root = SwitchRoot.create
switch_thumb = SwitchThumb.create

tabs_root = TabsRoot.create
tabs_list = TabsList.create
tabs_trigger = TabsTrigger.create
tabs_content = TabsContent.create

toast_provider = ToastProvider.create
toast_viewport = ToastViewport.create
toast_root = ToastRoot.create
toast_title = ToastTitle.create
toast_description = ToastDescription.create
toast_close = ToastClose.create
toast_action = ToastAction.create

toggle_group_root = ToggleGroupRoot.create
toggle_group_item = ToggleGroupItem.create

toolbar_root = ToolbarRoot.create
toolbar_button = ToolbarButton.create
toolbar_link = ToolbarLink.create
toolbar_separator = ToolbarSeparator.create
toolbar_toggle_group = ToolbarToggleGroup.create
toolbar_toggle_item = ToolbarToggleItem.create

tooltip_provider = TooltipProvider.create
tooltip_root = TooltipRoot.create
tooltip_trigger = TooltipTrigger.create
tooltip_content = TooltipContent.create
tooltip_portal = TooltipPortal.create
tooltip_arrow = TooltipArrow.create
