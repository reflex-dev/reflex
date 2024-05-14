"""Radix themes components."""

from .alert_dialog import alert_dialog as alert_dialog
from .aspect_ratio import aspect_ratio as aspect_ratio
from .avatar import avatar as avatar
from .badge import badge as badge
from .button import button as button
from .callout import callout as callout
from .card import card as card
from .checkbox import checkbox as checkbox
from .checkbox_cards import checkbox_cards as checkbox_cards
from .checkbox_group import checkbox_group as checkbox_group
from .context_menu import context_menu as context_menu
from .data_list import data_list as data_list
from .dialog import dialog as dialog
from .dropdown_menu import dropdown_menu as dropdown_menu
from .dropdown_menu import menu as menu
from .hover_card import hover_card as hover_card
from .icon_button import icon_button as icon_button
from .inset import inset as inset
from .popover import popover as popover
from .progress import progress as progress
from .radio_cards import radio_cards as radio_cards
from .radio_group import radio as radio
from .radio_group import radio_group as radio_group
from .scroll_area import scroll_area as scroll_area
from .segmented_control import segmented_control as segmented_control
from .select import select as select
from .separator import divider as divider
from .separator import separator as separator
from .skeleton import skeleton as skeleton
from .slider import slider as slider
from .spinner import spinner as spinner
from .switch import switch as switch
from .table import table as table
from .tabs import tabs as tabs
from .text_area import text_area as text_area
from .text_field import text_field as text_field
from .tooltip import tooltip as tooltip

input = text_field

__all__ = [
    "alert_dialog",
    "aspect_ratio",
    "avatar",
    "badge",
    "button",
    "callout",
    "card",
    "checkbox",
    "checkbox_cards",
    "checkbox_group",
    "context_menu",
    "data_list",
    "dialog",
    "divider",
    "dropdown_menu",
    "hover_card",
    "icon_button",
    "input",
    "inset",
    "menu",
    "popover",
    # progress is in experimental namespace until https://github.com/radix-ui/themes/pull/492
    # "progress",
    "radio",
    "radio_cards",
    "radio_group",
    "scroll_area",
    "segmented_control",
    "select",
    "separator",
    "skeleton",
    "slider",
    "spinner",
    "switch",
    "table",
    "tabs",
    "text_area",
    "text_field",
    "tooltip",
]
