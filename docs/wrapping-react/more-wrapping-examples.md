# More React Libraries 


## AG Charts

Here we wrap the AG Charts library from the NPM package [ag-charts-react](https://www.npmjs.com/package/ag-charts-react). 

In the react code below we can see the first `2` lines are importing React and ReactDOM, and this can be ignored when wrapping your component.

We import the `AgCharts` component from the `ag-charts-react` library on line 5. In Reflex this is wrapped by `library = "ag-charts-react"` and `tag = "AgCharts"`.

Line `7` defines a functional React component, which on line `26` returns `AgCharts` which is similar in the Reflex code to using the `chart` component.

Line `9` uses the `useState` hook to create a state variable `chartOptions` and its setter function `setChartOptions` (equivalent to the event handler `set_chart_options` in reflex). The initial state variable is of type dict and has two key value pairs `data` and `series`. 

When we see `useState` in React code, it correlates to state variables in your State. As you can see in our Reflex code we have a state variable `chart_options` which is a dictionary, like in our React code.

Moving to line `26` we see that the `AgCharts` has a prop `options`. In order to use this in Reflex we must wrap this prop. We do this with `options: rx.Var[dict]` in the `AgCharts` component. 

Lines `31` and `32` are rendering the component inside the root element. This can be ignored when we are wrapping a component as it is done in Reflex by creating an `index` function and adding it to the app.


---md tabs

--tab React Code    

```javascript
1 | import React, \{ useState } from 'react';
2 | import ReactDOM from 'react-dom/client';
3 | 
4 | // React Chart Component
5 | import \{ AgCharts } from 'ag-charts-react';
6 | 
7 | const ChartExample = () => {
8 |     // Chart Options: Control & configure the chart
9 |     const [chartOptions, setChartOptions] = useState({
10|         // Data: Data to be displayed in the chart
11|         data: [
12|             \{ month: 'Jan', avgTemp: 2.3, iceCreamSales: 162000 },
13|             \{ month: 'Mar', avgTemp: 6.3, iceCreamSales: 302000 },
14|             \{ month: 'May', avgTemp: 16.2, iceCreamSales: 800000 },
15|             \{ month: 'Jul', avgTemp: 22.8, iceCreamSales: 1254000 },
16|             \{ month: 'Sep', avgTemp: 14.5, iceCreamSales: 950000 },
17|             \{ month: 'Nov', avgTemp: 8.9, iceCreamSales: 200000 },
18|         ],
19|         // Series: Defines which chart type and data to use
20|         series: [\{ type: 'bar', xKey: 'month', yKey: 'iceCreamSales' }],
21|     });
22| 
23|     // React Chart Component
24|     return (
25|         // AgCharts component with options passed as prop
26|         <AgCharts options=\{chartOptions} />
27|     );
28| }
29| 
30| // Render component inside root element
31| const root = ReactDOM.createRoot(document.getElementById('root'));
32| root.render(<ChartExample />);
```

--
--tab Reflex Code

```python
import reflex as rx

class AgCharts(rx.Component):
    """ A simple line chart component using AG Charts """

    library = "ag-charts-react"
    
    tag = "AgCharts"

    options: rx.Var[dict]


chart = AgCharts.create


class State(rx.State):
    """The app state."""
    chart_options: dict = {
           "data": [
                \{"month":"Jan", "avgTemp":2.3, "iceCreamSales":162000},
                \{"month":"Mar", "avgTemp":6.3, "iceCreamSales":302000},
                \{"month":"May", "avgTemp":16.2, "iceCreamSales":800000},
                \{"month":"Jul", "avgTemp":22.8, "iceCreamSales":1254000},
                \{"month":"Sep", "avgTemp":14.5, "iceCreamSales":950000},
                \{"month":"Nov", "avgTemp":8.9, "iceCreamSales":200000}
            ],
            "series": [\{"type":"bar", "xKey":"month", "yKey":"iceCreamSales"}]
        }

def index() -> rx.Component:
    return chart(
        options=State.chart_options,
    )

app = rx.App()
app.add_page(index)
```
--

---


## React Leaflet

```python exec
from pcweb.pages import docs
```

In this example we are wrapping the React Leaflet library from the NPM package [react-leaflet](https://www.npmjs.com/package/react-leaflet).

On line `1` we import the `dynamic` function from Next.js and on line `21` we set `ssr: false`. Lines `4` and `6` use the `dynamic` function to import the `MapContainer` and `TileLayer` components from the `react-leaflet` library. This is used to dynamically import the `MapContainer` and `TileLayer` components from the `react-leaflet` library. This is done in Reflex by using the `NoSSRComponent` class when defining the component. There is more information of when this is needed on the `Dynamic Imports` section of this [page]({docs.wrapping_react.library_and_tags.path}).

It mentions in the documentation that it is necessary to include the Leaflet CSS file, which is added on line `2` in the React code below. This can be done in Reflex by using the `add_imports` method in the `MapContainer` component. We can add a relative path from within the React library or a full URL to the CSS file.

Line `4` defines a functional React component, which on line `8` returns the `MapContainer` which is done in the Reflex code using the `map_container` component.

The `MapContainer` component has props `center`, `zoom`, `scrollWheelZoom`, which we wrap in the `MapContainer` component in the Reflex code. We ignore the `style` prop as it is a reserved name in Reflex. We can use the `rename_props` method to change the name of the prop, as we will see in the React PDF Renderer example, but in this case we just ignore it and add the `width` and `height` props as css in Reflex.

The `TileLayer` component has a prop `url` which we wrap in the `TileLayer` component in the Reflex code.

Lines `24` and `25` defines and exports a React functional component named `Home` which returns the `MapComponent` component. This can be ignored in the Reflex code when wrapping the component as we return the `map_container` component in the `index` function.

---md tabs

--tab React Code 

```javascript
1 | import dynamic from "next/dynamic";
2 | import "leaflet/dist/leaflet.css";
3 | 
4 | const MapComponent = dynamic(
5 |   () => {
6 |     return import("react-leaflet").then((\{ MapContainer, TileLayer }) => {
7 |       return () => (
8 |         <MapContainer
9 |           center=\{[51.505, -0.09]}
10|           zoom=\{13}
11|           scrollWheelZoom=\{true}
12|           style=\{\{ height: "50vh", width: "100%" }}
13|        >
14|          <TileLayer
15|            url="https://\{s}.tile.openstreetmap.org/\{z}/\{x}/\{y}.png"
16|          />
17|        </MapContainer>
18|      );
19|    });
20|  },
21|  \{ ssr: false }
22| );
23|
24| export default function Home() {
25|   return <MapComponent />;
26| }
```

--
--tab Reflex Code

```python 
import reflex as rx

class MapContainer(rx.NoSSRComponent):

    library = "react-leaflet"

    tag = "MapContainer"

    center: rx.Var[list]

    zoom: rx.Var[int]

    scroll_wheel_zoom: rx.Var[bool]

    # Can also pass a url like: https://unpkg.com/leaflet/dist/leaflet.css 
    def add_imports(self):
        return \{"": ["leaflet/dist/leaflet.css"]}



class TileLayer(rx.NoSSRComponent):

    library = "react-leaflet"

    tag = "TileLayer"

    url: rx.Var[str]


map_container = MapContainer.create
tile_layer = TileLayer.create

def index() -> rx.Component:
    return map_container(
                tile_layer(url="https://\{s}.tile.openstreetmap.org/\{z}/\{x}/\{y}.png"),
                center=[51.505, -0.09], 
                zoom=13,
                #scroll_wheel_zoom=True
                width="100%",
                height="50vh",
            )


app = rx.App()
app.add_page(index)

```
--

---


## React PDF Renderer

In this example we are wrapping the React renderer for creating PDF files on the browser and server from the NPM package [@react-pdf/renderer](https://www.npmjs.com/package/@react-pdf/renderer).

This example is similar to the previous examples, and again Dynamic Imports are required for this library. This is done in Reflex by using the `NoSSRComponent` class when defining the component. There is more information on why this is needed on the `Dynamic Imports` section of this [page]({docs.wrapping_react.library_and_tags.path}).

The main difference with this example is that the `style` prop, used on lines `20`, `21` and `24` in React code, is a reserved name in Reflex so can not be wrapped. A different name must be used when wrapping this prop and then this name must be changed back to the original with the `rename_props` method. In this example we name the prop `theme` in our Reflex code and then change it back to `style` with the `rename_props` method in both the `Page` and `View` components.


```md alert info
# List of reserved names in Reflex

_The style of the component._

`style: Style = Style()`

_A mapping from event triggers to event chains._

`event_triggers: Dict[str, Union[EventChain, Var]] = \{}`

_The alias for the tag._

`alias: Optional[str] = None`

_Whether the import is default or named._

`is_default: Optional[bool] = False`

_A unique key for the component._

`key: Any = None`

_The id for the component._

`id: Any = None`

_The class name for the component._

`class_name: Any = None`

_Special component props._

`special_props: List[Var] = []`

_Whether the component should take the focus once the page is loaded_

`autofocus: bool = False`

_components that cannot be children_

`_invalid_children: List[str] = []`

_only components that are allowed as children_

`_valid_children: List[str] = []`

_only components that are allowed as parent_

`_valid_parents: List[str] = []`

_props to change the name of_

`_rename_props: Dict[str, str] = \{}`

_custom attribute_

`custom_attrs: Dict[str, Union[Var, str]] = \{}`

_When to memoize this component and its children._

`_memoization_mode: MemoizationMode = MemoizationMode()`

_State class associated with this component instance_

`State: Optional[Type[reflex.state.State]] = None`
```

---md tabs

--tab React Code    

```javascript
1 | import ReactDOM from 'react-dom';
2 | import \{ Document, Page, Text, View, StyleSheet, PDFViewer } from '@react-pdf/renderer';
3 |
4 | // Create styles
5 | const styles = StyleSheet.create({
6 |   page: {
7 |     flexDirection: 'row',
8 |     backgroundColor: '#E4E4E4',
9 |   },
10|   section: {
11|     margin: 10,
12|    padding: 10,
13|     flexGrow: 1,
14|   },
15| });
16|
17| // Create Document Component
18| const MyDocument = () => (
19|   <Document>
20|     <Page size="A4" style=\{styles.page}>
21|       <View style=\{styles.section}>
22|         <Text>Section #1</Text>
23|       </View>
24|       <View style=\{styles.section}>
25|         <Text>Section #2</Text>
26|       </View>
27|     </Page>
28|   </Document>
29| );
30| 
31| const App = () => (
32|   <PDFViewer>
33|     <MyDocument />
34|   </PDFViewer>
35| );
36| 
37| ReactDOM.render(<App />, document.getElementById('root'));
```

--
--tab Reflex Code

```python
import reflex as rx

class Document(rx.Component):
    
    library = "@react-pdf/renderer"

    tag = "Document"
    

class Page(rx.Component):
    
    library = "@react-pdf/renderer"

    tag = "Page"

    size: rx.Var[str]
    # here we are wrapping style prop but as style is a reserved name in Reflex we must name it something else and then change this name with rename props method
    theme: rx.Var[dict]

    _rename_props: dict[str, str] = {
        "theme": "style",
    }


class Text(rx.Component):
    
    library = "@react-pdf/renderer"

    tag = "Text"


class View(rx.Component):
    
    library = "@react-pdf/renderer"

    tag = "View"

    # here we are wrapping style prop but as style is a reserved name in Reflex we must name it something else and then change this name with rename props method
    theme: rx.Var[dict]

    _rename_props: dict[str, str] = {
        "theme": "style",
    }


class StyleSheet(rx.Component):
    
    library = "@react-pdf/renderer"

    tag = "StyleSheet"

    page: rx.Var[dict]

    section: rx.Var[dict]


class PDFViewer(rx.NoSSRComponent):
    
    library = "@react-pdf/renderer"

    tag = "PDFViewer"


document = Document.create
page = Page.create
text = Text.create
view = View.create
style_sheet = StyleSheet.create
pdf_viewer = PDFViewer.create


styles = style_sheet({
  "page": {
    "flexDirection": 'row',
    "backgroundColor": '#E4E4E4',
  },
  "section": {
    "margin": 10,
    "padding": 10,
    "flexGrow": 1,
  },
})


def index() -> rx.Component:
    return pdf_viewer( 
        document(
            page(
                view(
                    text("Hello, World!"),
                    theme=styles.section,
                ),
                view(
                    text("Hello, 2!"),
                    theme=styles.section,
                ),
                size="A4", theme=styles.page),
        ),
        width="100%",
        height="80vh",
    )

app = rx.App()
app.add_page(index)
```
--

---