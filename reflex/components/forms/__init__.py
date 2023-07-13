"""Convenience functions to define core components."""

from .button import Button, ButtonGroup
from .checkbox import Checkbox, CheckboxGroup
from .colormodeswitch import (
    ColorModeButton,
    ColorModeIcon,
    ColorModeSwitch,
    color_mode_cond,
)
from .copytoclipboard import CopyToClipboard
from .date_picker import DatePicker
from .date_time_picker import DateTimePicker
from .debounce import DebounceInput
from .editable import Editable, EditableInput, EditablePreview, EditableTextarea
from .email import Email
from .form import Form, FormControl, FormErrorMessage, FormHelperText, FormLabel
from .iconbutton import IconButton
from .input import (
    Input,
    InputGroup,
    InputLeftAddon,
    InputLeftElement,
    InputRightAddon,
    InputRightElement,
)
from .multiselect import Option as MultiSelectOption
from .multiselect import Select as MultiSelect
from .numberinput import (
    NumberDecrementStepper,
    NumberIncrementStepper,
    NumberInput,
    NumberInputField,
    NumberInputStepper,
)
from .password import Password
from .pininput import PinInput, PinInputField
from .radio import Radio, RadioGroup
from .rangeslider import (
    RangeSlider,
    RangeSliderFilledTrack,
    RangeSliderThumb,
    RangeSliderTrack,
)
from .select import Option, Select
from .slider import Slider, SliderFilledTrack, SliderMark, SliderThumb, SliderTrack
from .switch import Switch
from .textarea import TextArea
from .upload import Upload

helpers = [
    "color_mode_cond",
]

__all__ = [f for f in dir() if f[0].isupper()] + helpers  # type: ignore
