# AG Chart

AG Chart is a powerful charting library that provides interactive charts and data visualization components for enterprise applications.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe


def basic_chart():
    return rxe.ag_chart(
        options={
            "data": [
                {"month": "Jan", "value": 10},
                {"month": "Feb", "value": 20},
                {"month": "Mar", "value": 15},
            ],
            "series": [
                {
                    "type": "line",
                    "xKey": "month",
                    "yKey": "value",
                }
            ],
        },
        width="100%",
        height="400px",
    )
```

```python test
def test_line_chart_renders(demo):
    expect(demo.get_by_role("figure", name="chart, 1 series")).to_be_visible()
    expect(demo.locator("canvas").first).to_be_visible()
```

For more detailed documentation, see the [AG Chart Documentation](https://charts.ag-grid.com/).
