```python exec
import reflex as rx
from pcweb import constants, styles
```

# Dynamic Routes

Dynamic routes in Reflex allow you to handle varying URL structures, enabling you to create flexible
and adaptable web applications. This section covers regular dynamic routes, catch-all routes,
and optional catch-all routes, each with detailed examples.

## Regular Dynamic Routes

Regular dynamic routes in Reflex allow you to match specific segments in a URL dynamically. A regular dynamic route is defined by square brackets in a route string / url pattern. For example `/users/[id]` or `/products/[category]`. These dynamic route arguments can be accessed through a state var. For the examples above they would be `rx.State.id` and `rx.State.category` respectively.

```md alert info
# Why is the state var accessed as `rx.State.id`?

The dynamic route arguments are accessible as `rx.State.id` and `rx.State.category` here as the var is added to the root state, so that it is accessible from any state.
```

Example:

```python
@rx.page(route='/post/[pid]')
def post():
    '''A page that updates based on the route.'''
    # Displays the dynamic part of the URL, the post ID
    return rx.heading(rx.State.pid)

app = rx.App()
```

The [pid] part in the route is a dynamic segment, meaning it can match any value provided in the URL. For instance, `/post/5`, `/post/10`, or `/post/abc` would all match this route.

If a user navigates to `/post/5`, `State.post_id` will return `5`, and the page will display `5` as the heading. If the URL is `/post/xyz`, it will display `xyz`. If the URL is `/post/` without any additional parameter, it will display `""`.

### Adding Dynamic Routes

Adding dynamic routes uses the `add_page` method like any other page. The only difference is that the route string contains dynamic segments enclosed in square brackets.

If you are using the `app.add_page` method to define pages, it is necessary to add the dynamic routes first, especially if they use the same function as a non dynamic route.

For example the code snippet below will:

```python
app.add_page(index, route="/page/[page_id]", on_load=DynamicState.on_load)
app.add_page(index, route="/static/x", on_load=DynamicState.on_load)
app.add_page(index)
```

But if we switch the order of adding the pages, like in the example below, it will not work:

```python
app.add_page(index, route="/static/x", on_load=DynamicState.on_load)
app.add_page(index)
app.add_page(index, route="/page/[page_id]", on_load=DynamicState.on_load)
```

## Catch-All Routes

Catch-all routes in Reflex allow you to match any number of segments in a URL dynamically.

Example:

```python
class State(rx.State):
    @rx.var
    def user_post(self) -> str:
        args = self.router.page.params
        usernames = args.get('splat', [])
        return f"Posts by \{', '.join(usernames)}"

@rx.page(route='/users/[id]/posts/[[...splat]]')
def post():
    return rx.center(
        rx.text(State.user_post)
    )


app = rx.App()
```

In this case, the `...splat` catch-all pattern captures any number of segments after
`/users/`, allowing URLs like `/users/2/posts/john/` and `/users/1/posts/john/doe/` to match the route.

```md alert
# Catch-all routes must be named `splat` and be placed at the end of the URL pattern to ensure proper route matching.
```

### Routes Validation Table

| Route Pattern                                    | Example URl                                     |   valid |
| :----------------------------------------------- | :---------------------------------------------- | ------: |
| `/users/posts`                                   | `/users/posts`                                  |   valid |
| `/products/[category]`                           | `/products/electronics`                         |   valid |
| `/users/[username]/posts/[id]`                   | `/users/john/posts/5`                           |   valid |
| `/users/[[...splat]]/posts`                      | `/users/john/posts`                             | invalid |
|                                                  | `/users/john/doe/posts`                         | invalid |
| `/users/[[...splat]]`                            | `/users/john/`                                  |   valid |
|                                                  | `/users/john/doe`                               |   valid |
| `/products/[category]/[[...splat]]`              | `/products/electronics/laptops`                 |   valid |
|                                                  | `/products/electronics/laptops/lenovo`          |   valid |
| `/products/[category]/[[...splat]]`              | `/products/electronics`                         |   valid |
|                                                  | `/products/electronics/laptops`                 |   valid |
|                                                  | `/products/electronics/laptops/lenovo`          |   valid |
|                                                  | `/products/electronics/laptops/lenovo/thinkpad` |   valid |
| `/products/[category]/[[...splat]]/[[...splat]]` | `/products/electronics/laptops`                 | invalid |
|                                                  | `/products/electronics/laptops/lenovo`          | invalid |
|                                                  | `/products/electronics/laptops/lenovo/thinkpad` | invalid |
