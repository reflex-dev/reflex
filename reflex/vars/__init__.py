"""Immutable-Based Var System."""

from .base import LiteralVar as LiteralVar
from .base import Var as Var
from .base import VarData as VarData
from .base import get_unique_variable_name as get_unique_variable_name
from .base import get_uuid_string_var as get_uuid_string_var
from .base import var_operation as var_operation
from .base import var_operation_return as var_operation_return
from .function import FunctionStringVar as FunctionStringVar
from .function import FunctionVar as FunctionVar
from .function import VarOperationCall as VarOperationCall
from .number import BooleanVar as BooleanVar
from .number import LiteralBooleanVar as LiteralBooleanVar
from .number import LiteralNumberVar as LiteralNumberVar
from .number import NumberVar as NumberVar
from .object import LiteralObjectVar as LiteralObjectVar
from .object import ObjectVar as ObjectVar
from .sequence import ArrayVar as ArrayVar
from .sequence import ConcatVarOperation as ConcatVarOperation
from .sequence import LiteralArrayVar as LiteralArrayVar
from .sequence import LiteralStringVar as LiteralStringVar
from .sequence import StringVar as StringVar
