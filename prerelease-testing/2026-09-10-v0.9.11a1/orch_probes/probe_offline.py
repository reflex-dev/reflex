"""Offline probes for reflex 0.9.11a1 items not covered by a cluster agent yet.

Run from a neutral cwd with a venv python:
    $SB/envs/smoke/bin/python probe_offline.py
"""
import io, json, os, sys, traceback, contextlib

import reflex  # noqa
VENV = os.environ.get("EXPECT_VENV", "/envs/smoke/")
assert VENV in reflex.__file__, reflex.__file__

results = {}


def probe(name):
    def deco(fn):
        try:
            out = fn()
            results[name] = {"ok": True, "detail": out}
        except BaseException as e:  # noqa: BLE001
            results[name] = {"ok": False, "exc": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-800:]}
        return fn
    return deco


@probe("import_reflex_testing_bare")
def _():
    import reflex.testing  # noqa
    return "import ok; AppHarness=%r" % (hasattr(reflex.testing, "AppHarness"),)


@probe("apphamess_missing_deps_error")
def _():
    from reflex.testing import AppHarness
    import tempfile, pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    def App():
        import reflex as rx
        class S(rx.State):
            v: int = 0
        app = rx.App()
        app.add_page(lambda: rx.text("hi"), route="/")
    try:
        h = AppHarness.create(root=d, app_source=App)
        h.__enter__()
    except BaseException as e:  # noqa: BLE001
        return {"raised": f"{type(e).__name__}: {e}"[:400],
                "mentions_extra": "reflex[testing]" in str(e) or "testing" in str(e)}
    else:
        try:
            h.__exit__(None, None, None)
        except Exception:
            pass
        return {"raised": None, "note": "AppHarness started without the testing extra"}


@probe("rx_model_without_sqlmodel")
def _():
    import reflex as rx
    try:
        import sqlmodel  # noqa
        return {"skipped": "sqlmodel installed in this venv"}
    except ImportError:
        pass
    try:
        class Thing(rx.Model, table=True):  # type: ignore[call-arg]
            name: str
    except BaseException as e:  # noqa: BLE001
        msg = str(e)
        return {"raised": f"{type(e).__name__}: {msg}"[:400],
                "mentions_db_extra": "reflex[db]" in msg or "sqlmodel" in msg}
    return {"raised": None, "note": "no error without sqlmodel"}


@probe("plotly_id_prop_in_render")
def _():
    import reflex as rx
    try:
        fig = {"data": [{"x": [1, 2], "y": [3, 4], "type": "scatter"}], "layout": {}}
        c = rx.plotly(data=fig, id="myplot")
    except BaseException as e:  # noqa: BLE001
        return {"construct_error": f"{type(e).__name__}: {e}"[:300]}
    r = c.render()
    props = r.get("props", [])
    return {"props": [p for p in props if "id" in p.lower() or "divId" in p],
            "has_id": any(p.startswith("id=") for p in props),
            "has_divId": any("divId" in p for p in props)}


@probe("cachedvar_attributeerror_masking")
def _():
    import reflex as rx

    class Boom:
        def __getattr__(self, k):
            raise AttributeError("inner boom: " + k)

    class S(rx.State):
        n: int = 1

        @rx.var(cache=True)
        def bad(self) -> int:
            raise AttributeError("deliberate inner AttributeError")

    try:
        _ = S.bad._var_full_name if hasattr(S.bad, "_var_full_name") else str(S.bad)
    except BaseException as e:  # noqa: BLE001
        return {"raised": f"{type(e).__name__}: {e}"[:300],
                "masked": "_cached_get_all_var_data" in str(e)}
    return {"raised": None}


@probe("load_config_deprecation")
def _():
    import warnings
    from reflex_base import config as bcfg
    has_load = hasattr(bcfg, "_load_config")
    has_get = hasattr(bcfg, "_get_config")
    if not has_load:
        return {"_load_config": False, "_get_config": has_get}
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                bcfg._load_config()
        except BaseException as e:  # noqa: BLE001
            return {"call_error": f"{type(e).__name__}: {e}"[:200], "warnings": [str(x.message)[:200] for x in w],
                    "stdout": buf.getvalue()[-400:]}
        return {"_load_config": True, "_get_config": has_get,
                "warnings": [str(x.message)[:250] for x in w],
                "output": buf.getvalue()[-400:]}


@probe("frontend_path_validation")
def _():
    import reflex as rx
    out = {}
    for bad in ["../x", "a\\b", "C:foo", "/ok/../x", "//srv"]:
        try:
            rx.Config(app_name="x", frontend_path=bad)
            out[bad] = "ACCEPTED"
        except BaseException as e:  # noqa: BLE001
            out[bad] = f"{type(e).__name__}: {str(e)[:160]}"
    for good in ["/app", "/a/b", ""]:
        try:
            c = rx.Config(app_name="x", frontend_path=good)
            out[good or "(empty)"] = f"accepted -> {c.frontend_path!r}"
        except BaseException as e:  # noqa: BLE001
            out[good or "(empty)"] = f"REJECTED {type(e).__name__}: {str(e)[:160]}"
    return out


@probe("reserve_stdout")
def _():
    from reflex_base.utils import log as rlog
    if not hasattr(rlog, "reserve_stdout"):
        return {"present": False}
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        with rlog.reserve_stdout():
            logger = rlog.get_logger("reflex_base.probe") if hasattr(rlog, "get_logger") else None
            if logger:
                logger.warning("inside reservation")
            print("document-line", file=sys.stdout)
        logger2 = rlog.get_logger("reflex_base.probe") if hasattr(rlog, "get_logger") else None
        if logger2:
            logger2.warning("outside reservation")
    return {"present": True, "stdout": out.getvalue()[-300:], "stderr": err.getvalue()[-300:]}


@probe("hosting_cli_version_compare")
def _():
    import importlib, pkgutil
    import reflex_hosting_cli as rhc
    found = []
    for m in pkgutil.walk_packages(rhc.__path__, "reflex_hosting_cli."):
        try:
            mod = importlib.import_module(m.name)
        except Exception:
            continue
        for attr in dir(mod):
            if "version" in attr.lower() and callable(getattr(mod, attr, None)):
                found.append(f"{m.name}.{attr}")
    out = {"candidates": found[:12]}
    try:
        from reflex_hosting_cli.utils import console  # noqa
    except Exception:
        pass
    for fn_path in found:
        modname, attr = fn_path.rsplit(".", 1)
        fn = getattr(importlib.import_module(modname), attr)
        if attr.startswith("_") or "check" not in attr.lower():
            continue
        for v in ["0.7.6.post1", "0.9.11a1", "0.9.10.post2", "1.0.0rc1"]:
            try:
                fn(v)
                out[f"{attr}({v})"] = "ok"
            except TypeError:
                break
            except BaseException as e:  # noqa: BLE001
                out[f"{attr}({v})"] = f"{type(e).__name__}: {str(e)[:120]}"
    return out


@probe("otel_inert_in_bare_env")
def _():
    mods = sorted(m for m in sys.modules if m.startswith("opentelemetry"))
    from reflex_base import otel
    return {"opentelemetry_modules_imported": mods, "otel_enabled": getattr(otel, "enabled", "?")}


print(json.dumps(results, indent=1, default=str))
