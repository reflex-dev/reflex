"""Tests for the I18nPlugin: config activation and catalog emission."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from reflex_i18n import I18nPlugin, t
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.plugin import _RUNTIME_SOURCE
from reflex_i18n.registry import clear_messages
from reflex_i18n.runtime import negotiate_locale

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node missing")

# Stand-ins for the modules the client runtime imports. Effects run during the
# render call; state setters and navigations are recorded for the driver.
_RUNTIME_STUBS = {
    "react": """
export const createContext = (value) => ({ value, Provider: "Provider" });
export const createElement = (type, props, ...children) => ({ type, props, children });
export const Fragment = "Fragment";
export const useCallback = (fn) => fn;
export const useContext = (context) => context.value;
export const useEffect = (effect) => {
  effect();
};
export const useState = (initial) => [
  initial,
  (next) => globalThis.stateUpdates.push(next),
];
""",
    "react-router": """
export const useHref = (to) => to;
export const useLocation = () => globalThis.routerLocation;
export const useNavigate = () => (to, options) =>
  globalThis.navigations.push([to, options ?? null]);
""",
}

# Renders one runtime component with browser globals from argv and prints the
# navigations and state updates its effects made.
_RUNTIME_DRIVER = """
import { pathToFileURL } from "node:url";
const [modulePath, component, env] = process.argv.slice(2);
const { pathname, languages } = JSON.parse(env);
globalThis.navigations = [];
globalThis.stateUpdates = [];
globalThis.routerLocation = { pathname, search: "", hash: "" };
Object.defineProperty(globalThis, "navigator", {
  value: { languages, language: languages[0] },
  configurable: true,
});
globalThis.document = { cookie: "", documentElement: {} };
globalThis.location = { protocol: "http:" };
const mod = await import(pathToFileURL(modulePath).href);
mod[component]({ children: null });
process.stdout.write(JSON.stringify({ navigations, stateUpdates }));
"""


def _render_runtime(
    tmp_path: Path,
    component: str,
    *,
    locales: list[str],
    default_locale: str,
    url_routing: bool = False,
    default_at_root: bool = True,
    pathname: str = "/",
    languages: tuple[str, ...] = ("en",),
) -> dict[str, Any]:
    """Render a component of the shipped client runtime against stub modules.

    Args:
        tmp_path: Directory for the runtime, its stubs and the driver.
        component: The exported component to render.
        locales: The configured locales.
        default_locale: The configured default locale.
        url_routing: Whether locales are routed through the URL.
        default_at_root: Whether the default locale is served unprefixed.
        pathname: The router location's path.
        languages: The browser's preferred languages.

    Returns:
        The recorded ``navigations`` and ``stateUpdates``.
    """
    config = {
        "locales": locales,
        "defaultLocale": default_locale,
        "urlRouting": url_routing,
        "defaultAtRoot": default_at_root,
        "cookieName": "reflex_locale",
        "deployUrl": "",
    }
    index = "".join(f"export const {k} = {json.dumps(v)};\n" for k, v in config.items())
    index += (
        "export const defaultPlural = (n) => Number(n != 1);\n"
        "export const loaders = Object.fromEntries(locales.map((locale) => "
        "[locale, async () => ({ messages: new Map() })]));\n"
    )
    stubs = {**_RUNTIME_STUBS, "$/i18n/index.js": index}
    source = _RUNTIME_SOURCE.read_text(encoding="utf-8")
    for specifier, stub_source in stubs.items():
        stub = tmp_path / (specifier.replace("/", "_").replace("$", "") + ".mjs")
        stub.write_text(stub_source)
        source = source.replace(f'from "{specifier}"', f'from "./{stub.name}"')
    module = tmp_path / "i18n.mjs"
    module.write_text(source)
    driver = tmp_path / "driver.mjs"
    driver.write_text(_RUNTIME_DRIVER)
    env = json.dumps({"pathname": pathname, "languages": list(languages)})
    result = subprocess.run(
        ["node", str(driver), str(module), component, env],
        capture_output=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture(autouse=True)
def clean_registry():
    """Isolate the message registry and global config per test.

    Yields:
        None
    """
    clear_messages()
    set_active_i18n_config(None)
    yield
    clear_messages()
    set_active_i18n_config(None)


def _write_po(catalog_dir: Path, locale: str, body: str) -> None:
    catalog_dir.mkdir(parents=True, exist_ok=True)
    header = (
        'msgid ""\nmsgstr ""\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
    )
    (catalog_dir / f"{locale}.po").write_text(header + body, encoding="utf-8")


def test_plugin_activates_config():
    I18nPlugin(locales=["en", "de"], default_locale="en")
    # rx.t requires an active config; constructing the plugin provides it.
    var = t("Hello")
    assert 't_("Hello"' in str(var)


def test_t_without_plugin_raises():
    with pytest.raises(RuntimeError, match="requires the i18n plugin"):
        t("Hello")


def test_plugin_ships_client_runtime():
    plugin = I18nPlugin(locales=["en"])
    assets = dict(plugin.get_static_assets())
    runtime = assets[Path("utils/i18n.js")]
    assert isinstance(runtime, str)
    assert "useTranslation" in runtime


def test_plugin_emits_index_and_locale_modules(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_po(tmp_path / "locales", "de", 'msgid "Hello"\nmsgstr "Hallo"\n')

    plugin = I18nPlugin(locales=["en", "de"], default_locale="en")
    t("Hello")

    outputs = dict(plugin._compile_catalogs())
    assert set(outputs) == {"i18n/index.js", "i18n/en.js", "i18n/de.js"}
    assert '"de": () => import("$/i18n/de.js")' in outputs["i18n/index.js"]
    assert '["Hello", "Hallo"]' in outputs["i18n/de.js"]
    # The default (source) locale needs no translation entry.
    assert '"Hello"' not in outputs["i18n/en.js"]


def test_plugin_missing_catalog_file_still_emits_module(
    tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    plugin = I18nPlugin(locales=["en", "de"], default_locale="en")
    t("Hello")

    outputs = dict(plugin._compile_catalogs())
    # de.js exists but is empty (falls back to source text at runtime).
    assert "i18n/de.js" in outputs
    assert "export const messages" in outputs["i18n/de.js"]
    assert "No translation catalog found" in capsys.readouterr().out


def test_plugin_emits_default_plural_in_index(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # French source locale without a catalog: the client fallback rule comes
    # from Babel's CLDR table, not the English (n != 1) default. Only the
    # source locale is configured, so no catalog is missing.
    plugin = I18nPlugin(locales=["fr"], default_locale="fr")
    outputs = dict(plugin._compile_catalogs())
    assert (
        "export const defaultPlural = (n) => Number((n > 1));"
        in outputs["i18n/index.js"]
    )


@requires_node
@pytest.mark.parametrize(
    ("locales", "default_locale", "languages", "expected"),
    [
        (["en-GB", "en-us"], "en-GB", ("en-US",), "en-us"),
        (["pt-PT", "pt-br"], "pt-PT", ("pt-BR",), "pt-br"),
        (["EN", "de"], "de", ("en-US",), "EN"),
        (["en", "de"], "en", ("fr-CA", "de-AT"), "de"),
        (["en", "de"], "en", ("fr",), "en"),
    ],
)
def test_client_negotiation_matches_server(
    tmp_path: Path,
    locales: list[str],
    default_locale: str,
    languages: tuple[str, ...],
    expected: str,
):
    """Without a chosen locale, the browser picks the server's locale."""
    rendered = _render_runtime(
        tmp_path,
        "I18nProvider",
        locales=locales,
        default_locale=default_locale,
        languages=languages,
    )
    server = negotiate_locale(", ".join(languages), locales, default_locale)
    assert rendered["stateUpdates"][0] == server == expected


@requires_node
@pytest.mark.parametrize(
    ("default_at_root", "pathname", "expected"),
    [
        (False, "/pricing", [["/en/pricing", {"replace": True}]]),
        (False, "/de/pricing", []),
        (True, "/pricing", []),
    ],
)
def test_routing_wrap_redirects_unprefixed_path(
    tmp_path: Path, default_at_root: bool, pathname: str, expected: list
):
    """The redirect to a prefixed URL runs without client translation in use.

    ``HreflangLinks`` is on every page with URL routing; the provider is only
    pulled in by client translation, so it must not redirect a second time.
    """
    options: dict[str, Any] = {
        "locales": ["en", "de"],
        "default_locale": "en",
        "url_routing": True,
        "default_at_root": default_at_root,
        "pathname": pathname,
    }
    assert _render_runtime(tmp_path, "HreflangLinks", **options)["navigations"] == (
        expected
    )
    assert _render_runtime(tmp_path, "I18nProvider", **options)["navigations"] == []
