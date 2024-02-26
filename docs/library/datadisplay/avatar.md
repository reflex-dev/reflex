---
components:
    - rx.radix.avatar
Avatar: |
    lambda **props: rx.hstack(rx.avatar(src="/logo.jpg", **props), rx.avatar(fallback="RX", **props), spacing="3")
---
# Avatar

```python exec
import reflex as rx
from pcweb.templates.docpage import style_grid
```

The Avatar component is used to represent a user, and display their profile pictures or fallback texts such as initials.

## Basic Example

To create an avatar component with an image, pass the image URL as the `src` prop.

```python demo
rx.avatar(src="/logo.jpg")
```

To display a text such as initials, set the `fallback` prop without passing the `src` prop.

```python demo
rx.avatar(fallback="RX")
```

## Styling

```python eval
style_grid(component_used=rx.avatar, component_used_str="rx.avatar", variants=["solid", "soft"], fallback="RX")
```

### Size

The `size` prop controls the size and spacing of the avatar. The acceptable size is from `"1"` to `"9"`, with `"3"` being the default.

```python demo
rx.flex(
    rx.avatar(src="/logo.jpg", fallback="RX", size="1"),
    rx.avatar(src="/logo.jpg", fallback="RX", size="2"),
    rx.avatar(src="/logo.jpg", fallback="RX", size="3"),
    rx.avatar(src="/logo.jpg", fallback="RX"),
    rx.avatar(src="/logo.jpg", fallback="RX", size="4"),
    rx.avatar(src="/logo.jpg", fallback="RX", size="5"),
    rx.avatar(src="/logo.jpg", fallback="RX", size="6"),
    rx.avatar(src="/logo.jpg", fallback="RX", size="7"),
    rx.avatar(src="/logo.jpg", fallback="RX", size="8"),
    spacing="1",
)
```

### Variant

The `variant` prop controls the visual style of the avatar fallback text. The variant can be `"solid"` or `"soft"`. The default is `"soft"`.

```python demo
rx.flex(
    rx.avatar(fallback="RX", variant="solid"),
    rx.avatar(fallback="RX", variant="soft"),
    rx.avatar(fallback="RX"),
    spacing="2",
)
```

### Color Scheme

The `color_scheme` prop sets a specific color to the fallback text, ignoring the global theme.

```python demo
rx.flex(
    rx.avatar(fallback="RX", color_scheme="indigo"),
    rx.avatar(fallback="RX", color_scheme="cyan"),
    rx.avatar(fallback="RX", color_scheme="orange"),
    rx.avatar(fallback="RX", color_scheme="crimson"),
    spacing="2",
)
```

### High Contrast

The `high_contrast` prop increases color contrast of the fallback text with the background.

```python demo
rx.grid(
    rx.avatar(fallback="RX", variant="solid"),
    rx.avatar(fallback="RX", variant="solid", high_contrast=True),
    rx.avatar(fallback="RX", variant="soft"),
    rx.avatar(fallback="RX", variant="soft", high_contrast=True),
    rows="2",
    spacing="2",
    flow="column",
)
```

### Radius

The `radius` prop sets specific radius value, ignoring the global theme. It can take values `"none" | "small" | "medium" | "large" | "full"`.

```python demo
rx.grid(
    rx.avatar(src="/logo.jpg", fallback="RX", radius="none"),
    rx.avatar(fallback="RX", radius="none"),
    rx.avatar(src="/logo.jpg", fallback="RX", radius="small"),
    rx.avatar(fallback="RX", radius="small"),
    rx.avatar(src="/logo.jpg", fallback="RX", radius="medium"),
    rx.avatar(fallback="RX", radius="medium"),
    rx.avatar(src="/logo.jpg", fallback="RX", radius="large"),
    rx.avatar(fallback="RX", radius="large"),
    rx.avatar(src="/logo.jpg", fallback="RX", radius="full"),
    rx.avatar(fallback="RX", radius="full"),
    rows="2",
    spacing="2",
    flow="column",
)
```

### Fallback

The `fallback` prop indicates the rendered text when the `src` cannot be loaded.

```python demo
rx.flex(
    rx.avatar(fallback="RX"),
    rx.avatar(fallback="PC"),
    spacing="2",
)
```

## Final Example

As part of a user profile page, the Avatar component is used to display the user's profile picture, with the fallback text showing the user's initials. Text components displays the user's full name and username handle and a Button component shows the edit profile button.

```python demo
rx.flex(
    rx.avatar(src="/logo.jpg", fallback="RU", size="9"),
    rx.text("Reflex User", weight="bold", size="4"),
    rx.text("@reflexuser", color_scheme="gray"),
    rx.button("Edit Profile", color_scheme="indigo", variant="solid"),
    direction="column",
    spacing="1",
)
```
