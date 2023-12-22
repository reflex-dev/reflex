import reflex as rx
from reflex.components.radix.themes.components import *
from reflex.components.radix.themes.typography import *
from reflex.components.radix.themes.layout import *
import reflex.components.radix.themes as rdxt


class RadixDocState(rx.State):
    """The app state."""

    color: str = "red"

    def change_color(self, color: str) -> None:
        self.color = color


def hover_item(component: rx.Component, component_str: str) -> rx.Component:
    return hovercard_root(
        hovercard_trigger(flex(component)),
        hovercard_content(
            rx.code_block(f"{component_str}", can_copy=True, language="python"),
        ),
    )


def dict_to_formatted_string(input_dict):
    # List to hold formatted string parts
    formatted_parts = []

    # Iterate over dictionary items
    for key, value in input_dict.items():
        # Format each key-value pair
        if isinstance(value, str):
            formatted_part = f'{key}="{value}"'  # Enclose string values in quotes
        else:
            formatted_part = f'{key}={value}'  # Non-string values as is

        # Append the formatted part to the list
        formatted_parts.append(formatted_part)

    # Join all parts with a comma and a space
    return ', '.join(formatted_parts)


def used_component(component_used: rx.Component, components_passed: rx.Component | str | None, color_scheme: str, variant: str, high_contrast: bool, disabled: bool = False, **kwargs) -> rx.Component:
        
        if components_passed == None and disabled == False:
            return component_used(color_scheme=color_scheme, variant=variant, high_contrast=high_contrast, **kwargs)
        
        elif components_passed != None and disabled == False:
            return component_used(components_passed, color_scheme=color_scheme, variant=variant, high_contrast=high_contrast, **kwargs)
        
        elif components_passed == None and disabled == True:
            return component_used(color_scheme=color_scheme, variant=variant, high_contrast=high_contrast, disabled=True, **kwargs)
        
        else: 
            return component_used(components_passed, color_scheme=color_scheme, variant=variant, high_contrast=high_contrast, disabled=True, **kwargs)



def style_grid(component_used: rx.Component, component_used_str: str, variants: list, components_passed: rx.Component | str | None = None, disabled: bool = False, **kwargs) -> rx.Component:
     return rx.vstack(
                    grid(
                        text("", size="5"),
                        *[
                            text(variant, size="5") for variant in variants
                        ],
                        text("Accent", size="5"),
                        *[
                            hover_item(
                                component=used_component(
                                    component_used=component_used,
                                    components_passed=components_passed,
                                    color_scheme=RadixDocState.color,
                                    variant=variant,
                                    high_contrast=False,
                                    **kwargs,
                                ),
                                component_str=f"{component_used_str}(color_scheme={RadixDocState.color}, variant={variant}, high_contrast=False, {dict_to_formatted_string(kwargs)})",
                            )
                            for variant in variants
                        ],
                        text("", size="5"),
                        *[
                            hover_item(
                                component=used_component(
                                component_used=component_used,
                                components_passed=components_passed,
                                color_scheme=RadixDocState.color,
                                variant=variant,
                                high_contrast=True,
                                **kwargs,
                                ),
                                component_str=f"{component_used_str}(color_scheme={RadixDocState.color}, variant={variant}, high_contrast=True, {dict_to_formatted_string(kwargs)})",
                            )
                            for variant in variants
                        ],
                        text("Gray", size="5"),
                        *[
                            hover_item(
                                component=used_component(
                                component_used=component_used,
                                components_passed=components_passed,
                                color_scheme="gray",
                                variant=variant,
                                high_contrast=False,
                                **kwargs,
                                ),
                                component_str=f"{component_used_str}(color_scheme={RadixDocState.color}, variant={variant}, high_contrast=False, {dict_to_formatted_string(kwargs)})",
                            )
                            for variant in variants
                        ],
                        text("", size="5"),
                        *[
                            hover_item(
                                component=used_component(
                                component_used=component_used,
                                components_passed=components_passed,
                                color_scheme="gray",
                                variant=variant,
                                high_contrast=True,
                                **kwargs,
                                ),
                                component_str=f"{component_used_str}(color_scheme={RadixDocState.color}, variant={variant}, high_contrast=True, {dict_to_formatted_string(kwargs)})",
                            )
                            for variant in variants
                        ],
                        (rx.fragment(text("Disabled", size="5"),
                        *[
                            hover_item(
                                component=used_component(
                                component_used=component_used,
                                components_passed=components_passed,
                                color_scheme="gray",
                                variant=variant,
                                high_contrast=True,
                                disabled=disabled,
                                **kwargs,
                                ),
                                component_str=f"{component_used_str}(color_scheme={RadixDocState.color}, variant={variant}, disabled=True, {dict_to_formatted_string(kwargs)})",
                            )
                            for variant in variants
                        ]) if disabled else ""),
                        
                        
                     
                        flow="column",
                        columns="5",
                        rows=str(len(variants) + 1),
                        gap="3",
                    ),

                    select_root(
                        select_trigger(button(size="2", on_click=RadixDocState.change_color())),
                        select_content(
                            select_group(
                                select_label("Colors"),
                                *[
                                    select_item(
                                        color,
                                        value=color,
                                        _hover={"background": f"var(--{color}-9)"},
                                    )
                                    for color in [
                                        "tomato",
                                        "red",
                                        "ruby",
                                        "crimson",
                                        "pink",
                                        "plum",
                                        "purple",
                                        "violet",
                                        "iris",
                                        "indigo",
                                        "blue",
                                        "cyan",
                                        "teal",
                                        "jade",
                                        "green",
                                        "grass",
                                        "brown",
                                        "orange",
                                        "sky",
                                        "mint",
                                        "lime",
                                        "yellow",
                                        "amber",
                                        "gold",
                                        "bronze",
                                        "gray",
                                    ]
                                ],
                            ),
                        ),
                        ## we need to clearly document how the on_value_change works as it is not obvious at all
                        default_value=RadixDocState.color,
                        on_value_change=RadixDocState.change_color,
                    ),
                )
