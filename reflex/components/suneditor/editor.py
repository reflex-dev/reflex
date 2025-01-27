"""A Rich Text Editor based on SunEditor."""

from __future__ import annotations

import enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from reflex.base import Base
from reflex.components.component import Component, NoSSRComponent
from reflex.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex.utils.format import to_camel_case
from reflex.utils.imports import ImportDict, ImportVar
from reflex.vars.base import Var


class EditorButtonList(list, enum.Enum):
    """List enum that provides three predefined button lists."""

    BASIC = [
        ["font", "fontSize"],
        ["fontColor"],
        ["horizontalRule"],
        ["link", "image"],
    ]
    FORMATTING = [
        ["undo", "redo"],
        ["bold", "underline", "italic", "strike", "subscript", "superscript"],
        ["removeFormat"],
        ["outdent", "indent"],
        ["fullScreen", "showBlocks", "codeView"],
        ["preview", "print"],
    ]
    COMPLEX = [
        ["undo", "redo"],
        ["font", "fontSize", "formatBlock"],
        ["bold", "underline", "italic", "strike", "subscript", "superscript"],
        ["removeFormat"],
        "/",
        ["fontColor", "hiliteColor"],
        ["outdent", "indent"],
        ["align", "horizontalRule", "list", "table"],
        ["link", "image", "video"],
        ["fullScreen", "showBlocks", "codeView"],
        ["preview", "print"],
        ["save", "template"],
    ]


class EditorOptions(Base):
    """Some of the additional options to configure the Editor.
    Complete list of options found here:
    https://github.com/JiHong88/SunEditor/blob/master/README.md#options.
    """

    # Specifies default tag name of the editor.
    # default: 'p' {String}
    default_tag: Optional[str] = None

    # The mode of the editor ('classic', 'inline', 'balloon', 'balloon-always').
    # default: 'classic' {String}
    mode: Optional[str] = None

    # If true, the editor is set to RTL(Right To Left) mode.
    # default: false {Boolean}
    rtl: Optional[bool] = None

    # List of buttons to use in the toolbar.
    button_list: Optional[List[Union[List[str], str]]]


def on_blur_spec(e: Var, content: Var[str]) -> Tuple[Var[str]]:
    """A helper function to specify the on_blur event handler.

    Args:
        e: The event.
        content: The content of the editor.

    Returns:
        A tuple containing the content of the editor.
    """
    return (content,)


def on_paste_spec(
    e: Var, clean_data: Var[str], max_char_count: Var[bool]
) -> Tuple[Var[str], Var[bool]]:
    """A helper function to specify the on_paste event handler.

    Args:
        e: The event.
        clean_data: The clean data.
        max_char_count: The maximum character count.

    Returns:
        A tuple containing the clean data and the maximum character count.
    """
    return (clean_data, max_char_count)


class Editor(NoSSRComponent):
    """A Rich Text Editor component based on SunEditor.
    Not every JS prop is listed here (some are not easily usable from python),
    refer to the library docs for a complete list.
    """

    library = "suneditor-react"

    tag = "SunEditor"

    is_default = True

    lib_dependencies: List[str] = ["suneditor"]

    # Language of the editor.
    # Alternatively to a string, a dict of your language can be passed to this prop.
    # Please refer to the library docs for this.
    # options: "en" | "da" | "de" | "es" | "fr" | "ja" | "ko" | "pt_br" |
    # "ru" | "zh_cn" | "ro" | "pl" | "ckb" | "lv" | "se" | "ua" | "he" | "it"
    # default: "en".
    lang: Var[
        Union[
            Literal[
                "en",
                "da",
                "de",
                "es",
                "fr",
                "ja",
                "ko",
                "pt_br",
                "ru",
                "zh_cn",
                "ro",
                "pl",
                "ckb",
                "lv",
                "se",
                "ua",
                "he",
                "it",
            ],
            dict,
        ]
    ]

    # This is used to set the HTML form name of the editor.
    # This means on HTML form submission,
    # it will be submitted together with contents of the editor by the name provided.
    name: Var[str]

    # Sets the default value of the editor.
    # This is useful if you don't want the on_change method to be called on render.
    # If you want the on_change method to be called on render please use the set_contents prop
    default_value: Var[str]

    # Sets the width of the editor.
    # px and percentage values are accepted, eg width="100%" or width="500px"
    # default: 100%
    width: Var[str]

    # Sets the height of the editor.
    # px and percentage values are accepted, eg height="100%" or height="100px"
    height: Var[str]

    # Sets the placeholder of the editor.
    placeholder: Var[str]

    # Should the editor receive focus when initialized?
    auto_focus: Var[bool]

    # Pass an EditorOptions instance to modify the behaviour of Editor even more.
    set_options: Var[Dict]

    # Whether all SunEditor plugins should be loaded.
    # default: True.
    set_all_plugins: Var[bool]

    # Set the content of the editor.
    # Note: To set the initial contents of the editor
    # without calling the on_change event,
    # please use the default_value prop.
    # set_contents is used to set the contents of the editor programmatically.
    # You must be aware that, when the set_contents's prop changes,
    # the on_change event is triggered.
    set_contents: Var[str]

    # Append editor content
    append_contents: Var[str]

    # Sets the default style of the editor's edit area
    set_default_style: Var[str]

    # Disable the editor
    # default: False.
    disable: Var[bool]

    # Hide the editor
    # default: False.
    hide: Var[bool]

    # Hide the editor toolbar
    # default: False.
    hide_toolbar: Var[bool]

    # Disable the editor toolbar
    # default: False.
    disable_toolbar: Var[bool]

    # Fired when the editor content changes.
    on_change: EventHandler[passthrough_event_spec(str)]

    # Fired when the something is inputted in the editor.
    on_input: EventHandler[no_args_event_spec]

    # Fired when the editor loses focus.
    on_blur: EventHandler[on_blur_spec]

    # Fired when the editor is loaded.
    on_load: EventHandler[passthrough_event_spec(bool)]

    # Fired when the editor content is copied.
    on_copy: EventHandler[no_args_event_spec]

    # Fired when the editor content is cut.
    on_cut: EventHandler[no_args_event_spec]

    # Fired when the editor content is pasted.
    on_paste: EventHandler[on_paste_spec]

    # Fired when the code view is toggled.
    toggle_code_view: EventHandler[passthrough_event_spec(bool)]

    # Fired when the full screen mode is toggled.
    toggle_full_screen: EventHandler[passthrough_event_spec(bool)]

    def add_imports(self) -> ImportDict:
        """Add imports for the Editor component.

        Returns:
            The import dict.
        """
        return {
            "": ImportVar(tag="suneditor/dist/css/suneditor.min.css", install=False)
        }

    @classmethod
    def create(
        cls, set_options: Optional[EditorOptions] = None, **props: Any
    ) -> Component:
        """Create an instance of Editor. No children allowed.

        Args:
            set_options: Configuration object to further configure the instance.
            **props: Any properties to be passed to the Editor

        Returns:
            An Editor instance.

        Raises:
            ValueError: If set_options is a state Var.
        """
        if set_options is not None:
            if isinstance(set_options, Var):
                raise ValueError("EditorOptions cannot be a state Var")
            props["set_options"] = {
                to_camel_case(k): v
                for k, v in set_options.dict().items()
                if v is not None
            }
        return super().create(*[], **props)
