---
order: 3
---

```python exec
import reflex as rx
import reflex_enterprise as rxe
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

    @rx.event
    def set_theme(self, value: str):
        self.theme = value


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
            rx.select(
                AGGridThemeState.themes,
                value=AGGridThemeState.theme,
                on_change=AGGridThemeState.set_theme,
            ),
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

## Customizing a Theme with CSS

The `theme` prop maps directly to one of AG Grid's built-in theme classes, which `reflex-enterprise` applies on the grid root element:

- `theme="quartz"` → `.ag-theme-quartz`
- `theme="balham"` → `.ag-theme-balham`
- `theme="alpine"` → `.ag-theme-alpine`
- `theme="material"` → `.ag-theme-material`

Each theme also has a dark variant (`.ag-theme-quartz-dark`, `.ag-theme-balham-dark`, etc.). The dark variant is only applied when the corresponding theme name is selected; listing both light and dark class selectors in your CSS lets the same overrides apply in either mode.

You can customize any theme by overriding the AG Grid CSS variables (the `--ag-*` custom properties) and by writing rules that target AG Grid's built-in classes. The full list of available variables is documented in the [AG Grid theming reference](https://www.ag-grid.com/javascript-data-grid/global-style-customisation-variables/).

### CSS Variables

AG Grid exposes most visual properties as CSS variables. Commonly customized ones:

- Typography: `--ag-font-family`, `--ag-font-size`
- Density and shape: `--ag-grid-size` (base unit), `--ag-border-radius`, `--ag-wrapper-border-radius`, `--ag-cell-horizontal-padding`
- Borders: `--ag-border-color`, `--ag-row-border-color`
- Backgrounds: `--ag-background-color`, `--ag-odd-row-background-color`, `--ag-row-hover-color`
- Headers: `--ag-header-background-color`, `--ag-header-foreground-color`, `--ag-header-column-separator-color`
- Accents (selection / focus): `--ag-accent-color`, `--ag-selected-row-background-color`, `--ag-range-selection-background-color`, `--ag-input-focus-border-color`, `--ag-checkbox-checked-color`

### Scoping Overrides with a Wrapper Class

If you have multiple grids on a page, scope your overrides to a parent class so they don't leak to other grids. Wrap the grid in an `rx.box` (or any element) with a class such as `custom-ag-grid`, then target the theme class _inside_ that wrapper in your CSS:

```python
rx.box(
    rxe.ag_grid(
        id="my_themed_grid",
        row_data=df.to_dict("records"),
        column_defs=column_defs,
        theme="quartz",
        width="100%",
        height="40vh",
    ),
    class_name="custom-ag-grid",
)
```

```css
/* assets/ag_grid_theme.css */

/*
 * Custom ag-grid theme overrides.
 *
 * reflex-enterprise applies the built-in theme as a class on the grid root.
 * Scope overrides to a parent `.custom-ag-grid` container so they don't leak
 * to other grids on the page.
 */

.custom-ag-grid .ag-theme-quartz,
.custom-ag-grid .ag-theme-quartz-dark,
.custom-ag-grid .ag-theme-balham,
.custom-ag-grid .ag-theme-balham-dark,
.custom-ag-grid .ag-theme-alpine,
.custom-ag-grid .ag-theme-alpine-dark,
.custom-ag-grid .ag-theme-material,
.custom-ag-grid .ag-theme-material-dark {
    --ag-font-family: "Inter", ui-sans-serif, system-ui, sans-serif;
    --ag-font-size: 13px;

    --ag-grid-size: 6px;
    --ag-border-radius: 12px;
    --ag-wrapper-border-radius: 12px;

    --ag-background-color: #ffffff;
    --ag-odd-row-background-color: #fafbfd;
    --ag-row-hover-color: #f1f5f9;

    --ag-header-background-color: #eef2ff;
    --ag-header-foreground-color: #1e293b;

    --ag-accent-color: #3b82f6;
    --ag-selected-row-background-color: #dbeafe;
    --ag-input-focus-border-color: #3b82f6;
    --ag-checkbox-checked-color: #3b82f6;

    --ag-cell-horizontal-padding: 16px;
}

/* Stronger header typography. */
.custom-ag-grid .ag-header-cell-text {
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-size: 11px;
}
```

Listing every theme variant in the selector keeps the overrides applied no matter which built-in theme is selected at runtime, including its dark variant.

### Loading the Stylesheet

Place your CSS file under `assets/` and add it to the `stylesheets` list on your `rxe.App` (or `rx.App`):

```python
app = rxe.App(
    stylesheets=["/ag_grid_theme.css"],
)
```

The path is relative to `assets/`, so `assets/ag_grid_theme.css` is referenced as `/ag_grid_theme.css`.

### Overriding CSS Variables Inline via `style`

For one-off tweaks you don't need a separate stylesheet — you can set `--ag-*` variables directly in the `style` dict on the grid:

```python
rxe.ag_grid(
    id="comic_grid",
    row_data=df.to_dict("records"),
    column_defs=column_defs,
    theme="quartz",
    style={
        "--ag-font-family": "Comic Sans MS !important",
        "--ag-font-size": "14px !important",
    },
    width="100%",
    height="40vh",
)
```

```md alert warning
# CSS variable inheritance and `!important`
Inline `style` sets the variable on the grid root element only. The built-in themes bind their styling to multiple CSS classes (`.ag-theme-quartz`, `.ag-theme-quartz .ag-cell`, etc.), and those rules often have higher specificity than a custom property defined inline. As a result, a value set via `style={"--ag-font-family": "..."}` may be ignored unless you append `!important`. If your inline override doesn't take effect, add `!important` or move the override into a stylesheet that targets the theme class with comparable specificity.

Inline `style` overrides only apply to the grid they are set on. To customize multiple grids consistently, prefer a stylesheet scoped to a wrapper class (see above).
```

## Per-Cell Custom Classes

Built-in themes style the grid as a whole. To highlight individual cells based on their value, attach custom CSS classes via the `cellClass` and `cellClassRules` column-def keys, then style those classes in your stylesheet.

- `cellClass` always applies the listed class(es) to every cell in the column.
- `cellClassRules` is a mapping of `class name -> JS expression`; the class is applied when the expression evaluates truthy. The cell's value is available as `params.value`.

```python
column_defs = [
    {"field": "project"},
    {
        "field": "status",
        "cellClass": "status-pill",
        "cellClassRules": {
            "status-active": "params.value === 'Active'",
            "status-blocked": "params.value === 'Blocked'",
            "status-complete": "params.value === 'Complete'",
            "status-planning": "params.value === 'Planning'",
        },
    },
]
```

```css
/* assets/ag_grid_theme.css */

.custom-ag-grid .status-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
}

.custom-ag-grid .status-active   { color: #047857; }
.custom-ag-grid .status-blocked  { color: #b91c1c; }
.custom-ag-grid .status-complete { color: #1d4ed8; }
.custom-ag-grid .status-planning { color: #a16207; }
```

The same approach works for header cells (`headerClass`) and rows (`rowClass` / `rowClassRules` on the grid itself).
