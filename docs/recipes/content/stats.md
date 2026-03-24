```python exec
import reflex as rx
```

# Stats

Stats cards are used to display key metrics or data points. They are typically used in dashboards or admin panels.

## Variant 1

```python demo exec toggle
from reflex.components.radix.themes.base import LiteralAccentColor

def stats(stat_name: str = "Users", value: int = 4200, prev_value: int = 3000, icon: str = "users", badge_color: LiteralAccentColor = "blue") -> rx.Component:
	percentage_change = round(((value - prev_value) / prev_value) * 100, 2) if prev_value != 0 else 0 if value == 0 else float('inf')
	change = "increase" if value > prev_value else "decrease"
	arrow_icon = "trending-up" if value > prev_value else "trending-down"
	arrow_color = "grass" if value > prev_value else "tomato"
	return rx.card(
		rx.vstack(
			rx.hstack(
				rx.badge(
					rx.icon(tag=icon, size=34),
					color_scheme=badge_color,
					radius="full",
					padding="0.7rem"
				),
				rx.vstack(
					rx.heading(f"{value:,}", size="6", weight="bold"),
					rx.text(stat_name, size="4", weight="medium"),
					spacing="1",
					height="100%",
					align_items="start",
					width="100%"
				),
				height="100%",
				spacing="4",
				align="center",
				width="100%",
			),
			rx.hstack(
				rx.hstack(
					rx.icon(tag=arrow_icon, size=24, color=rx.color(arrow_color, 9)),
					rx.text(f"{percentage_change}%", size="3", color=rx.color(arrow_color, 9), weight="medium"),
					spacing="2",
					align="center",
				),
				rx.text(f"{change} from last month", size="2", color=rx.color("gray", 10)),
				align="center",
				width="100%",
			),
			spacing="3",
		),
		size="3",
		width="100%",
		max_width="21rem"
	)
```

## Variant 2

```python demo exec toggle
from reflex.components.radix.themes.base import LiteralAccentColor

def stats_2(stat_name: str = "Orders", value: int = 6500, prev_value: int = 12000, icon: str = "shopping-cart", icon_color: LiteralAccentColor = "pink") -> rx.Component:
	percentage_change = round(((value - prev_value) / prev_value) * 100, 2) if prev_value != 0 else 0 if value == 0 else float('inf')
	arrow_icon = "trending-up" if value > prev_value else "trending-down"
	arrow_color = "grass" if value > prev_value else "tomato"
	return rx.card(
		rx.hstack(
			rx.vstack(
				rx.hstack(
                    rx.hstack(
                        rx.icon(tag=icon, size=22, color=rx.color(icon_color, 11)),
                        rx.text(stat_name, size="4", weight="medium", color=rx.color("gray", 11)),
                        spacing="2",
                        align="center",
                    ),
                    rx.badge(
                        rx.icon(tag=arrow_icon, color=rx.color(arrow_color, 9)),
                        rx.text(f"{percentage_change}%", size="2", color=rx.color(arrow_color, 9), weight="medium"),
                        color_scheme=arrow_color,
                        radius="large",
                        align_items="center",
                    ),
                    justify="between",
                    width="100%",
                ),
				rx.hstack(
					rx.heading(f"{value:,}", size="7", weight="bold"),
					rx.text(f"from {prev_value:,}", size="3", color=rx.color("gray", 10)),
					spacing="2",
					align_items="end",
				),
				align_items="start",
				justify="between",
				width="100%",
			),
			align_items="start",
			width="100%",
			justify="between",
		),
		size="3",
		width="100%",
		max_width="21rem",
	)
```