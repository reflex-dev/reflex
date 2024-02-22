"""Import all the components."""
from __future__ import annotations

from . import lucide
from .base import Fragment, Script, fragment, script
from .component import Component
from .component import NoSSRComponent as NoSSRComponent
from .core import *
from .datadisplay import *
from .el import img as image
from .gridjs import *
from .markdown import *
from .moment import *
from .next import NextLink, next_link
from .plotly import *
from .radix import *
from .react_player import *
from .suneditor import *

icon = lucide.icon
