import {
  createContext,
  createElement,
  Fragment,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { useHref, useLocation, useNavigate } from "react-router";

import {
  cookieName,
  defaultAtRoot,
  defaultLocale,
  defaultPlural,
  deployUrl,
  fallbackLocale,
  loaders,
  localizedPaths,
  locales,
  urlRouting,
} from "$/i18n/index.js";
import env from "$/env.json";

// gettext msgctxt separator; catalog keys are "context\u0004msgid".
const CONTEXT_SEPARATOR = "\u0004";

// Language subtags written right-to-left.
const RTL_LANGUAGES = new Set([
  "ar",
  "arc",
  "ckb",
  "dv",
  "fa",
  "he",
  "ks",
  "ps",
  "sd",
  "ug",
  "ur",
  "yi",
]);

// The element the app renders into: an embedded app (EmbedPlugin) owns only its
// mount target, never the host page's <html>, so it has no root while the host
// page lacks that element.
const appRoot = () =>
  env.MOUNT_TARGET
    ? document.querySelector(env.MOUNT_TARGET)
    : document.documentElement;

// Set lang/dir on the app's root for a locale. Tags are case-insensitive (RFC
// 5646).
const applyDocumentLocale = (locale) => {
  const root = appRoot();
  if (!root) {
    return;
  }
  root.lang = locale;
  const language = locale.split("-")[0].toLowerCase();
  root.dir = RTL_LANGUAGES.has(language) ? "rtl" : "ltr";
};

const stripContext = (key) => {
  const index = key.indexOf(CONTEXT_SEPARATOR);
  return index === -1 ? key : key.slice(index + 1);
};

const interpolate = (message, params) =>
  message.replace(/\{(\w+)\}/g, (match, name) =>
    params && name in params ? String(params[name]) : match,
  );

const readCookie = (name) => {
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(name + "="));
  return match ? decodeURIComponent(match.split("=")[1]) : undefined;
};

const writeCookie = (name, value) => {
  const secure = location.protocol === "https:" ? "; secure" : "";
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=31536000; samesite=lax${secure}`;
};

// The supported locale that best serves a list of requested ones: for each
// requested tag in turn, the supported locale with the same tag, else the first
// one with the same primary language ("de-AT" -> "de"). Tags compare
// case-insensitively (RFC 5646). Mirrors reflex_i18n.runtime.match_locale.
export const matchLocale = (requested, supported) => {
  const byTag = new Map();
  const byLanguage = new Map();
  for (const locale of supported) {
    const tag = locale.toLowerCase();
    byTag.set(tag, locale);
    const language = tag.split("-")[0];
    if (!byLanguage.has(language)) {
      byLanguage.set(language, locale);
    }
  }
  for (const tag of requested) {
    const lower = tag.toLowerCase();
    const match = byTag.get(lower) ?? byLanguage.get(lower.split("-")[0]);
    if (match !== undefined) {
      return match;
    }
  }
  return undefined;
};

// The locales to try, in order, for content wanted in a locale (the default
// locale if none), each followed by its own language. Mirrors
// reflex_i18n.runtime.fallback_chain.
export const fallbackChain = (locale) => {
  const chain = new Map();
  for (const candidate of [
    locale || defaultLocale,
    defaultLocale,
    fallbackLocale,
    ...locales,
  ]) {
    for (const tag of [candidate, candidate.split("-")[0]]) {
      if (!chain.has(tag.toLowerCase())) {
        chain.set(tag.toLowerCase(), tag);
      }
    }
  }
  return [...chain.values()];
};

// The locale whose text to show from a {locale: text} mapping, "" if it has
// no text. Mirrors reflex_i18n.runtime.pick_translation_locale.
export const pickTranslationLocale = (translations, locale) => {
  const available = Object.keys(translations ?? {}).filter(
    (key) => String(translations[key] ?? "").trim() !== "",
  );
  return matchLocale(fallbackChain(locale), available) ?? available[0] ?? "";
};

const initialLocale = () => {
  const fromCookie = readCookie(cookieName);
  if (fromCookie && locales.includes(fromCookie)) {
    return fromCookie;
  }
  return (
    matchLocale(navigator.languages ?? [navigator.language], locales) ??
    fallbackLocale
  );
};

// Cookie mode renders the default locale first; for a visitor in another
// locale the app stays hidden until that locale's catalog has rendered, so
// the client-rendered source text never flashes. The timeout shows the app
// anyway should the catalog never arrive.
const HOLD_TIMEOUT_MS = 3000;
let holdTimer;
let heldRoot;

const releaseDocument = () => {
  clearTimeout(holdTimer);
  heldRoot?.style.removeProperty("visibility");
  heldRoot = undefined;
};

const holdDocument = () => {
  heldRoot = appRoot();
  if (!heldRoot) {
    return;
  }
  heldRoot.style.visibility = "hidden";
  clearTimeout(holdTimer);
  holdTimer = setTimeout(releaseDocument, HOLD_TIMEOUT_MS);
};

export const I18nContext = createContext({
  locale: defaultLocale,
  catalog: undefined,
  setLocale: () => {},
});

// The mounted provider's setter, so a Reflex event (run_script) can switch
// the locale without threading context through the calling component.
let _switchLocale = null;

export function switchLocale(locale, options) {
  if (_switchLocale) {
    _switchLocale(locale, options);
  }
}

// Publish a setter as the one `switchLocale` (a Reflex event) drives, without
// clobbering another provider's on unmount.
const usePublishedSetter = (setLocale) => {
  useEffect(() => {
    _switchLocale = setLocale;
    return () => {
      if (_switchLocale === setLocale) {
        _switchLocale = null;
      }
    };
  }, [setLocale]);
};

// Switch locale by navigating to the current page's address in the target
// locale, keeping the query string and fragment.
const useLocaleNavigate = () => {
  const { pathname, search, hash } = useLocation();
  const navigate = useNavigate();
  return useCallback(
    (nextLocale, options) =>
      navigate(
        localizePath(delocalizePath(pathname), nextLocale) + search + hash,
        options,
      ),
    [pathname, search, hash, navigate],
  );
};

export function I18nProvider({ children, onLocaleChange, serverLocale }) {
  const { pathname } = useLocation();
  const navigateLocale = useLocaleNavigate();
  // The compiled event binding (cookie mode only) may change identity between
  // renders; reading it through a ref keeps setLocale stable.
  const onLocaleChangeRef = useRef(onLocaleChange);
  onLocaleChangeRef.current = onLocaleChange;
  // Cookie mode starts from the default locale so the server/first render is
  // deterministic and never touches document/navigator; the cookie- and
  // browser-based locale is resolved client-side in the layout effect below.
  const [cookieLocale, setCookieLocale] = useState(defaultLocale);
  // With URL routing the path is authoritative (mirroring the server), so
  // the cookie and browser preferences never override what the URL names.
  const locale = urlRouting
    ? (pathLocale(pathname) ?? defaultLocale)
    : cookieLocale;
  // The catalog together with the locale it was loaded for.
  const [loaded, setLoaded] = useState({
    locale: undefined,
    catalog: undefined,
  });
  const holdingRef = useRef(false);

  // A layout effect runs before the first paint, so the document is hidden
  // before the default-locale render could show.
  useLayoutEffect(() => {
    if (urlRouting) {
      return;
    }
    const initial = initialLocale();
    if (initial !== defaultLocale) {
      holdingRef.current = true;
      holdDocument();
    }
    setCookieLocale(initial);
    return () => {
      if (holdingRef.current) {
        holdingRef.current = false;
        releaseDocument();
      }
    };
  }, []);

  // Once hydrated, the server's locale wins: it is the one server-side
  // translations use, and it follows a locale a backend handler chose (e.g. the
  // one saved in a user's profile).
  useEffect(() => {
    if (!urlRouting && serverLocale && locales.includes(serverLocale)) {
      setCookieLocale(serverLocale);
    }
  }, [serverLocale]);

  useEffect(() => {
    let cancelled = false;
    loaders[locale]()
      .then((module_) => {
        if (!cancelled) {
          setLoaded({ locale, catalog: module_ });
        }
      })
      .catch((error) => {
        // A failed chunk load (e.g. a stale hashed chunk after a redeploy)
        // falls back to the source msgids rather than keeping the previous
        // locale's catalog. Surface it instead of an unhandled rejection.
        if (!cancelled) {
          setLoaded({ locale, catalog: undefined });
        }
        console.error(
          `Failed to load i18n catalog for locale "${locale}".`,
          error,
        );
      });
    return () => {
      cancelled = true;
    };
  }, [locale]);

  // A switch takes effect once the new locale's catalog has loaded, so text,
  // formatting and <html lang> change together: neither the source text nor a
  // mix of two languages shows while the catalog downloads.
  const shownLocale = loaded.locale ?? locale;

  useEffect(() => {
    // With URL routing the routing wrap (on every page) owns <html lang>/dir.
    if (!urlRouting) {
      applyDocumentLocale(shownLocale);
    }
  }, [shownLocale]);

  // Runs once the held locale's catalog is committed, so the revealed
  // document already shows the translated text.
  useEffect(() => {
    if (holdingRef.current && loaded.locale === locale) {
      holdingRef.current = false;
      releaseDocument();
    }
  }, [loaded, locale]);

  const setLocale = useCallback(
    (nextLocale, { notifyServer = true } = {}) => {
      if (!locales.includes(nextLocale)) {
        console.error(
          `Invalid locale "${nextLocale}". Supported locales: ${locales.join(", ")}.`,
        );
        return;
      }
      if (urlRouting) {
        // The URL owns the locale in this mode: switch by navigating to the
        // localized address (the cookie is not consulted).
        navigateLocale(nextLocale);
        return;
      }
      // The cookie is the source of truth for a chosen locale; only an
      // explicit choice writes it, so browser-preference changes keep
      // applying for users who never picked a language.
      writeCookie(cookieName, nextLocale);
      setCookieLocale(nextLocale);
      // Keep the server's locale (server-side translations) in step. A caller
      // that already sends I18nState.set_locale itself opts out.
      if (notifyServer) {
        onLocaleChangeRef.current?.(nextLocale);
      }
    },
    [navigateLocale],
  );

  usePublishedSetter(setLocale);

  return createElement(
    I18nContext.Provider,
    { value: { locale: shownLocale, catalog: loaded.catalog, setLocale } },
    children,
  );
}

// Cached Intl formatter instances, keyed by locale + serialized options, so a
// list of many formatted values reuses one formatter per (locale, options).
const _numberFormatters = new Map();
const _dateFormatters = new Map();
const _languageNames = new Map();

// In normal use the key set is small (locales x compile-time option sets), but
// runtime-varying options (a Var in `options=`) could grow it, so cap the cache
// and evict the oldest entry (Map preserves insertion order).
const FORMATTER_CACHE_LIMIT = 100;

const getFormatter = (cache, Ctor, locale, options) => {
  const key = locale + " " + JSON.stringify(options ?? {});
  let formatter = cache.get(key);
  if (formatter === undefined) {
    formatter = new Ctor(locale, options);
    if (cache.size >= FORMATTER_CACHE_LIMIT) {
      cache.delete(cache.keys().next().value);
    }
    cache.set(key, formatter);
  }
  return formatter;
};

// Turn a value into a Date, normalizing Python's str(date/datetime/time):
// trim microseconds to milliseconds; parse a date-only value as local midnight
// (not UTC, which would shift the day in negative offsets); anchor a bare time
// to the epoch date so Intl can format it (new Date("14:30:00") is invalid).
const toDate = (value) => {
  if (value instanceof Date) return value;
  if (typeof value === "number") return new Date(value);
  const s = String(value).replace(/(\.\d{3})\d+/, "$1");
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return new Date(`${s}T00:00:00`);
  if (/^\d{2}:\d{2}/.test(s)) return new Date(`1970-01-01T${s}`);
  return new Date(s.replace(" ", "T"));
};

const LANGUAGE_NAMES = { type: "language", languageDisplay: "standard" };

// A language's name in another language ("Portugiesisch (Brasilien)"), or the
// tag itself for one Intl cannot name.
const languageName = (tag, inLocale) => {
  try {
    return (
      getFormatter(
        _languageNames,
        Intl.DisplayNames,
        inLocale,
        LANGUAGE_NAMES,
      ).of(tag) ?? tag
    );
  } catch {
    return tag;
  }
};

export function useFormat() {
  const { locale } = useContext(I18nContext);
  // A missing value (or a date that does not parse) formats as empty text,
  // rather than as 0 or a thrown RangeError.
  const formatNumber = useCallback(
    (value, options) =>
      value == null
        ? ""
        : getFormatter(
            _numberFormatters,
            Intl.NumberFormat,
            locale,
            options,
          ).format(value),
    [locale],
  );
  const formatDate = useCallback(
    (value, options) => {
      const date = value == null ? undefined : toDate(value);
      return date === undefined || Number.isNaN(date.getTime())
        ? ""
        : getFormatter(
            _dateFormatters,
            Intl.DateTimeFormat,
            locale,
            options,
          ).format(date);
    },
    [locale],
  );
  const formatLanguage = useCallback(
    (tag) => languageName(tag, locale),
    [locale],
  );
  return [formatNumber, formatDate, formatLanguage];
}

export function useLocale() {
  return useContext(I18nContext).locale;
}

// [pick, pickLocale] for {locale: text} mappings, defaulting to the active
// locale (for a missing or empty one, as on the server); both return "" when
// the mapping has no text.
export function usePick() {
  const { locale: active } = useContext(I18nContext);
  const pickLocale = useCallback(
    (translations, locale) =>
      pickTranslationLocale(translations, locale || active),
    [active],
  );
  const pick = useCallback(
    (translations, locale) => {
      const key = pickLocale(translations, locale);
      return key === "" ? "" : translations[key];
    },
    [pickLocale],
  );
  return [pick, pickLocale];
}

export function useTranslation() {
  const { catalog } = useContext(I18nContext);

  const t_ = useCallback(
    (key, params) => {
      const message = catalog?.messages.get(key) ?? stripContext(key);
      return interpolate(message, params);
    },
    [catalog],
  );

  const tp_ = useCallback(
    (key, pluralMessage, count, params) => {
      const entry = catalog?.messages.get(key);
      // Uncataloged messages fall back to the two source strings, picked by
      // the DEFAULT locale's plural rule (they are written in that language).
      const message = Array.isArray(entry)
        ? (entry[catalog.plural(count)] ?? entry[entry.length - 1])
        : defaultPlural(count) === 0
          ? stripContext(key)
          : pluralMessage;
      return interpolate(message, params);
    },
    [catalog],
  );

  return [t_, tp_];
}

// URL-based locale routing, opt-in via I18nPlugin(routing=...).

// The URL-routing locale setter: validate, then navigate to the current page in
// that locale. Independent of the I18nProvider, which an app that uses neither
// rx.t nor a formatting var never pulls in.
const useUrlLocaleSetter = (navigateLocale) =>
  useCallback(
    (nextLocale) => {
      if (!locales.includes(nextLocale)) {
        console.error(
          `Invalid locale "${nextLocale}". Supported locales: ${locales.join(", ")}.`,
        );
        return;
      }
      navigateLocale(nextLocale);
    },
    [navigateLocale],
  );

// Provide a fixed locale + statically-imported catalog to a route's subtree.
// The catalog is a static import (bundled with the route chunk), so the right
// language is present synchronously during prerender.
export function LocaleRoute({ locale, catalog, children }) {
  const setLocale = useUrlLocaleSetter(useLocaleNavigate());
  return createElement(
    I18nContext.Provider,
    { value: { locale, catalog, setLocale } },
    children,
  );
}

// Path-prefix helpers (mirror reflex_i18n.routing.PathPrefixRouting).

// The configured locale a path segment names, matched case-insensitively as
// React Router matches paths, in the configured spelling.
const localesBySegment = new Map(
  locales.map((locale) => [locale.toLowerCase(), locale]),
);
const segmentLocale = (segment) => localesBySegment.get(segment.toLowerCase());

const pathLocale = (pathname) =>
  segmentLocale(pathname.replace(/^\/+/, "").split("/")[0]);

// One leading slash ("//host" is a protocol-relative URL off the site) and no
// trailing one: a nested page is prerendered at "/a/b/" but addressed as "/a/b".
const sitePath = (path) => "/" + path.replace(/^\/+|\/+$/g, "");

// Translated page paths, keyed case-insensitively as React Router matches
// paths: each base path's paths by locale, and a path's base path by locale.
const pathsByBase = new Map();
const basePaths = new Map(locales.map((locale) => [locale, new Map()]));
for (const [base, paths] of Object.entries(localizedPaths)) {
  pathsByBase.set(base.toLowerCase(), paths);
  for (const [locale, path] of Object.entries(paths)) {
    basePaths.get(locale).set(path.toLowerCase(), base);
  }
}

const delocalizePath = (pathname) => {
  const [head, ...rest] = pathname.replace(/^\/+/, "").split("/");
  const locale = segmentLocale(head);
  if (locale === undefined) {
    return sitePath(pathname);
  }
  const path = sitePath(rest.join("/"));
  return basePaths.get(locale).get(path.toLowerCase()) ?? path;
};

const localizePath = (base, locale) => {
  const path = pathsByBase.get(base.toLowerCase())?.[locale] ?? base;
  if (locale === defaultLocale && defaultAtRoot) {
    return path;
  }
  return path === "/" ? "/" + locale : "/" + locale + path;
};

const absoluteUrl = (path) => {
  const base = (deployUrl || "").replace(/\/$/, "");
  return base ? base + path : path;
};

// React Router paths (useLocation, navigate) are relative to the router
// basename (Reflex's `frontend_path`); raw <a>/<link> hrefs are not, so they
// need the basename prepended. useHref("/") is the basename with a trailing "/".
const useBasename = () => useHref("/").replace(/\/$/, "");

// Emit reciprocal <link rel="alternate" hreflang> + canonical for the current
// route. Rendered as an app-wrap so it applies to every page; React hoists the
// links into <head> and they prerender into the static HTML.
export function HreflangLinks({ children }) {
  const { pathname } = useLocation();
  const basename = useBasename();
  const navigateLocale = useLocaleNavigate();
  // This wrap is on every page with URL routing, unlike the provider and
  // LocaleRoute (absent from the default locale's unprefixed pages), so it
  // publishes the setter rx.i18n.set_locale drives and keeps <html lang>/dir
  // in step with the URL, including on the way back to an unprefixed page.
  usePublishedSetter(useUrlLocaleSetter(navigateLocale));
  useEffect(
    () => applyDocumentLocale(pathLocale(pathname) ?? defaultLocale),
    [pathname],
  );
  // When every locale is prefixed (defaultAtRoot off), an unprefixed URL has
  // no locale of its own; send it to its default-locale address.
  useEffect(() => {
    if (!defaultAtRoot && pathLocale(pathname) === undefined) {
      navigateLocale(defaultLocale, { replace: true });
    }
  }, [pathname, navigateLocale]);
  const base = delocalizePath(pathname);
  const href = (locale) => absoluteUrl(basename + localizePath(base, locale));
  const links = locales.map((locale) =>
    createElement("link", {
      key: locale,
      rel: "alternate",
      hrefLang: locale,
      href: href(locale),
    }),
  );
  links.push(
    createElement("link", {
      key: "x-default",
      rel: "alternate",
      hrefLang: "x-default",
      href: href(defaultLocale),
    }),
    createElement("link", {
      key: "canonical",
      rel: "canonical",
      // The localized URL for the page's own locale: identical to pathname
      // except for an unprefixed page when every locale is prefixed, whose
      // canonical is its default-locale address.
      href: href(pathLocale(pathname) ?? defaultLocale),
    }),
  );
  // This is an app-wrap: render the links AND pass the app content through.
  return createElement(Fragment, null, ...links, children);
}

// The current page's address in each locale. With URL routing these are the
// page's real per-locale URLs; without it there is only one URL per page, and
// the locale is switched through the provider (and cookie) instead.
export function useAlternateUrls() {
  const { pathname, search, hash } = useLocation();
  const basename = useBasename();
  const base = delocalizePath(pathname);
  // Keep the query string and fragment: switching language must not drop the
  // filters or the anchor the visitor is on. The clean canonical URL for each
  // locale is emitted by HreflangLinks, so crawlers still see one per page.
  const rest = search + hash;
  return Object.fromEntries(
    locales.map((locale) => [
      locale,
      basename +
        (urlRouting ? localizePath(base, locale) : sitePath(pathname)) +
        rest,
    ]),
  );
}

// A language switcher: one <a> per locale, labelled with the language's own
// name. With URL routing these are real links to the current page in each
// locale, so crawlers follow them and the URL stays the source of truth.
export function LanguageSwitcher(props) {
  const urls = useAlternateUrls();
  const { locale: active, setLocale } = useContext(I18nContext);
  return createElement(
    "nav",
    props,
    ...locales.map((locale) =>
      createElement(
        "a",
        {
          key: locale,
          href: urls[locale],
          hrefLang: locale,
          // Each language is named in itself, so a visitor finds their own
          // whatever the page's language is.
          lang: locale,
          "aria-current": locale === active ? "true" : undefined,
          onClick: urlRouting
            ? undefined
            : (event) => {
                event.preventDefault();
                setLocale(locale);
              },
        },
        languageName(locale, locale),
      ),
    ),
  );
}
