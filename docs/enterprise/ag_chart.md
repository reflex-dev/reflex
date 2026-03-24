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

For more detailed documentation, see the [AG Chart Documentation](https://charts.ag-grid.com/).
