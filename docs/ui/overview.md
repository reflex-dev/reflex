```python exec
import reflex as rx
```

# UI Overview

Components are the building blocks for your app's user interface (UI). They are the visual elements that make up your app, like buttons, text, and images.

## Component Basics

Components are made up of children and props.

```md definition
# Children

- Text or other Reflex components nested inside a component.
- Passed as **positional arguments**.

# Props

- Attributes that affect the behavior and appearance of a component.
- Passed as **keyword arguments**.
```

Let's take a look at the `rx.text` component.

```python demo
rx.text("Hello World!", color="blue", font_size="1.5em")
```

```python test
def test_text_with_props(demo):
    text = demo.get_by_text("Hello World!", exact=True)
    expect(text).to_have_css("color", "rgb(0, 0, 255)")
    expect(text).to_have_css("font-size", "24px")
```

Here `"Hello World!"` is the child text to display, while `color` and `font_size` are props that modify the appearance of the text.

```md alert success
# Regular Python data types can be passed in as children to components. This is useful for passing in text, numbers, and other simple data types.
```

## Another Example

Now let's take a look at a more complex component, which has other components nested inside it. The `rx.vstack` component is a container that arranges its children vertically with space between them.

```python demo
rx.vstack(
    rx.heading("Sample Form", as_="h2"),
    rx.input(placeholder="Name"),
    rx.checkbox("Subscribe to Newsletter"),
)
```

```python test
def test_vstack_form(demo):
    expect(demo.get_by_role("heading")).to_have_text("Sample Form")
    name = demo.get_by_placeholder("Name")
    name.fill("Ada")
    expect(name).to_have_value("Ada")
    newsletter = demo.get_by_role("checkbox", name="Subscribe to Newsletter")
    expect(newsletter).not_to_be_checked()
    newsletter.click()
    expect(newsletter).to_be_checked()
```

Some props are specific to a component. For example, the `header` and `content` props of the `rx.accordion.item` component show the heading and accordion content details of the accordion respectively.

Styling props like `color` are shared across many components.

```md alert info
# You can find all the props for a component by checking its documentation page in the [component library](/docs/library/).
```

## Pages

Reflex apps are organized into pages, each of which maps to a different URL.

Pages are defined as functions that return a component. By default, the function name will be used as the path, but you can also specify a route explicitly.

```python
def index():
    return rx.text("Root Page")


def about():
    return rx.text("About Page")


app = rx.App()
app.add_page(index, route="/")
app.add_page(about, route="/about")
```

In this example we add a page called `index` at the root route.
If you `reflex run` the app, you will see the `index` page at `http://localhost:3000`.
Similarly, the `about` page will be available at `http://localhost:3000/about`.
