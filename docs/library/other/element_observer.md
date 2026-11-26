---
components:
  - rx.element_observer
meta_description: "Measure the size, position and visibility of elements in the browser with rx.element_observer, and feed them into client state in pure Python."
---

```python exec
import reflex as rx
```

# Element Observer

`rx.element_observer` reports what the browser knows about an element once it
has laid out the page: its size, its position in the viewport, whether it is
visible, and when its CSS transitions end. It renders its child unchanged and
adds nothing to the page.

Use it for UI that depends on the layout: a card that rearranges itself when it
gets narrow, a table of contents that marks the section in view, a back-to-top
button that appears once the reader has scrolled down, or a fixed header whose
height the content below has to leave room for.

```python demo exec
def element_size_example():
    width = rx.client_state(0)
    return rx.vstack(
        rx.element_observer(
            rx.text_area(
                placeholder="Drag the corner to resize me", resize="horizontal"
            ),
            on_resize=lambda w, h: width.set(round(w)),
        ),
        rx.text("Width: ", width.value, "px"),
    )
```

The observer wraps the element to measure and fires `on_resize` with its width
and height. The lambda passes the width to a
[client state](/docs/wrapping-react/overview/#naming-and-scoping-client-state)
var, and `width.value` renders it. The [API reference](#api-reference) at the
end of the page lists each event trigger with its arguments and each prop.

## How Values Flow

The observer's event triggers fire in the browser, often many times per second
while the page scrolls or an element animates. Send them to a client state
var's `set`, and the components that read the var re-render right away, without
a round trip to the backend.

The lambda you pass to a trigger runs only once, when the page compiles. Its
arguments are Vars that stand for the values measured in the browser, so write
its logic as [Var operations](/docs/vars/var-operations/) rather than Python
`if` statements: comparisons and arithmetic such as `w < 400` or `h + 16`, `~`
for not, and `rx.cond` for a choice. Store what the page needs rather than raw
pixels where you can: a client state var set to the value it already holds
re-renders nothing, so a boolean only re-renders when it flips.

```python
narrow = rx.client_state(False)

rx.element_observer(
    rx.box(...),
    on_resize=lambda w, h: narrow.set(w < 400),
)
```

Read the var with `.value` wherever a component takes a Var: as a child, in
`rx.cond`, or in a style prop.

```python
rx.flex(..., direction=rx.cond(narrow.value, "column", "row"))
rx.box(..., padding_top=f"{header_height.value}px")
```

A trigger given a client state var's `set` without a lambda passes it the
trigger's first argument, so `on_intersect=visible.set` stores whether the
element is visible.

### When Not To Use It

- **Backend event handlers for continuous values.** The triggers accept backend
  event handlers too, but each report then becomes an event sent to the server,
  and the page only changes once the server's update comes back. During a
  scroll or a resize that is many events per second, and the page lags behind.
  Keep sizes and positions in client state, and call the backend only for
  occasional events that need it, such as
  [loading more rows](#calling-the-backend) once the end of a list comes into
  view.
- **Layout that CSS can express.** Media queries, container queries and
  `position: sticky` need no measurement and work before JavaScript loads.
  Reach for an observer when a measurement decides _what_ to render, or when
  CSS has no way to express the layout.

## Responsive Components

Unlike a media query, `on_resize` follows the element's own size, not the
window's. The card below drops its description and stacks its parts once it is
narrower than 400 pixels. Drag the corner of the dashed box to resize it.

```python demo exec
def responsive_card_example():
    narrow = rx.client_state(False)
    return rx.box(
        rx.element_observer(
            rx.flex(
                rx.box(
                    background_color=rx.color("accent", 5),
                    border_radius="6px",
                    min_height="4em",
                    min_width="6em",
                ),
                rx.vstack(
                    rx.text("Wireless headphones", size="4", weight="bold"),
                    rx.cond(
                        ~narrow.value,
                        rx.text("Up to 30 hours of playback.", color_scheme="gray"),
                    ),
                    rx.button("Add to cart"),
                    align="start",
                ),
                direction=rx.cond(narrow.value, "column", "row"),
                spacing="4",
            ),
            on_resize=lambda w, h: narrow.set(w < 400),
        ),
        border=f"1px dashed {rx.color('gray', 8)}",
        padding="1em",
        width="520px",
        min_width="200px",
        max_width="100%",
        overflow="hidden",
        resize="horizontal",
    )
```

## Lazy Reveals

`on_intersect` reports whether the element is in the viewport and which
fraction of it is. With the default `threshold` of 0 it fires when the element
enters or leaves the viewport; `threshold=0.5` fires when half of it is in
view, and a list such as `[0, 0.5, 1]` fires at each. Parts of the element that
a scroll container clips count as out of view, so it works inside scrollable
boxes as well as on the page.

The cards below fade in once half of each is in view. Setting `disabled` once a
card has been seen stops observing it, so it stays visible when it scrolls out
again.

```python demo exec
def reveal(text: str) -> rx.Component:
    seen = rx.client_state(False)
    return rx.element_observer(
        rx.card(
            text,
            opacity=rx.cond(seen.value, "1", "0"),
            transform=rx.cond(seen.value, "none", "translateY(1em)"),
            transition="opacity 600ms, transform 600ms",
        ),
        on_intersect=lambda visible, ratio: seen.set(ratio >= 0.5),
        threshold=0.5,
        disabled=seen.value,
    )


def reveal_example():
    return rx.box(
        rx.text("Scroll down to reveal the cards."),
        rx.box(height="12em"),
        rx.vstack(*[reveal(f"Card {number}") for number in range(1, 6)]),
        height="12em",
        overflow_y="auto",
    )
```

`reveal` is a plain function, so every call creates its own client state var
and every card is revealed on its own.

## Scroll Spies

A scroll spy marks the section the reader is looking at. Here every section
reports whether it is in view, and the first one that is counts as the current
one:

```python demo exec
SPY_SECTIONS = ["Introduction", "Installation", "Usage", "Options"]


def scroll_spy_example():
    in_view = [rx.client_state(False) for _ in SPY_SECTIONS]

    def is_current(index: int) -> rx.Var[bool]:
        current = in_view[index].value
        for earlier in in_view[:index]:
            current = current & ~earlier.value
        return current

    return rx.hstack(
        rx.vstack(
            *[
                rx.text(
                    title,
                    weight=rx.cond(is_current(index), "bold", "regular"),
                    color_scheme=rx.cond(is_current(index), "accent", "gray"),
                )
                for index, title in enumerate(SPY_SECTIONS)
            ],
            align="start",
            min_width="8em",
        ),
        rx.box(
            *[
                rx.element_observer(
                    rx.box(
                        rx.text(title, size="4", weight="bold"),
                        rx.text(f"The {title.lower()} section."),
                        min_height="12em",
                    ),
                    on_intersect=visible.set,
                )
                for title, visible in zip(SPY_SECTIONS, in_view)
            ],
            height="12em",
            overflow_y="auto",
            padding_bottom="1em",
            flex="1",
        ),
        width="100%",
    )
```

## Back-To-Top Buttons

A back-to-top button appears once the reader has scrolled down. Rather than
following the scroll position, observe the top of the content and show the
button while it is out of view:

```python demo exec
def back_to_top_example():
    show = rx.client_state(False)
    return rx.box(
        rx.box(
            rx.element_observer(
                rx.text(
                    "Latest orders", size="4", weight="bold", padding_bottom="0.5em"
                ),
                on_intersect=lambda visible, ratio: show.set(~visible),
            ),
            *[rx.text(f"Order #{number}") for number in range(1001, 1031)],
            id="back_to_top_list",
            height="12em",
            overflow_y="auto",
        ),
        rx.cond(
            show.value,
            rx.button(
                "Back to top",
                on_click=rx.call_script(
                    "document.getElementById('back_to_top_list')"
                    ".scrollTo({top: 0, behavior: 'smooth'})"
                ),
                position="absolute",
                bottom="0.5em",
                right="1em",
            ),
        ),
        position="relative",
        width="100%",
    )
```

For the page itself, observe an empty box at the very top of the page.
`root_margin` grows or shrinks the viewport that `on_intersect` checks against,
in CSS margin syntax (pixels or percent) and `"0px"` by default. Growing it by
400 pixels at the top keeps the box in view, and the button hidden, until the
page has scrolled more than 400 pixels:

```python
def back_to_top_button() -> rx.Component:
    show = rx.client_state(False)
    return rx.fragment(
        rx.element_observer(
            rx.box(id="page_top"),
            on_intersect=lambda visible, ratio: show.set(~visible),
            root_margin="400px 0px 0px 0px",
        ),
        rx.cond(
            show.value,
            rx.button(
                "Back to top",
                on_click=rx.scroll_to("page_top"),
                position="fixed",
                bottom="1em",
                right="1em",
            ),
        ),
    )


def index() -> rx.Component:
    return rx.box(back_to_top_button(), ...)
```

## Position

`on_move` reports where the element is in the viewport whenever something
scrolls or resizes. A move without a scroll or resize, such as content inserted
above the element, is reported with the next one.

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

Use it when a line matters rather than the edges of the viewport, such as a
table of contents that marks a section as reached once its heading passes a
line 80 pixels below the top of the window:
`on_move=lambda x, y: passed.set(y <= 80)`. It reads the element's position on
every scroll event, so prefer `on_intersect` where whether the element is in
view is enough.

## Expanding Panels

CSS cannot transition a height to `auto`. Measure the content with `on_resize`
and transition to its height in pixels instead; `on_transition_end` tells when
the panel has settled.

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
                height=rx.cond(expanded.value, f"{content_height.value}px", "0px"),
                overflow="hidden",
                transition="height 300ms ease",
            ),
            on_transition_end=moving.set(False),
        ),
        rx.text(rx.cond(moving.value, "Moving", "Settled")),
    )
```

## Observing Another Element

With a child, the observer observes the child, which has to render an element
of its own: a fragment, `rx.cond`, `rx.match` or `rx.foreach` raises an error,
so wrap the element inside it instead. A child without an id gets one from
React's `useId`, which differs between the items of an `rx.foreach`, so an
observer works inside a loop too. Without a child, it observes the element whose
id is given as `target`, so it can sit anywhere in the page, and several
observers can observe one element:

```python
rx.fragment(
    rx.el.header(..., id="site_header"),
    rx.element_observer(
        target="site_header", on_resize=lambda w, h: header_height.set(h)
    ),
)
```

The observer follows the id rather than one element: it starts observing once
an element with the id is on the page, such as one that `rx.cond` shows later,
and moves to another element that takes the id over.

## Timing

Observing starts in an effect after the observer mounts, or once the element
is on the page if it comes later, so the first reports arrive just after the
render that shows the element. It restarts, with a first report, when `target`,
`threshold`, `root_margin`, `layout` or the set of triggers changes and when
`disabled` turns false again, but not when the observer merely re-renders.

After the first report, a change of the element's size fires `on_resize`, and
`on_move` if it moved the element, in the animation frame after the browser
laid it out. So a handler may resize the element it observes, like the
[responsive card](#responsive-components) above that stacks its parts once it
is narrow, without the browser raising a `ResizeObserver` loop error. Scrolls
and window resizes fire `on_move` right away.

`layout=True` is for a first measurement that has to be on screen in the same
frame as the element, such as the padding that keeps content clear of a fixed
header. Without it, the padding can lag a frame behind the header whenever the
layout mounts:

```python
header_height = rx.client_state(64)


def layout_with_fixed_header(*content: rx.Component) -> rx.Component:
    return rx.fragment(
        rx.element_observer(
            rx.el.header(..., position="fixed", top="0", width="100%"),
            on_resize=lambda w, h: header_height.set(h),
            layout=True,
        ),
        rx.el.main(*content, padding_top=f"{header_height.value}px"),
    )
```

## Calling The Backend

A backend event handler fits a trigger that fires rarely and needs the server.
It receives the trigger's arguments and may leave out trailing ones. This list
loads more rows whenever the marker at its end comes into view:

```python
class FeedState(rx.State):
    rows: list[str] = [f"Row {number}" for number in range(1, 21)]

    @rx.event
    def load_more(self, visible: bool):
        if visible:
            start = len(self.rows) + 1
            self.rows.extend(f"Row {number}" for number in range(start, start + 20))


def feed() -> rx.Component:
    return rx.box(
        rx.foreach(FeedState.rows, rx.text),
        rx.element_observer(rx.text("Loading..."), on_intersect=FeedState.load_more),
        height="20em",
        overflow_y="auto",
    )
```

For a trigger that fires continuously, limit how often the backend is called
with the [`throttle` and `debounce` event actions](/docs/events/event-actions/#throttle),
for example `on_move=PositionState.save.debounce(500)`.

## Notes

### Prerendering And Initial Values

Measurements exist only in the browser. In a prerendered page, as in a
production build, and until the observer first reports, its client state vars
hold their defaults. Choose defaults that look right before anything is
measured: the content shown, the wide layout, a header height close to the real
one. With a default of `0` in the fixed header example above, a prerendered
page would show its content under the header until the page hydrates.

### Performance

The observers on a page share the browser's observers: one `ResizeObserver`
watches all observed elements, one scroll and one resize listener on the window
serve all `on_move` triggers, one `IntersectionObserver` watches all elements
observed with the same `threshold` and `root_margin`, and one `MutationObserver`
watches for elements and ids coming and going. A scroll inside a scroll container only measures the elements
in it. Each time, all affected elements are measured before any is reported, so
the client state they set lands in one task and React renders it once.

`on_resize` and `on_move` report only values that changed. The first report
comes as soon as observing starts; later size changes come in the next
animation frame, the latest one per frame, while scrolls and window resizes are
reported as they happen. A `transitionend` listener on the element is the only
part each `on_transition_end` sets up for itself.

### Cleanup

An observer stops observing when it unmounts, when `disabled` becomes true,
and before observing restarts; a shared observer or listener goes away with the
last element that uses it. The client state vars keep the last values
reported.

### Browser Support

The observer relies on `ResizeObserver`, `IntersectionObserver`,
`MutationObserver` and the `transitionend` event, which all current browsers
support.
