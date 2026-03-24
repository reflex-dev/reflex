---
order: 3
---

```python exec
import reflex as rx
import reflex_enterprise as rxe
from pcweb.pages.docs import enterprise
```

# Themes

```md alert warning
# Only the old theme API of AG Grid is currently supported. The new theme API is not supported yet.
```

You can style your grid with a theme. AG Grid includes the following themes:

1. `quartz`
2. `alpine`
3. `balham`
4. `material`

The grid uses `quartz` by default. To use any other theme, set it using the `theme` prop, i.e. `theme="alpine"`.

```python
import reflex as rx
import reflex_enterprise as rxe
import pandas as pd

class AGGridThemeState(rx.State):
    """The app state."""

    theme: str = "quartz"
    themes: list[str] = ["quartz", "balham", "alpine", "material"]

df = pd.read_csv("data/gapminder2007.csv")

column_defs = [
    {"field": "country"},
    {"field": "pop", "headerName": "Population"},
    {"field": "lifeExp", "headerName": "Life Expectancy"},
]

def ag_grid_simple_themes():
    return rx.vstack(
        rx.hstack(
            rx.text("Theme:"),
            rx.select(AGGridThemeState.themes, value=AGGridThemeState.theme, on_change=AGGridThemeState.set_theme),
        ),
        rxe.ag_grid(
            id="ag_grid_basic_themes",
            row_data=df.to_dict("records"),
            column_defs=column_defs,
            theme=AGGridThemeState.theme,
            width="100%",
            height="40vh",
        ),
        width="100%",
    )
```

📊 **Dataset source:** [gapminder2007.csv](https://raw.githubusercontent.com/plotly/datasets/master/gapminder2007.csv)