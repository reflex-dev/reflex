"""This component wraps the local `hello.js` which is supplied as an external asset."""

import reflex as rx

# Because the top-level element in Hello is a `<div>` and all other props are passed
# directly through, we can subclass `Div` to get the base behavior automatically.
from reflex.components.el.elements.typography import Div

# Defining the asset with a module-relative path will result in copying the
# file into a subdir of the .web/public directory
component_asset = rx.asset(path="hello.jsx", shared=True)


class Hello(Div):
    # To access the JS as an import, use an absolute path (rooted in `.web`)
    # through `/public` where the assets exist in the frontend build.
    library = f"/public/{component_asset}"

    tag = "Hello"

    name: rx.Var[str]


hello = Hello.create
