"""Namespace for components provided by the @radix-ui/themes library."""
from .base import (
    Theme,
    ThemePanel,
)
from .components import (
    Button,
    Switch,
    TextField,
    TextFieldRoot,
    TextFieldSlot,
)
from .layout import (
    Box,
    Container,
    Flex,
    Grid,
    Section,
)
from .typography import Blockquote, Code, Em, Heading, Kbd, Link, Quote, Strong, Text

blockquote = Blockquote.create
box = Box.create
button = Button.create
code = Code.create
container = Container.create
em = Em.create
flex = Flex.create
grid = Grid.create
heading = Heading.create
kbd = Kbd.create
link = Link.create
quote = Quote.create
section = Section.create
strong = Strong.create
switch = Switch.create
text = Text.create
text_field = TextField.create
text_field_root = TextFieldRoot.create
text_field_slot = TextFieldSlot.create
theme = Theme.create
theme_panel = ThemePanel.create
