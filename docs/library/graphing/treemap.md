---
components:
    - rx.recharts.Treemap
---

# Treemap

```python exec
import reflex as rx
from pcweb.templates.docpage import docgraphing

data = [
  {
    "name": "axis",
    "children": [
      {
        "name": "Axis",
        "size": 24593
      },
      {
        "name": "Axes",
        "size": 1302
      },
      {
        "name": "AxisGridLine",
        "size": 652
      },
      {
        "name": "AxisLabel",
        "size": 636
      },
      {
        "name": "CartesianAxes",
        "size": 6703
      }
    ]
  },
  {
    "name": "controls",
    "children": [
      {
        "name": "TooltipControl",
        "size": 8435
      },
      {
        "name": "SelectionControl",
        "size": 7862
      },
      {
        "name": "PanZoomControl",
        "size": 5222
      },
      {
        "name": "HoverControl",
        "size": 4896
      },
      {
        "name": "ControlList",
        "size": 4665
      },
      {
        "name": "ClickControl",
        "size": 3824
      },
      {
        "name": "ExpandControl",
        "size": 2832
      },
      {
        "name": "DragControl",
        "size": 2649
      },
      {
        "name": "AnchorControl",
        "size": 2138
      },
      {
        "name": "Control",
        "size": 1353
      },
      {
        "name": "IControl",
        "size": 763
      }
    ]
  },
  {
    "name": "data",
    "children": [
      {
        "name": "Data",
        "size": 20544
      },
      {
        "name": "NodeSprite",
        "size": 19382
      },
      {
        "name": "DataList",
        "size": 19788
      },
      {
        "name": "DataSprite",
        "size": 10349
      },
      {
        "name": "EdgeSprite",
        "size": 3301
      },
      {
        "name": "render",
        "children": [
          {
            "name": "EdgeRenderer",
            "size": 5569
          },
          {
            "name": "ShapeRenderer",
            "size": 2247
          },
          {
            "name": "ArrowType",
            "size": 698
          },
          {
            "name": "IRenderer",
            "size": 353
          }
        ]
      },
      {
        "name": "ScaleBinding",
        "size": 11275
      },
      {
        "name": "TreeBuilder",
        "size": 9930
      },
      {
        "name": "Tree",
        "size": 7147
      }
    ]
  },
  {
    "name": "events",
    "children": [
      {
        "name": "DataEvent",
        "size": 7313
      },
      {
        "name": "SelectionEvent",
        "size": 6880
      },
      {
        "name": "TooltipEvent",
        "size": 3701
      },
      {
        "name": "VisualizationEvent",
        "size": 2117
      }
    ]
  },
  {
    "name": "legend",
    "children": [
      {
        "name": "Legend",
        "size": 20859
      },
      {
        "name": "LegendRange",
        "size": 10530
      },
      {
        "name": "LegendItem",
        "size": 4614
      }
    ]
  },
  {
    "name": "operator",
    "children": [
      {
        "name": "distortion",
        "children": [
          {
            "name": "Distortion",
            "size": 6314
          },
          {
            "name": "BifocalDistortion",
            "size": 4461
          },
          {
            "name": "FisheyeDistortion",
            "size": 3444
          }
        ]
      },
      {
        "name": "encoder",
        "children": [
          {
            "name": "PropertyEncoder",
            "size": 4138
          },
          {
            "name": "Encoder",
            "size": 4060
          },
          {
            "name": "ColorEncoder",
            "size": 3179
          },
          {
            "name": "SizeEncoder",
            "size": 1830
          },
          {
            "name": "ShapeEncoder",
            "size": 1690
          }
        ]
      },
      {
        "name": "filter",
        "children": [
          {
            "name": "FisheyeTreeFilter",
            "size": 5219
          },
          {
            "name": "VisibilityFilter",
            "size": 3509
          },
          {
            "name": "GraphDistanceFilter",
            "size": 3165
          }
        ]
      },
      {
        "name": "IOperator",
        "size": 1286
      },
      {
        "name": "label",
        "children": [
          {
            "name": "Labeler",
            "size": 9956
          },
          {
            "name": "RadialLabeler",
            "size": 3899
          },
          {
            "name": "StackedAreaLabeler",
            "size": 3202
          }
        ]
      },
      {
        "name": "layout",
        "children": [
          {
            "name": "RadialTreeLayout",
            "size": 12348
          },
          {
            "name": "NodeLinkTreeLayout",
            "size": 12870
          },
          {
            "name": "CirclePackingLayout",
            "size": 12003
          },
          {
            "name": "CircleLayout",
            "size": 9317
          },
          {
            "name": "TreeMapLayout",
            "size": 9191
          },
          {
            "name": "StackedAreaLayout",
            "size": 9121
          },
          {
            "name": "Layout",
            "size": 7881
          },
          {
            "name": "AxisLayout",
            "size": 6725
          },
          {
            "name": "IcicleTreeLayout",
            "size": 4864
          },
          {
            "name": "DendrogramLayout",
            "size": 4853
          },
          {
            "name": "ForceDirectedLayout",
            "size": 8411
          },
          {
            "name": "BundledEdgeRouter",
            "size": 3727
          },
          {
            "name": "IndentedTreeLayout",
            "size": 3174
          },
          {
            "name": "PieLayout",
            "size": 2728
          },
          {
            "name": "RandomLayout",
            "size": 870
          }
        ]
      },
      {
        "name": "OperatorList",
        "size": 5248
      },
      {
        "name": "OperatorSequence",
        "size": 4190
      },
      {
        "name": "OperatorSwitch",
        "size": 2581
      },
      {
        "name": "Operator",
        "size": 2490
      },
      {
        "name": "SortOperator",
        "size": 2023
      }
    ]
  }
]


treemap_example = """rx.recharts.treemap(
                rx.recharts.graphing_tooltip(),
                data=data,
                data_key="size",
                stroke="#fff",
                fill="#8884d8")"""

```

Treemaps display hierarchical (tree-structured) data as a set of nested rectangles. Each branch of the tree is given a rectangle, which is then tiled with smaller rectangles representing sub-branches. A leaf node's rectangle has an area proportional to a specified dimension of the data.

```python eval
docgraphing(treemap_example, comp=eval(treemap_example), data =  "data=" + str(data))
```
