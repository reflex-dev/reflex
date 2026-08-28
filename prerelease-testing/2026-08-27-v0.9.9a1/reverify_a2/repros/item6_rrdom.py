"""Item 6 (FINDING-010): library='react-router-dom' custom component must fail
compile with an actionable error naming the react-router migration; 'react-router' works."""
import reflex, sys
assert "site-packages" in reflex.__file__ and "envs/" in reflex.__file__, reflex.__file__
print("reflex.__file__:", reflex.__file__)
import reflex as rx

class BadDomLink(rx.Component):
    library = "react-router-dom"
    tag = "Link"
    to: rx.Var[str]

class GoodLink(rx.Component):
    library = "react-router"
    tag = "Link"
    to: rx.Var[str]

def try_build(label, cls):
    try:
        c = cls.create(to="/next")
        # gather imports / render -> triggers import resolution
        imports = c._get_all_imports()
        r = c.render()
        print(f"OK    {label}: built+rendered; import keys sample={list(imports)[:5]}")
    except Exception as e:
        print(f"REJECT {label}: {type(e).__name__}: {e}")

try_build("react-router-dom (bad)", BadDomLink)
try_build("react-router (good)", GoodLink)
