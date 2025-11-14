from reflex.compiler.templates import _RenderUtils
from reflex.vars.base import Var


def test_var_render_raw_js():
    v = Var("_event?.formData")
    assert _RenderUtils.render(v) == "_event?.formData"
