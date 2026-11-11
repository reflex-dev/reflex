"""ENT-01 / ENT-02 / CLI-03: deprecated reflex names still work and warn."""
import io, contextlib, os, warnings
import reflex
assert os.environ["EXPECT_VENV"] in reflex.__file__, reflex.__file__
warnings.simplefilter("always")
for label, stmt in [
    ("ENT-01 dynamic.bundled_libraries", "from reflex_base.components import dynamic; v = dynamic.bundled_libraries; print(type(v).__name__, len(v))"),
    ("ENT-01 reflex.components.dynamic.bundled_libraries", "from reflex.components import dynamic as d2; v = d2.bundled_libraries; print(type(v).__name__, len(v))"),
    ("ENT-02 from reflex.page import DECORATED_PAGES", "from reflex.page import DECORATED_PAGES; print(type(DECORATED_PAGES).__name__)"),
    ("CLI-03 get_config(reload=True)", "from reflex.config import get_config; c = get_config(reload=True); print(type(c).__name__)"),
    ("rxe get_bundled_libraries()", "from reflex_enterprise.vars import get_bundled_libraries; print(len(get_bundled_libraries()))"),
]:
    buf = io.StringIO()
    with warnings.catch_warnings(record=True) as w, contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        warnings.simplefilter("always")
        try:
            exec(stmt, {})
            err = ""
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
    out = " ".join(buf.getvalue().split())
    print(f"{label}: err={err!r} out={out[:300]!r} warnings={[f'{x.category.__name__}: {str(x.message)[:120]}' for x in w]}")
