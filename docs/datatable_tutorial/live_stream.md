```python exec
import reflex as rx
from docs.datatable_tutorial.datatable_tutorial_utils import DataTableLiveState

darkTheme = {
    "accentColor": "#8c96ff",
    "accentLight": "rgba(202, 206, 255, 0.253)",
    "textDark": "#ffffff",
    "textMedium": "#b8b8b8",
    "textLight": "#a0a0a0",
    "textBubble": "#ffffff",
    "bgIconHeader": "#b8b8b8",
    "fgIconHeader": "#000000",
    "textHeader": "#a1a1a1",
    "textHeaderSelected": "#000000",
    "bgCell": "#16161b",
    "bgCellMedium": "#202027",
    "bgHeader": "#212121",
    "bgHeaderHasFocus": "#474747",
    "bgHeaderHovered": "#404040",
    "bgBubble": "#212121",
    "bgBubbleSelected": "#000000",
    "bgSearchResult": "#423c24",
    "borderColor": "rgba(225,225,225,0.2)",
    "drilldownBorder": "rgba(225,225,225,0.4)",
    "linkColor": "#4F5DFF",
    "headerFontStyle": "bold 14px",
    "baseFontStyle": "13px",
    "fontFamily": "Inter, Roboto, -apple-system, BlinkMacSystemFont, avenir next, avenir, segoe ui, helvetica neue, helvetica, Ubuntu, noto, arial, sans-serif",
}
```

# Live Streaming example

Lastly let's add in an API so we can live stream data into our datatable.

Here we use a [Background Task](https://reflex.dev/docs/advanced-guide/background-tasks) to stream the data into the table without blocking UI interactivity. We call an advice API using `httpx` and then append that data to the `self.table_data` state var. We also create a button that allows us to start and pause the streaming of the data by changing the value of the boolean state var `running` using the event handler `toggle_pause`. If the `running` state var is set to `True` we stream the API data, when it is set to `False` we break out of the `while` loop and end the background event.

```python
class DataTableLiveState(BaseState):
    "The app state."

    running: bool = False
    table_data: list[dict[str, Any]] = []
    rate: int = 0.4
    columns: list[dict[str, str]] = [
        {
            "title": "id", 
            "id": "v1", 
            "type": "int",
            "width": 100,
        },
        {
            "title": "advice", 
            "id": "v2", 
            "type": "str",
            "width": 750,
        },
    
    ]

    @rx.background
    async def live_stream(self):
        while True:
            await asyncio.sleep(1 / self.rate)
            if not self.running:
                break

            async with self:
                if len(self.table_data) > 50:
                    self.table_data.pop(0)

                res = httpx.get('https://api.adviceslip.com/advice')
                data = res.json()
                self.table_data.append(\{"v1": data["slip"]["id"], "v2": data["slip"]["advice"]})


    def toggle_pause(self):
        self.running = not self.running
        if self.running:
            return DataTableLiveState.live_stream
```

```python demo
rx.vstack(
    rx.stack(
        rx.cond(
            ~DataTableLiveState.running,
            rx.button("Start", on_click=DataTableLiveState.toggle_pause, color_scheme='green'),
            rx.button("Pause", on_click=DataTableLiveState.toggle_pause, color_scheme='red'),
        ),
    ),
    rx.data_editor(
        columns=DataTableLiveState.columns,
        data=DataTableLiveState.table_data,
        draw_focus_ring=True,
        row_height=50,
        smooth_scroll_x=True,
        smooth_scroll_y=True,
        column_select="single",
        # style
        theme=darkTheme,
        ),
    overflow_x="auto",
    width="100%",
    height="30vh",
)
```
