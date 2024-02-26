```python exec
import reflex as rx
from pcweb import constants, styles

dynamic_routes = (
"""
class State(rx.State):
    @rx.var
    def post_id(self) -> str:
        return self.router.page.params.get('pid', 'no pid')
        
@rx.page(route='/post/[pid]')
def post():
    \'''A page that updates based on the route.\'''
    return rx.heading(State.post_id)

app = rx.App()
"""
)


catch_all_route = (
"""
class State(rx.State):
    @rx.var
    def user_post(self) -> str:
        args = self.router.page.params
        usernames = args.get('username', [])
        return f'Posts by {', '.join(usernames)}'

@rx.page(route='/users/[id]/posts/[...username]')
def post():
    return rx.center(
        rx.text(State.user_post)
    )


app = rx.App()
"""  
)


optional_catch_all_route = (
"""
class State(rx.State):
    @rx.var
    def user_post(self) -> str:
        args = self.router.page.params
        usernames = args.get('username', [])
        return f'Posts by {', '.join(usernames)}'

@rx.page(route='/users/[id]/posts/[[...username]]')
def post():
    return rx.center(
        rx.text(State.user_post)
    )


app = rx.App()
"""  
)
```

# Dynamic Routes

Dynamic routes in Reflex allow you to handle varying URL structures, enabling you to create flexible
and adaptable web applications. This section covers regular dynamic routes, catch-all routes,
and optional catch-all routes, each with detailed examples.

## Regular Dynamic Routes

Regular dynamic routes in Reflex allow you to match specific segments in a URL dynamically.

Example:

```python
{dynamic_routes}
```

In this case, a route like `/user/john/posts/5` would display "Posts by john: Post 5".

## Catch-All Routes

Catch-all routes in Reflex allow you to match any number of segments in a URL dynamically.

Example:

```python
{catch_all_route}
```

In this case, the `...username` catch-all pattern captures any number of segments after
`/users/`, allowing URLs like `/users/2/john/` and `/users/1/john/doe/` to match the route.

## Optional Catch-All Routes

Optional catch-all routes, enclosed in double square brackets (`[[...]]`). This indicates that the specified segments
are optional, and the route can match URLs with or without those segments.

Example:

```python
{optional_catch_all_route}
```

Optional catch-all routes allow matching URLs with or without specific segments.
Each optional catch-all pattern should be independent and not nested within another catch-all pattern.

```md alert
# Catch-all routes must be placed at the end of the URL pattern to ensure proper route matching.
```

### Routes Validation Table

| Route Pattern                                         | Example URl                                            |    valid |
|:------------------------------------------------------|:-------------------------------------------------------|---------:|
| `/users/posts`                                        | `/users/posts`                                         |    valid |
| `/products/[category]`                                | `/products/electronics`                                |    valid |                                                  |         |
| `/users/[username]/posts/[id]`                       | `/users/john/posts/5`                                  |    valid |
| `/users/[...username]/posts`                          | `/users/john/posts`                                    |  invalid |
|                                                       | `/users/john/doe/posts`                                |  invalid |
| `/users/[...username]`                                | `/users/john/`                                         |    valid |
|                                                       | `/users/john/doe`                                      |    valid |
| `/products/[category]/[...subcategories]`             | `/products/electronics/laptops`                        |    valid |
|                                                       | `/products/electronics/laptops/lenovo`                 |    valid |
| `/products/[category]/[[...subcategories]]`           | `/products/electronics`                                |    valid |
|                                                       | `/products/electronics/laptops`                        |    valid |
|                                                       | `/products/electronics/laptops/lenovo`                 |    valid |
|                                                       | `/products/electronics/laptops/lenovo/thinkpad`        |    valid |
| `/products/[category]/[...subcategories]/[...items]`  | `/products/electronics/laptops`                        |  invalid |
|                                                       | `/products/electronics/laptops/lenovo`                 |  invalid |
|                                                       | `/products/electronics/laptops/lenovo/thinkpad`        |  invalid |
