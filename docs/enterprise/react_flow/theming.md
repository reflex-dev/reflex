# Theming

You can customize the appearance of the Flow component using CSS. The Flow component comes with a default theme, which you can override with your own styles.

## CSS Variables

The Flow component uses CSS variables for theming. You can override these variables to change the appearance of the flow. Here are some of the most common variables:

```css
.react-flow {
  --xy-background-color: #f7f9fb;
  --xy-node-border-default: 1px solid #ededed;
  --xy-node-boxshadow-default: 0px 3.54px 4.55px 0px #00000005,
    0px 3.54px 4.55px 0px #0000000d, 0px 0.51px 1.01px 0px #0000001a;
  --xy-node-border-radius-default: 8px;
  --xy-handle-background-color-default: #ffffff;
  --xy-handle-border-color-default: #aaaaaa;
  --xy-edge-label-color-default: #505050;
}
```

## Custom Stylesheets

You can add custom stylesheets to your app to override the default styles. To do this, add the `stylesheets` prop to your `rxe.App` or `rx.App` instance:

```python
app = rxe.App(
    stylesheets=[
        "/css/my-custom-styles.css",
    ],
)
```

Then, create a file `assets/css/my-custom-styles.css` in your project and add your custom styles there.

## Customizing Node and Edge Styles

You can also apply custom styles to individual nodes and edges using the `style` and `className` props.

### Using the style prop

You can pass a style dictionary to the `style` prop of a node or edge:

```python
node = {
    "id": "1",
    "position": {"x": 100, "y": 100},
    "data": {"label": "Node 1"},
    "style": {"backgroundColor": "#ffcc00"},
}
```

### Using the className prop

You can also pass a class name to the `className` prop and define the styles in your CSS file:

```python
# In your python code
node = {
    "id": "1",
    "position": {"x": 100, "y": 100},
    "data": {"label": "Node 1"},
    "className": "my-custom-node",
}
```

```css
/* In your CSS file */
.my-custom-node {
    background-color: #ffcc00;
    border: 2px solid #ff9900;
    border-radius: 10px;
}
```
