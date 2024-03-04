```python exec
from pcweb.pages.docs import styling
import reflex as rx
```

# Style Props

In addition to component-specific props, most built-in components support a full range of style props. You can use any CSS property to style a component.

```python demo
rx.button(
    "Fancy Button",
    border_radius="1em",
    box_shadow="rgba(151, 65, 252, 0.8) 0 15px 30px -10px",
    background_image="linear-gradient(144deg,#AF40FF,#5B42F3 50%,#00DDEB)",
    box_sizing="border-box",
    color="white",
    opacity= 1,
    _hover={
        "opacity": .5,
    }
)
```

See the [styling docs]({styling.overview.path}) to learn more about customizing the appearance of your app.
