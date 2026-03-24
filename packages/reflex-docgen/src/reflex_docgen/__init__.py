"""Module for generating documentation for Reflex components and classes."""

from reflex_docgen._class import ClassDocumentation as ClassDocumentation
from reflex_docgen._class import FieldDocumentation as FieldDocumentation
from reflex_docgen._class import MethodDocumentation as MethodDocumentation
from reflex_docgen._class import (
    generate_class_documentation as generate_class_documentation,
)
from reflex_docgen._component import ComponentDocumentation as ComponentDocumentation
from reflex_docgen._component import (
    EventHandlerDocumentation as EventHandlerDocumentation,
)
from reflex_docgen._component import PropDocumentation as PropDocumentation
from reflex_docgen._component import generate_documentation as generate_documentation
from reflex_docgen._component import (
    get_component_event_handlers as get_component_event_handlers,
)
from reflex_docgen._component import get_component_props as get_component_props
from reflex_docgen._markdown import Block as Block
from reflex_docgen._markdown import BoldSpan as BoldSpan
from reflex_docgen._markdown import CodeBlock as CodeBlock
from reflex_docgen._markdown import CodeSpan as CodeSpan
from reflex_docgen._markdown import DirectiveBlock as DirectiveBlock
from reflex_docgen._markdown import Document as Document
from reflex_docgen._markdown import FrontMatter as FrontMatter
from reflex_docgen._markdown import HeadingBlock as HeadingBlock
from reflex_docgen._markdown import ImageSpan as ImageSpan
from reflex_docgen._markdown import ItalicSpan as ItalicSpan
from reflex_docgen._markdown import LinkSpan as LinkSpan
from reflex_docgen._markdown import Span as Span
from reflex_docgen._markdown import StrikethroughSpan as StrikethroughSpan
from reflex_docgen._markdown import TextBlock as TextBlock
from reflex_docgen._markdown import TextSpan as TextSpan
from reflex_docgen._markdown import parse_document as parse_document

__all__ = [
    "Block",
    "BoldSpan",
    "ClassDocumentation",
    "CodeBlock",
    "CodeSpan",
    "ComponentDocumentation",
    "DirectiveBlock",
    "Document",
    "EventHandlerDocumentation",
    "FieldDocumentation",
    "FrontMatter",
    "HeadingBlock",
    "ImageSpan",
    "ItalicSpan",
    "LinkSpan",
    "MethodDocumentation",
    "PropDocumentation",
    "Span",
    "StrikethroughSpan",
    "TextBlock",
    "TextSpan",
    "generate_class_documentation",
    "generate_documentation",
    "get_component_event_handlers",
    "get_component_props",
    "parse_document",
]
