---
components:
  - rx.element_observer
---

```python exec
import reflex as rx
```

# Element Observer

`rx.element_observer` reports the size, position and visibility of an element to
event triggers, from the browser's `ResizeObserver`, `IntersectionObserver` and
scroll events. It renders its child unchanged and adds nothing to the page.

Its triggers fit [client state](/docs/wrapping-react/overview): setting a client
state var from them restyles the page from what the browser measured, without a
round trip to the backend. They accept backend event handlers as well.

The observed element is the only child. If it has no id, it gets one from
React's `useId`, which differs between the items of an `rx.foreach`. To observe
an element rendered elsewhere, leave out the child and pass its id as `target`.
The observer follows the id: it starts observing once an element with it is on
the page, such as one that `rx.cond` shows later, and moves to an element that
takes the id over.

## Size

`on_resize` fires with the element's width and height in pixels when observing
starts and whenever its border box changes size. They are the size
`getBoundingClientRect` measures, so a transform such as `scale` is included,
but a change of the transform alone does not fire `on_resize`: the browser's
`ResizeObserver` it follows ignores transforms.

```python demo exec
def element_size_example():
    width = rx.client_state(0)
    return rx.vstack(
        rx.element_observer(
            rx.text_area(
                placeholder="Drag the corner to resize me", resize="horizontal"
            ),
            on_resize=lambda w, h: width.set(w),
        ),
        rx.text("Width: ", width.value, "px"),
    )
```

## Visibility

`on_intersect` fires with whether the element is in the viewport and which
fraction of it is, when observing starts and whenever that fraction crosses one
of the `threshold` values (by default 0: when the element enters or leaves).
`root_margin` grows or shrinks the viewport for it, in CSS margin syntax such as
`"-100px 0px 0px 0px"`. Parts of the element that a scroll container clips are
not in view.

```python demo exec
def element_visibility_example():
    visible = rx.client_state(False)
    return rx.vstack(
        rx.badge(
            rx.cond(
                visible.value, "The last line is in view", "Scroll to the last line"
            )
        ),
        rx.box(
            *[rx.text(f"Line {number}") for number in range(1, 20)],
            rx.element_observer(rx.text("The last line"), on_intersect=visible.set),
            height="8em",
            overflow_y="auto",
        ),
    )
```

## Position

`on_move` fires with the element's position in the viewport, the pixels from
the viewport's left and top edge to the element's, when observing starts and
whenever it changes because the page or one of its scroll containers scrolled,
the window resized or the element resized. A table of contents can mark a
section as reached once its heading's top passes a line below the top of the
viewport.

```python demo exec
def element_position_example():
    top = rx.client_state(0)
    return rx.vstack(
        rx.text("Distance of the box from the top of the viewport: ", top.value, "px"),
        rx.box(
            rx.box(height="6em"),
            rx.element_observer(
                rx.box("Box", background_color=rx.color("accent", 4), padding="1em"),
                on_move=lambda x, y: top.set(round(y)),
            ),
            rx.box(height="12em"),
            height="10em",
            overflow_y="auto",
        ),
    )
```

## Transitions

`on_transition_end` fires with the property name when a CSS transition of the
element itself ends; transitions of its descendants do not fire it. Together
with `on_resize` it animates the height of a panel to the height of its content.

```python demo exec
def element_transition_example():
    expanded = rx.client_state(False)
    content_height = rx.client_state(0)
    moving = rx.client_state(False)
    return rx.vstack(
        rx.button(
            rx.cond(expanded.value, "Collapse", "Expand"),
            on_click=[expanded.set(~expanded.value), moving.set(True)],
        ),
        rx.element_observer(
            rx.box(
                rx.element_observer(
                    rx.box(rx.text("The content of the panel."), padding="1em"),
                    on_resize=lambda w, h: content_height.set(h),
                ),
                height=rx.cond(
                    expanded.value, content_height.value.to(str) + "px", "0px"
                ),
                overflow="hidden",
                transition="height 300ms ease",
            ),
            on_transition_end=moving.set(False),
        ),
        rx.text(rx.cond(moving.value, "Moving", "Settled")),
    )
```

## Timing

Observing starts in an effect after the observer mounts, or once the element is
on the page if it comes later, and `disabled` pauses it: once `disabled` is
false again, observing restarts with a first report.

With `layout=True` observing starts in a layout effect instead, so the first
`on_resize` and `on_move` fire while React commits the render that mounted or
enabled the observer, before that commit's effects run and before the browser
paints. Use it where the first measurement has to come before anything else
reacts to the render, such as a header measured while it is still in the flow,
before it is fixed to the top of the viewport.

After the first report, a change of the element's size fires `on_resize`, and
`on_move` if it moved the element, in the animation frame after the browser
laid it out. So a handler may resize the element it observes, such as a flex
row that stacks its items once it is narrow, without the browser raising a
`ResizeObserver` loop error. Scrolls and window resizes fire `on_move` right
away.
