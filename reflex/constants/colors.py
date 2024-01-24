"""The colors used in Reflex are a wrapper around https://www.radix-ui.com/colors."""
from typing import Literal

ColorType= Literal[
        "gray",
        "mauve",
        "slate",
        "sage",
        "olive",
        "sand",
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

ShadeType= Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]


class Colors:
    def __init__(self, color: ColorType, shade: ShadeType, alpha: bool = False) -> None:
        self.color = color
        self.shade = shade
        self.alpha = alpha

    def __str__(self) -> str:
        if self.alpha:
            return f"--{self.color}-{self.shade}-alpha"
        else:
            return f"--var({self.color}-{self.shade})"

        

    

    
    
