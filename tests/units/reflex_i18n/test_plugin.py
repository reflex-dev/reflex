"""Tests for the I18nPlugin: config activation and catalog emission."""

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from reflex_base.config import get_config
from reflex_i18n import I18nPlugin, PathPrefixRouting, t
from reflex_i18n.config import I18nConfig, set_active_i18n_config
from reflex_i18n.format import _SOURCE_FMT_DATE, _SOURCE_FMT_NUMBER
from reflex_i18n.plugin import _RTL_LANGUAGES, _RUNTIME_SOURCE, _set_document_locale
from reflex_i18n.registry import clear_messages
from reflex_i18n.runtime import (
    WeekdayLength,
    fallback_chain,
    format_language,
    format_weekday,
    pick_translation_locale,
    use_locale,
)
from reflex_i18n.state import _resolve_locale
from reflex_i18n.vars import _SOURCE_PICK_LOCALE

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node missing")

# Stand-ins for the modules the client runtime imports. Effects run during the
# render call; state setters and navigations are recorded for the driver. A
# rendered context provider supplies its value to components rendered after it.
_RUNTIME_STUBS = {
    "react": """
export const createContext = (value) => {
  const context = { value };
  context.Provider = { context };
  return context;
};
export const createElement = (type, props, ...children) => {
  if (type?.context) {
    type.context.value = props.value;
  }
  return { type, props, children };
};
export const Fragment = "Fragment";
export const useCallback = (fn) => fn;
export const useContext = (context) => context.value;
export const useEffect = (effect) => {
  effect();
};
export const useLayoutEffect = (effect) => {
  effect();
};
export const useRef = (current) => ({ current });
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

# Renders one runtime component with browser globals from argv, runs the
# optional action script against the module and the rendered element, and
# prints the navigations, state updates and onLocaleChange calls they made, the
# attributes and visibility set on <html> and on the embed mount element, and
# the action's return value.
_RUNTIME_DRIVER = """
import { pathToFileURL } from "node:url";
const [modulePath, component, env, action] = process.argv.slice(2);
const { pathname, languages, props, mountTarget } = JSON.parse(env);
globalThis.navigations = [];
globalThis.stateUpdates = [];
const localeChanges = [];
globalThis.routerLocation = { pathname, search: "", hash: "" };
Object.defineProperty(globalThis, "navigator", {
  value: { languages, language: languages[0] },
  configurable: true,
});
// The style is not enumerable, so the recorded attributes leave it out.
const element = () =>
  Object.defineProperty({}, "style", {
    value: {
      removeProperty(name) {
        delete this[name];
      },
    },
  });
const mountElement = element();
globalThis.document = {
  cookie: "",
  documentElement: element(),
  querySelector: (selector) => (selector === mountTarget ? mountElement : null),
};
// A pending timer would keep node running after the driver is done.
const setTimer = globalThis.setTimeout;
globalThis.setTimeout = (...args) => setTimer(...args).unref();
globalThis.location = { protocol: "http:" };
const mod = await import(pathToFileURL(modulePath).href);
const rendered = mod[component]({
  children: null,
  onLocaleChange: (locale) => localeChanges.push(locale),
  ...props,
});
const result = new Function("mod", "rendered", action)(mod, rendered);
const { documentElement } = globalThis.document;
process.stdout.write(
  JSON.stringify({
    navigations,
    stateUpdates,
    localeChanges,
    documentElement,
    visibility: documentElement.style.visibility ?? "",
    mountElement,
    mountVisibility: mountElement.style.visibility ?? "",
    result,
  }),
);
"""


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The warnings logged so far.

    Args:
        caplog: The log capture.

    Returns:
        Their messages.
    """
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def _render_runtime(
    tmp_path: Path,
    component: str,
    *,
    locales: list[str],
    default_locale: str,
    fallback_locale: str | None = None,
    url_routing: bool = False,
    default_at_root: bool = True,
    localized_paths: dict[str, dict[str, str]] | None = None,
    pathname: str = "/",
    languages: tuple[str, ...] = ("en",),
    props: dict[str, Any] | None = None,
    mount_target: str | None = None,
    mount_present: bool = True,
    action: str = "",
) -> dict[str, Any]:
    """Render a component of the shipped client runtime against stub modules.

    Args:
        tmp_path: Directory for the runtime, its stubs and the driver.
        component: The exported component to render.
        locales: The configured locales.
        default_locale: The configured default locale.
        fallback_locale: The configured fallback locale (default: the default
            locale).
        url_routing: Whether locales are routed through the URL.
        default_at_root: Whether the default locale is served unprefixed.
        localized_paths: The translated paths of pages, base path ->
            {locale: path}.
        pathname: The router location's path.
        languages: The browser's preferred languages.
        props: Extra props for the component.
        mount_target: The embed mount target selector (EmbedPlugin), if any.
        mount_present: Whether the page has an element matching the mount
            target.
        action: JS run after the render with the runtime module as ``mod``
            and the rendered element as ``rendered``.

    Returns:
        The recorded ``navigations``, ``stateUpdates``, ``localeChanges``,
        ``documentElement`` attributes and ``visibility``, the same for the
        ``mountElement``, and the action's ``result``.
    """
    config = {
        "locales": locales,
        "defaultLocale": default_locale,
        "fallbackLocale": fallback_locale or default_locale,
        "urlRouting": url_routing,
        "defaultAtRoot": default_at_root,
        "localizedPaths": localized_paths or {},
        "cookieName": "reflex_locale",
        "deployUrl": "",
    }
    index = "".join(f"export const {k} = {json.dumps(v)};\n" for k, v in config.items())
    index += (
        "export const defaultPlural = (n) => Number(n != 1);\n"
        "export const loaders = Object.fromEntries(locales.map((locale) => "
        "[locale, async () => ({ messages: new Map() })]));\n"
    )
    stubs = {
        **_RUNTIME_STUBS,
        "$/i18n/index.js": index,
        "$/env.json": f"export default {json.dumps({'MOUNT_TARGET': mount_target})};\n",
    }
    source = _RUNTIME_SOURCE.read_text(encoding="utf-8")
    for specifier, stub_source in stubs.items():
        stub = tmp_path / (specifier.replace("/", "_").replace("$", "") + ".mjs")
        stub.write_text(stub_source)
        source = source.replace(f'from "{specifier}"', f'from "./{stub.name}"')
    module = tmp_path / "i18n.mjs"
    module.write_text(source)
    driver = tmp_path / "driver.mjs"
    driver.write_text(_RUNTIME_DRIVER)
    env = json.dumps({
        "pathname": pathname,
        "languages": list(languages),
        "props": props or {},
        "mountTarget": mount_target if mount_present else None,
    })
    result = subprocess.run(
        ["node", str(driver), str(module), component, env, action],
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
    """Write a .po file with a two-form plural header.

    Args:
        catalog_dir: The catalog directory, created if missing.
        locale: The file's locale.
        body: The messages after the header.
    """
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


def test_plugin_ships_client_runtime():
    plugin = I18nPlugin(locales=["en"])
    assert dict(plugin.get_static_assets()) == {
        Path("utils/i18n.js"): _RUNTIME_SOURCE.read_text(encoding="utf-8")
    }


def test_plugin_emits_index_and_locale_modules(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_po(tmp_path / "locales", "de", 'msgid "Hello"\nmsgstr "Hallo"\n')

    plugin = I18nPlugin(locales=["en", "de"], default_locale="en")
    t("Hello")

    # The default (source) locale needs no translation entry.
    assert dict(plugin._compile_catalogs()) == {
        "i18n/index.js": (
            "// Generated by Reflex. Do not edit.\n"
            'export const locales = ["en", "de"];\n'
            'export const defaultLocale = "en";\n'
            'export const fallbackLocale = "en";\n'
            'export const cookieName = "reflex_locale";\n'
            "export const urlRouting = false;\n"
            "export const defaultAtRoot = true;\n"
            'export const deployUrl = "";\n'
            "export const defaultPlural = (n) => Number((n != 1));\n"
            "export const localizedPaths = {};\n"
            "export const loaders = {\n"
            '  "en": () => import("$/i18n/en.js"),\n'
            '  "de": () => import("$/i18n/de.js"),\n'
            "};\n"
        ),
        "i18n/en.js": (
            "// Generated by Reflex. Do not edit.\n"
            "export const plural = (n) => Number(n != 1);\n"
            "export const messages = new Map([\n\n]);\n"
        ),
        "i18n/de.js": (
            "// Generated by Reflex. Do not edit.\n"
            "export const plural = (n) => Number((n != 1));\n"
            "export const messages = new Map([\n"
            '  ["Hello", "Hallo"],\n'
            "]);\n"
        ),
    }


def test_pre_compile_warns_about_messages_built_before_the_plugin(
    tmp_path: Path, monkeypatch, caplog: pytest.LogCaptureFixture
):
    monkeypatch.chdir(tmp_path)
    # e.g. a module rxconfig.py imports before it constructs the plugin.
    t("Too early")
    plugin = I18nPlugin(locales=["en", "de"], default_locale="en")
    t("In time")
    save_tasks: list[Any] = []

    plugin.pre_compile(add_save_task=save_tasks.append)  # pyright: ignore[reportCallIssue]

    assert save_tasks == [plugin._compile_catalogs]
    assert _warnings(caplog) == [
        (
            "1 rx.t message(s) were built before I18nPlugin was configured and "
            "always render their source text:\n"
            "  'Too early'\n"
            "Build them inside a page or component function instead."
        )
    ]


def test_plugin_missing_catalog_file_still_emits_module(
    tmp_path: Path, monkeypatch, caplog: pytest.LogCaptureFixture
):
    monkeypatch.chdir(tmp_path)
    plugin = I18nPlugin(locales=["en", "de"], default_locale="en")
    t("Hello")

    outputs = dict(plugin._compile_catalogs())
    # de.js exists but is empty (falls back to source text at runtime).
    assert outputs["i18n/de.js"] == (
        "// Generated by Reflex. Do not edit.\n"
        "export const plural = (n) => Number(n != 1);\n"
        "export const messages = new Map([\n\n]);\n"
    )
    po_path = tmp_path.resolve() / "locales" / "de.po"
    assert _warnings(caplog) == [
        f"No translation catalog found for locale 'de' (expected {po_path}).",
        (
            "1 translation(s) missing for locale 'de' (falling back to the default "
            "locale):\n  'Hello'"
        ),
    ]


def test_plugin_emits_default_plural_in_index(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # French source locale without a catalog: the client fallback rule comes
    # from Babel's CLDR table, not the English (n != 1) default. Only the
    # source locale is configured, so no catalog is missing.
    plugin = I18nPlugin(locales=["fr"], default_locale="fr")
    outputs = dict(plugin._compile_catalogs())
    assert outputs["i18n/index.js"] == (
        "// Generated by Reflex. Do not edit.\n"
        'export const locales = ["fr"];\n'
        'export const defaultLocale = "fr";\n'
        'export const fallbackLocale = "fr";\n'
        'export const cookieName = "reflex_locale";\n'
        "export const urlRouting = false;\n"
        "export const defaultAtRoot = true;\n"
        'export const deployUrl = "";\n'
        "export const defaultPlural = (n) => Number((n > 1));\n"
        "export const localizedPaths = {};\n"
        "export const loaders = {\n"
        '  "fr": () => import("$/i18n/fr.js"),\n'
        "};\n"
    )


@requires_node
@pytest.mark.parametrize(
    ("locales", "default_locale", "fallback_locale", "languages", "expected"),
    [
        (["en-GB", "en-us"], "en-GB", None, ("en-US",), "en-us"),
        (["pt-PT", "pt-br"], "pt-PT", None, ("pt-BR",), "pt-br"),
        (["EN", "de"], "de", None, ("en-US",), "EN"),
        (["en", "de"], "en", None, ("fr-CA", "de-AT"), "de"),
        (["en", "de"], "en", None, ("fr",), "en"),
        (["de", "en"], "de", "en", ("fr",), "en"),
        (["de", "en"], "de", "en", ("fr", "de-AT"), "de"),
    ],
)
def test_client_negotiation_matches_server(
    tmp_path: Path,
    locales: list[str],
    default_locale: str,
    fallback_locale: str | None,
    languages: tuple[str, ...],
    expected: str,
):
    """Without a chosen locale, the browser picks the server's locale."""
    rendered = _render_runtime(
        tmp_path,
        "I18nProvider",
        locales=locales,
        default_locale=default_locale,
        fallback_locale=fallback_locale,
        languages=languages,
    )
    set_active_i18n_config(
        I18nConfig(locales, default_locale, fallback_locale=fallback_locale)
    )
    server = _resolve_locale("", ", ".join(languages))
    assert rendered["stateUpdates"][0] == server == expected


@requires_node
@pytest.mark.parametrize(
    ("server_locale", "url_routing", "expected"),
    [
        # Not hydrated yet: the browser's own pick stands.
        ("", False, ["en"]),
        # A locale the server resolved or a handler chose wins.
        ("de", False, ["en", "de"]),
        ("fr", False, ["en"]),
        # The URL owns the locale.
        ("de", True, []),
    ],
)
def test_provider_follows_the_server_locale(
    tmp_path: Path, server_locale: str, url_routing: bool, expected: list[str]
):
    rendered = _render_runtime(
        tmp_path,
        "I18nProvider",
        locales=["en", "de"],
        default_locale="en",
        url_routing=url_routing,
        props={"serverLocale": server_locale},
    )
    assert rendered["stateUpdates"] == expected
    assert rendered["localeChanges"] == []


@requires_node
@pytest.mark.parametrize(
    ("languages", "url_routing", "expected"),
    [
        # The first render shows the default locale, not the visitor's.
        (("de",), False, "hidden"),
        # The first render already is in the visitor's locale.
        (("en",), False, ""),
        # The URL's locale is rendered from the start.
        (("de",), True, ""),
    ],
)
def test_provider_hides_the_page_until_the_visitors_locale_rendered(
    tmp_path: Path, languages: tuple[str, ...], url_routing: bool, expected: str
):
    rendered = _render_runtime(
        tmp_path,
        "I18nProvider",
        locales=["en", "de"],
        default_locale="en",
        url_routing=url_routing,
        languages=languages,
    )
    assert rendered["visibility"] == expected


@requires_node
def test_embedded_provider_leaves_the_host_page_alone(tmp_path: Path):
    """An embedded app hides and localizes its mount element, not the host's <html>."""
    rendered = _render_runtime(
        tmp_path,
        "I18nProvider",
        locales=["en", "de"],
        default_locale="en",
        languages=("de",),
        mount_target="#widget",
    )
    assert rendered["documentElement"] == {}
    assert rendered["visibility"] == ""
    assert rendered["mountElement"] == {"lang": "en", "dir": "ltr"}
    assert rendered["mountVisibility"] == "hidden"


@requires_node
def test_embedded_provider_without_its_mount_element_leaves_the_host_page_alone(
    tmp_path: Path,
):
    """An embedded app whose mount element is gone changes nothing on the host page."""
    rendered = _render_runtime(
        tmp_path,
        "I18nProvider",
        locales=["en", "de"],
        default_locale="en",
        languages=("de",),
        mount_target="#widget",
        mount_present=False,
    )
    assert rendered["documentElement"] == {}
    assert rendered["visibility"] == ""


_PICK_CASES = [
    ({"de": "Hallo", "en": "Hello"}, "en"),
    ({"de": "Hallo", "en": "Hello"}, "fr"),
    ({"en": "Hello", "fr": "Bonjour"}, "it"),
    ({"de-CH": "Grüezi", "en": "Hello"}, "de-AT"),
    ({"de": "  ", "en": "Hello"}, "de"),
    ({"it": "Ciao"}, "de"),
    ({"DE": "Hallo", "en": "Hello"}, "de"),
    ({"en-GB": "Colour", "de": "Farbe"}, "en"),
    ({}, "de"),
]


@requires_node
def test_client_picks_translations_like_the_server(tmp_path: Path):
    """The runtime and the plugin-less inline picker match pick_translation_locale."""
    rendered = _render_runtime(
        tmp_path,
        "I18nProvider",
        locales=["de", "en", "fr"],
        default_locale="de",
        fallback_locale="en",
        action=(
            f"const cases = {json.dumps(_PICK_CASES)};"
            f"const inline = {_SOURCE_PICK_LOCALE!s};"
            "return {"
            "runtime: cases.map(([t, l]) => mod.pickTranslationLocale(t, l)),"
            "inline: cases.map(([t, l]) => inline(t, l)),"
            "chains: cases.map(([, l]) => mod.fallbackChain(l)),"
            "unset: [mod.pickTranslationLocale(cases[0][0]), inline(cases[0][0], '')]};"
        ),
    )
    set_active_i18n_config(I18nConfig(["de", "en", "fr"], "de", fallback_locale="en"))
    configured = [pick_translation_locale(t, wanted) or "" for t, wanted in _PICK_CASES]
    chains = [list(fallback_chain(wanted)) for _, wanted in _PICK_CASES]
    configured_unset = pick_translation_locale(_PICK_CASES[0][0])
    set_active_i18n_config(None)
    unconfigured = [
        pick_translation_locale(t, wanted) or "" for t, wanted in _PICK_CASES
    ]
    unconfigured_unset = pick_translation_locale(_PICK_CASES[0][0], "")
    assert rendered["result"] == {
        "runtime": configured,
        "inline": unconfigured,
        "chains": chains,
        # A missing or empty locale means the default one in the browser, as
        # outside an event on the server.
        "unset": [configured_unset, unconfigured_unset],
    }
    assert configured == ["en", "de", "en", "de-CH", "en", "it", "DE", "en-GB", ""]


@requires_node
@pytest.mark.parametrize("locale", ["de", "en"])
def test_client_names_languages_and_weekdays_like_the_server(
    tmp_path: Path, locale: str
):
    """Intl in the browser and Babel on the server agree on these names."""
    tags = ["en", "de", "fr", "it", "nl", "pt-BR", "zh-Hant", "lt"]
    lengths: list[WeekdayLength] = ["long", "short", "narrow"]
    rendered = _render_runtime(
        tmp_path,
        "I18nProvider",
        locales=[locale],
        default_locale=locale,
        action=(
            "const [fmtNumber, fmtDate, fmtLanguage] = mod.useFormat();"
            f"const tags = {json.dumps(tags)};"
            f"const lengths = {json.dumps(lengths)};"
            "return {"
            "languages: tags.map((tag) => fmtLanguage(tag)),"
            "weekdays: lengths.map((weekday) => [0, 1, 2, 3, 4, 5, 6].map("
            "(day) => fmtDate(new Date(2024, 0, 1 + day), { weekday })))};"
        ),
    )
    with use_locale(locale):
        server = {
            "languages": [format_language(tag) for tag in tags],
            "weekdays": [
                [format_weekday(day, length=length) for day in range(7)]
                for length in lengths
            ],
        }
    assert rendered["result"] == server


@requires_node
def test_source_formatters_match_the_runtime(tmp_path: Path):
    """Without the plugin, values format as the runtime formats them in ``en``."""
    # A missing value or a date that does not parse formats as empty text.
    numbers = [[1234.5, {}], [0.19, {"style": "percent"}], [None, {}]]
    dates = [
        None,
        "not a date",
        0,
        "2026-07-18",
        "2026-07-18 14:30:00.123456",
        "2026-07-18T14:30:00+02:00",
        "14:30:00",
    ]
    date_options = {"timeZone": "UTC", "dateStyle": "medium", "timeStyle": "long"}
    rendered = _render_runtime(
        tmp_path,
        "I18nProvider",
        locales=["en"],
        default_locale="en",
        action=(
            "const [fmtNumber, fmtDate] = mod.useFormat();"
            f"const sourceNumber = {_SOURCE_FMT_NUMBER!s};"
            f"const sourceDate = {_SOURCE_FMT_DATE!s};"
            f"const numbers = {json.dumps(numbers)};"
            f"const dates = {json.dumps(dates)};"
            f"const dateOptions = {json.dumps(date_options)};"
            "const format = (number, date) => ["
            "...numbers.map(([value, options]) => number(value, options)),"
            "...dates.map((value) => date(value, dateOptions))];"
            "return {"
            "runtime: format(fmtNumber, fmtDate),"
            "source: format(sourceNumber, sourceDate)};"
        ),
    )
    runtime = rendered["result"]["runtime"]
    assert len(runtime) == len(numbers) + len(dates)
    assert [runtime[2], runtime[3], runtime[4]] == ["", "", ""]
    assert rendered["result"]["source"] == runtime


@requires_node
@pytest.mark.parametrize(
    ("pathname", "expected"),
    [
        ("/pricing", {"lang": "en", "dir": "ltr"}),
        ("/ar/pricing", {"lang": "ar", "dir": "rtl"}),
        ("/AR/pricing", {"lang": "ar", "dir": "rtl"}),
    ],
)
def test_routing_wrap_sets_the_document_locale_of_every_page(
    tmp_path: Path, pathname: str, expected: dict[str, str]
):
    """Leaving a right-to-left page for an unprefixed one restores ltr.

    The routing wrap is the one piece on every routed page: ``LocaleRoute`` and
    the provider are absent from unprefixed default-locale pages of an app
    translating only server-side.
    """
    rendered = _render_runtime(
        tmp_path,
        "HreflangLinks",
        locales=["en", "ar"],
        default_locale="en",
        url_routing=True,
        pathname=pathname,
    )
    assert rendered["documentElement"] == expected


@requires_node
@pytest.mark.parametrize(
    ("locale", "direction"), [("AR", "rtl"), ("Ar-EG", "rtl"), ("EN", "ltr")]
)
def test_provider_sets_direction_case_insensitively(
    tmp_path: Path, locale: str, direction: str
):
    """Configured tags are case-insensitive, so the RTL check is too."""
    rendered = _render_runtime(
        tmp_path, "I18nProvider", locales=[locale], default_locale=locale
    )
    assert rendered["documentElement"] == {"lang": locale, "dir": direction}


@requires_node
@pytest.mark.parametrize(
    ("default_at_root", "pathname", "expected"),
    [
        (False, "/pricing", [["/en/pricing", {"replace": True}]]),
        (False, "/de/pricing", []),
        (False, "//de/pricing", []),
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


@requires_node
@pytest.mark.parametrize(
    ("pathname", "locale", "expected"),
    [
        ("/pricing", "de", [["/de/pricing", None]]),
        ("/de/pricing", "en", [["/pricing", None]]),
        ("/pricing", "fr", []),
        ("/de//evil.example", "en", [["/evil.example", None]]),
        ("/DE/pricing", "en", [["/pricing", None]]),
        ("/DE/pricing", "de", [["/de/pricing", None]]),
    ],
)
def test_routing_wrap_drives_switch_locale(
    tmp_path: Path, pathname: str, locale: str, expected: list
):
    """``rx.i18n.set_locale`` navigates through the routing wrap alone.

    Regression: without client translation neither the provider nor
    ``LocaleRoute`` (absent from unprefixed default-locale pages) is mounted,
    so the switch did nothing.
    """
    rendered = _render_runtime(
        tmp_path,
        "HreflangLinks",
        locales=["en", "de"],
        default_locale="en",
        url_routing=True,
        pathname=pathname,
        action=f"mod.switchLocale({locale!r}, {{ notifyServer: false }})",
    )
    assert rendered["navigations"] == expected


@requires_node
def test_language_switcher_names_each_language_in_itself(tmp_path: Path):
    rendered = _render_runtime(
        tmp_path,
        "LanguageSwitcher",
        locales=["en", "de", "fr", "pt-BR"],
        default_locale="en",
        action=(
            "return rendered.children.map("
            "(link) => [link.props.lang, link.children[0]]);"
        ),
    )
    assert rendered["result"] == [
        ["en", "English"],
        ["de", "Deutsch"],
        ["fr", "français"],
        ["pt-BR", "português (Brasil)"],
    ]


@requires_node
@pytest.mark.parametrize(
    ("url_routing", "pathname", "expected"),
    [
        (True, "/de//evil.example", ["/evil.example", "/de/evil.example"]),
        (True, "//evil.example", ["/evil.example", "/de/evil.example"]),
        (False, "//evil.example", ["/evil.example", "/evil.example"]),
    ],
)
def test_language_switcher_links_stay_on_site(
    tmp_path: Path, url_routing: bool, pathname: str, expected: list[str]
):
    """A path with an empty leading segment yields no protocol-relative link."""
    rendered = _render_runtime(
        tmp_path,
        "LanguageSwitcher",
        locales=["en", "de"],
        default_locale="en",
        url_routing=url_routing,
        pathname=pathname,
        action="return rendered.children.map((link) => link.props.href);",
    )
    assert rendered["result"] == expected


@requires_node
@pytest.mark.parametrize(
    ("pathname", "expected"),
    [
        (
            "/en/news",
            ["/neuigkeiten", "/en/news", "/neuigkeiten", "/en/news"],
        ),
        (
            "/neuigkeiten/",
            ["/neuigkeiten", "/en/news", "/neuigkeiten", "/neuigkeiten"],
        ),
        # The German path under /en has no page of its own to translate.
        (
            "/en/neuigkeiten",
            ["/neuigkeiten", "/en/news", "/neuigkeiten", "/en/news"],
        ),
    ],
)
def test_client_follows_a_pages_translated_paths(
    tmp_path: Path, pathname: str, expected: list[str]
):
    """Alternates, canonical and switcher links use each locale's own path."""
    rendered = _render_runtime(
        tmp_path,
        "HreflangLinks",
        locales=["de", "en"],
        default_locale="de",
        url_routing=True,
        localized_paths={"/neuigkeiten": {"en": "/news"}},
        pathname=pathname,
        action=(
            "return [rendered.children.slice(0, -1).map((link) => link.props.href),"
            " Object.values(mod.useAlternateUrls())];"
        ),
    )
    assert rendered["result"] == [expected, expected[:2]]
    # The server names the same alternates, e.g. in the sitemap.
    plugin = I18nPlugin(
        locales=["de", "en"], default_locale="de", routing=PathPrefixRouting()
    )
    plugin._page_paths = {"/neuigkeiten": {"en": "/news"}}
    plugin._base_paths = {("en", "/news"): "/neuigkeiten"}
    assert list(plugin._alternates(pathname).values()) == expected[:3]


@requires_node
@pytest.mark.parametrize(
    ("url_routing", "expected"),
    [
        (True, {"en": "/help/terminal", "de": "/de/help/terminal"}),
        (False, {"en": "/de/help/terminal", "de": "/de/help/terminal"}),
    ],
)
def test_alternate_urls_name_the_current_page_in_each_locale(
    tmp_path: Path, url_routing: bool, expected: dict[str, str]
):
    """The hook behind rx.i18n.alternate_url gives the switcher's link targets."""
    rendered = _render_runtime(
        tmp_path,
        "useAlternateUrls",
        locales=["en", "de"],
        default_locale="en",
        url_routing=url_routing,
        pathname="/de/help/terminal/",
        action=(
            "return [rendered, mod.LanguageSwitcher({}).children"
            ".map((link) => link.props.href)];"
        ),
    )
    assert rendered["result"] == [expected, list(expected.values())]


@requires_node
@pytest.mark.parametrize(
    ("pathname", "expected"),
    [
        ("/de/pricing", ["/pricing", "/de/pricing", "/pricing", "/de/pricing"]),
        ("/DE/pricing", ["/pricing", "/de/pricing", "/pricing", "/de/pricing"]),
        ("//de/pricing", ["/pricing", "/de/pricing", "/pricing", "/de/pricing"]),
        ("///de", ["/", "/de", "/", "/de"]),
        # Prerendering renders a nested page at its path with a trailing slash.
        (
            "/de/help/terminal/",
            [
                "/help/terminal",
                "/de/help/terminal",
                "/help/terminal",
                "/de/help/terminal",
            ],
        ),
        (
            "/help/terminal/",
            ["/help/terminal", "/de/help/terminal", "/help/terminal", "/help/terminal"],
        ),
        ("/de/", ["/", "/de", "/", "/de"]),
        (
            "/de//evil.example",
            ["/evil.example", "/de/evil.example", "/evil.example", "/de/evil.example"],
        ),
        (
            "//evil.example",
            ["/evil.example", "/de/evil.example", "/evil.example", "/evil.example"],
        ),
    ],
)
def test_hreflang_links_match_server_routing(
    tmp_path: Path, pathname: str, expected: list[str]
):
    """The client reads a path's locale and base as ``PathPrefixRouting`` does."""
    locales = ["en", "de"]
    rendered = _render_runtime(
        tmp_path,
        "HreflangLinks",
        locales=locales,
        default_locale="en",
        url_routing=True,
        pathname=pathname,
        action="return rendered.children.slice(0, -1).map((link) => link.props.href);",
    )
    routing = PathPrefixRouting()
    alternates = routing.alternates(pathname, locales, "en")
    server = [
        *alternates.values(),
        alternates["en"],
        alternates[routing.locale_of(pathname, locales, "en")],
    ]
    assert rendered["result"] == server == expected


@requires_node
@pytest.mark.parametrize(
    ("action", "url_routing", "expected"),
    [
        ("mod.I18nContext.value.setLocale('de')", False, ["de"]),
        (
            (
                "mod.LanguageSwitcher({}).children"
                ".find((link) => link.props.hrefLang === 'de')"
                ".props.onClick({ preventDefault() {} })"
            ),
            False,
            ["de"],
        ),
        # rx.i18n.set_locale sends the server event itself and opts out.
        (
            "mod.switchLocale('de', { notifyServer: false }); mod.switchLocale('en')",
            False,
            ["en"],
        ),
        # The URL owns the locale: switching navigates and reports nothing.
        ("mod.I18nContext.value.setLocale('de')", True, []),
    ],
    ids=["set_locale", "switcher_click", "switch_locale_opt_out", "url_routing"],
)
def test_provider_reports_locale_switch_to_server(
    tmp_path: Path, action: str, url_routing: bool, expected: list[str]
):
    """A cookie-mode switch through the provider calls onLocaleChange once."""
    rendered = _render_runtime(
        tmp_path,
        "I18nProvider",
        locales=["en", "de"],
        default_locale="en",
        url_routing=url_routing,
        action=action,
    )
    assert rendered["localeChanges"] == expected
    if url_routing:
        assert rendered["navigations"] == [["/de", None]]
    else:
        # The client switched as well.
        assert rendered["stateUpdates"][-1] == expected[-1]


_PRERENDERED = '<!DOCTYPE html><html lang="en"><head></head><body></body></html>'
_HTML_TAG_RE = re.compile(r"<html[^>]*>")


def _html_tag(page: Path) -> str:
    """Return the ``<html>`` opening tag of a page.

    Args:
        page: The HTML file.

    Returns:
        The tag.
    """
    match = _HTML_TAG_RE.search(page.read_text(encoding="utf-8"))
    assert match is not None
    return match[0]


@pytest.mark.parametrize("frontend_path", ["", "/app"])
def test_post_build_sets_the_document_locale_of_prerendered_locale_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, frontend_path: str
):
    """Pages under a locale prefix carry its language; unprefixed ones the app's."""
    monkeypatch.setattr(get_config(), "frontend_path", frontend_path)
    pages_dir = tmp_path / frontend_path.strip("/")
    pages = [
        "index.html",
        "pricing.html",
        "pricing/index.html",
        "__spa-fallback.html",
        "de.html",
        "de/index.html",
        "de/pricing.html",
        "de/pricing/index.html",
        "ar/pricing/index.html",
    ]
    for page in pages:
        (pages_dir / page).parent.mkdir(parents=True, exist_ok=True)
        (pages_dir / page).write_text(_PRERENDERED, encoding="utf-8")

    plugin = I18nPlugin(locales=["en", "de", "ar"], routing=PathPrefixRouting())
    plugin.post_build(static_dir=tmp_path)

    unchanged = '<html lang="en">'
    german = '<html lang="de" dir="ltr">'
    arabic = '<html lang="ar" dir="rtl">'
    assert {page: _html_tag(pages_dir / page) for page in pages} == {
        "index.html": unchanged,
        "pricing.html": unchanged,
        "pricing/index.html": unchanged,
        "__spa-fallback.html": unchanged,
        "de.html": german,
        "de/index.html": german,
        "de/pricing.html": german,
        "de/pricing/index.html": german,
        "ar/pricing/index.html": arabic,
    }


def test_post_build_prefixes_the_default_locale_without_default_at_root(
    tmp_path: Path,
):
    """Without default-at-root, the default locale has a prefix of its own."""
    page = tmp_path / "en" / "index.html"
    page.parent.mkdir()
    page.write_text(_PRERENDERED.replace('lang="en"', 'lang="de"'), encoding="utf-8")

    plugin = I18nPlugin(
        locales=["en", "de"], routing=PathPrefixRouting(default_at_root=False)
    )
    plugin.post_build(static_dir=tmp_path)

    assert page.read_text(encoding="utf-8") == _PRERENDERED.replace(
        '<html lang="en">', '<html lang="en" dir="ltr">'
    )


def test_plugin_names_the_default_locale_as_document_language():
    """Pages are prerendered in the default locale, before any catalog loads."""
    assert I18nPlugin(locales=["en", "de"], default_locale="de").get_html_lang() == "de"


def test_post_build_leaves_cookie_mode_pages_alone(tmp_path: Path):
    """Cookie mode has one URL per page, so no page has a locale of its own."""
    page = tmp_path / "de" / "index.html"
    page.parent.mkdir()
    page.write_text(_PRERENDERED, encoding="utf-8")

    I18nPlugin(locales=["en", "de"]).post_build(static_dir=tmp_path)

    assert page.read_text(encoding="utf-8") == _PRERENDERED


@pytest.mark.parametrize(
    ("document", "locale", "expected"),
    [
        (
            '<html lang="en" dir="ltr" class="dark"><body></body></html>',
            "ar-EG",
            '<html lang="ar-EG" dir="rtl" class="dark"><body></body></html>',
        ),
        (
            '<html data-lang="en"><body lang="en"></body></html>',
            "de",
            '<html data-lang="en" lang="de" dir="ltr"><body lang="en"></body></html>',
        ),
        ("<p>no document root</p>", "de", "<p>no document root</p>"),
    ],
    ids=["replaces", "adds", "no_root"],
)
def test_set_document_locale_rewrites_only_the_root_attributes(
    document: str, locale: str, expected: str
):
    """Other attributes and elements keep their values."""
    assert _set_document_locale(document, locale) == expected


def test_server_and_client_agree_on_right_to_left_languages():
    """The prerendered direction matches what the client applies on hydration."""
    match = re.search(
        r"const RTL_LANGUAGES = new Set\(\[(.*?)\]\);",
        _RUNTIME_SOURCE.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert match is not None
    assert set(re.findall(r'"([a-z]+)"', match[1])) == _RTL_LANGUAGES
