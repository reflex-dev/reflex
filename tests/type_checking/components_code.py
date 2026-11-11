"""Props of `reflex_components_code` components that must accept what callers pass."""

from reflex_components_code.code import CodeBlock

# react-syntax-highlighter renders the code unhighlighted for "text", its plain-text language.
CodeBlock.create("$ pip install reflex", language="text")
