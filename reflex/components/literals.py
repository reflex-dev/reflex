"""Literal custom type used by Reflex."""

from typing import Literal

# Base Literals
LiteralInputType = Literal[
    "button",
    "checkbox",
    "color",
    "date",
    "datetime-local",
    "email",
    "file",
    "hidden",
    "image",
    "month",
    "number",
    "password",
    "radio",
    "range",
    "reset",
    "search",
    "submit",
    "tel",
    "text",
    "time",
    "url",
    "week",
]


LiteralRowMarker = Literal["none", "number", "checkbox", "both", "clickable-number"]
