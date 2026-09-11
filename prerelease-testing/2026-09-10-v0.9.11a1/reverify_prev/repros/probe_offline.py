"""Offline re-verification probes for the 0.9.9a1 campaign findings that a2 did NOT fix.

Run from a NEUTRAL cwd (never /home/user/reflex) with the venv python under test:
    $SB/envs/smoke/bin/python probe_offline.py        # reflex 0.9.11a1
    $SB/envs/base0910/bin/python probe_offline.py     # reflex 0.9.10.post2

Covers (no server, no browser):
  F014  rx.Model(table=True) without sqlmodel -> bare TypeError instead of reflex[db] hint
  F024  CachedVarOperation masks AttributeError raised inside a cached var computation
  F020  rx.plotly id= prop: compiled JSX emits id (react-plotly.js wants divId)
  F017a bundle_library() wiped by reset_bundled_libraries() (what compile_app does)
  F017b dynamic serializer never rewrites subpath imports of a bundled lib
  SWEEP (a2-fixed items, quick confirmation only):
      S002  PEP695 alias state var assignment
      S006  PEP695 alias-annotated event handler arg passed uncalled
      S007  upload filename sanitizer for all-dots names
      S027  console warning backslash-escaped brackets
      S010  library="react-router-dom" custom component
      S008/9 deprecation shims: bundled_libraries / DECORATED_PAGES / get_config(reload=True)
"""

import io
import re
import sys
import traceback
import warnings

import reflex

assert "site-packages" in reflex.__file__ and "/envs/" in reflex.__file__, reflex.__file__
print(f"### reflex.__file__ = {reflex.__file__}")

import reflex as rx  # noqa: E402

print(f"### reflex version = {rx.constants.Reflex.VERSION}")
print()


def hdr(name: str) -> None:
    print(f"===== {name} =====")


# ---------------------------------------------------------------- F014
hdr("F014 rx.Model(table=True) without sqlmodel")
try:
    import sqlmodel  # noqa: F401

    print("F014 SKIP: sqlmodel IS installed in this venv")
except ImportError:
    try:
        ns: dict = {}
        exec(
            "import reflex as rx\n"
            "class Item(rx.Model, table=True):\n"
            "    name: str\n",
            ns,
        )
        print("F014 RESULT: class definition SUCCEEDED (no error)")
    except Exception as e:  # noqa: BLE001
        msg = f"{type(e).__name__}: {e}"
        helpful = "reflex[db]" in str(e) or "install" in str(e).lower()
        print(f"F014 RESULT: {msg}")
        print(f"F014 helpful_db_hint={helpful}")
print()

# ---------------------------------------------------------------- F024
hdr("F024 CachedVarOperation masks AttributeError in cached computation")
try:
    import dataclasses

    from reflex_base.vars.base import (
        CachedVarOperation,
        VarData,
        cached_property_no_lock,
    )
    from reflex_base.vars.sequence import StringVar

    @dataclasses.dataclass(eq=False, frozen=True, slots=True)
    class BoomVarOperation(CachedVarOperation, StringVar[str]):
        """A cached var operation whose VarData computation raises AttributeError."""

        _var_value: str = ""

        @cached_property_no_lock
        def _cached_var_name(self) -> str:
            return f'"{self._var_value}"'

        @cached_property_no_lock
        def _cached_get_all_var_data(self) -> VarData | None:
            raise AttributeError(
                "module 'some.module' has no attribute 'the_real_problem'"
            )

    v = BoomVarOperation(_var_value="hi", _var_type=str, _js_expr="")
    try:
        v._get_all_var_data()
        print("F024 RESULT: no error raised (masking gone AND error gone?)")
    except Exception as e:  # noqa: BLE001
        masked = "_cached_get_all_var_data not found" in str(e)
        cause = e.__cause__ or e.__context__
        print(f"F024 RESULT: {type(e).__name__}: {e}")
        print(f"F024 masked={masked} chained_cause={type(cause).__name__ if cause else None}")
        print(f"F024 real_error_visible={'the_real_problem' in traceback.format_exc()}")
except Exception:  # noqa: BLE001
    print("F024 PROBE ERROR:")
    traceback.print_exc()
print()

# ---------------------------------------------------------------- F020
hdr("F020 rx.plotly id prop -> divId")
try:
    import plotly.graph_objects as go

    fig = go.Figure(data=[go.Bar(x=[1, 2], y=[3, 4])])
    comp = rx.plotly(data=fig, id="the-plot")
    rendered = str(comp.render())
    has_id = re.search(r'"?id"?\s*[:=]\s*"the-plot"', rendered) is not None
    has_divid = "divId" in rendered
    print(f"F020 rendered_contains_id={has_id} rendered_contains_divId={has_divid}")
    frag = [line for line in rendered.splitlines() if "the-plot" in line][:3]
    print(f"F020 fragment={frag}")
    import reflex_components_plotly

    print(f"F020 plotly wrapper file={reflex_components_plotly.__file__}")
except Exception:  # noqa: BLE001
    print("F020 PROBE ERROR:")
    traceback.print_exc()
print()

# ---------------------------------------------------------------- F017
hdr("F017 bundle_library + subpath rewrite")
try:
    from reflex.components.dynamic import bundle_library, reset_bundled_libraries
    from reflex.utils.serializers import serialize

    def current_bundled():
        try:
            from reflex_base.registry import RegistrationContext

            return list(RegistrationContext.ensure_context().bundled_libraries)
        except Exception:  # noqa: BLE001
            from reflex.components import dynamic as _dyn

            return list(_dyn.bundled_libraries)

    print(f"F017 default bundled={current_bundled()}")
    bundle_library("lucide-react")
    after = current_bundled()
    print(f"F017 after bundle_library: lucide-react present={('lucide-react' in after)}")

    code = serialize(rx.vstack(rx.icon("apple"), rx.text("hi")))
    bare = [ln for ln in str(code).splitlines() if "lucide-react/dist" in ln]
    print(f"F017b bare subpath import line: {bare[:1]}")
    print(f"F017b subpath_not_rewritten={bool(bare)}")

    reset_bundled_libraries()
    after_reset = current_bundled()
    wiped = "lucide-react" not in after_reset
    print(f"F017a user registration wiped by reset_bundled_libraries={wiped}")
except Exception:  # noqa: BLE001
    print("F017 PROBE ERROR:")
    traceback.print_exc()
print()

# ---------------------------------------------------------------- SWEEP S002/S006
hdr("SWEEP S002/S006 PEP695 alias (typing_extensions backport on 3.11)")
try:
    from typing import Literal, TypeVar

    from typing_extensions import TypeAliasType

    Key = TypeAliasType("Key", Literal["a", "b"])
    Plain = TypeAliasType("Plain", str)
    _K = TypeVar("_K")
    _V = TypeVar("_V")
    Pair = TypeAliasType("Pair", dict[_K, _V], type_params=(_K, _V))

    class AliasState(rx.State):
        k: Key = "a"  # pyright: ignore[reportInvalidTypeForm]
        p: Plain = ""  # pyright: ignore[reportInvalidTypeForm]

        @rx.event
        def choose(self, value: Key):  # pyright: ignore[reportInvalidTypeForm]
            self.k = value

    inst = AliasState(_reflex_internal_init=True)
    try:
        inst.k = "b"
        inst.p = "x"
        print("S002 RESULT: alias setattr OK")
    except Exception as e:  # noqa: BLE001
        print(f"S002 RESULT: FAIL {type(e).__name__}: {e}")

    try:
        rx.input(on_change=AliasState.choose).render()
        print("S006 RESULT: uncalled alias-annotated handler OK")
    except Exception as e:  # noqa: BLE001
        print(f"S006 RESULT: FAIL {type(e).__name__}: {e}")
except Exception:  # noqa: BLE001
    print("SWEEP alias PROBE ERROR:")
    traceback.print_exc()
print()

# ---------------------------------------------------------------- SWEEP S007
hdr("SWEEP S007 upload filename sanitizer")
try:
    from reflex_components_core.core._upload import _sanitize_upload_filename as s

    for name in ["..", "./../.", "..\\", "/..", "...", "../x.txt", "a/../b"]:
        print(f"S007 {name!r} -> {s(name)!r}")
except Exception:  # noqa: BLE001
    print("S007 PROBE ERROR:")
    traceback.print_exc()
print()

# ---------------------------------------------------------------- SWEEP S027
hdr("SWEEP S027 console warning bracket escaping")
try:
    from typing import Any

    from typing_extensions import TypeAliasType

    _K2 = TypeVar("_K2")
    _V2 = TypeVar("_V2")
    Pair2 = TypeAliasType("Pair2", dict[_K2, _V2], type_params=(_K2, _V2))

    class FormState(rx.State):
        key: str = ""

        @rx.event
        def submit_alias(self, form_data: Pair2[str, str]):  # pyright: ignore[reportInvalidTypeForm]
            self.key = str(form_data)

        @rx.event
        def submit_plain(self, form_data: dict[str, Any]):
            self.key = str(form_data)

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rx.form(rx.input(name="x"), on_submit=FormState.submit_alias).render()
        rx.form(rx.input(name="x"), on_submit=FormState.submit_plain).render()
    finally:
        sys.stdout = old
    out = buf.getvalue()
    esc = chr(92) + "["
    has_esc = esc in out
    print(f"S027 captured warning chars: has_backslash_bracket={has_esc}")
    for line in out.splitlines()[:6]:
        print(f"S027 | {line}")
except Exception:  # noqa: BLE001
    print("S027 PROBE ERROR:")
    traceback.print_exc()
print()

# ---------------------------------------------------------------- SWEEP S010
hdr("SWEEP S010 library='react-router-dom' custom component")
try:

    class BadDomLink(rx.Component):
        library = "react-router-dom"
        tag = "Link"
        to: rx.Var[str]

    class GoodLink(rx.Component):
        library = "react-router"
        tag = "Link"
        to: rx.Var[str]

    for label, cls in [("react-router-dom", BadDomLink), ("react-router", GoodLink)]:
        try:
            c = cls.create(to="/next")
            c._get_all_imports()
            c.render()
            print(f"S010 {label}: BUILT (no error)")
        except Exception as e:  # noqa: BLE001
            print(f"S010 {label}: {type(e).__name__}: {str(e)[:200]}")
except Exception:  # noqa: BLE001
    print("S010 PROBE ERROR:")
    traceback.print_exc()
print()

# ---------------------------------------------------------------- SWEEP shims
hdr("SWEEP S008/S009 deprecation shims")


def probe(label, fn):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            r = fn()
        except Exception as e:  # noqa: BLE001
            print(f"SHIM {label}: CRASH {type(e).__name__}: {str(e)[:120]}")
            return
        msgs = [str(x.message)[:80] for x in w]
        print(f"SHIM {label}: OK {type(r).__name__} warnings={len(msgs)} {msgs[:1]}")


probe(
    "dynamic.bundled_libraries",
    lambda: __import__(
        "reflex.components.dynamic", fromlist=["bundled_libraries"]
    ).bundled_libraries,
)
probe(
    "dynamic.DEFAULT_BUNDLED_LIBRARIES",
    lambda: getattr(
        __import__("reflex.components.dynamic", fromlist=["x"]),
        "DEFAULT_BUNDLED_LIBRARIES",
    ),
)


def get_dp():
    from reflex.page import DECORATED_PAGES

    return DECORATED_PAGES


probe("reflex.page.DECORATED_PAGES", get_dp)
probe("get_config(reload=True)", lambda: rx.config.get_config(reload=True))
print()
print("### probe_offline done")
