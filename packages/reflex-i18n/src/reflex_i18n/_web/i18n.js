import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import { cookieName, defaultLocale, loaders, locales } from "$/i18n/index.js";

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

// Match a requested locale list against the supported locales: exact tag
// first, then primary-language prefix (e.g. "de-AT" -> "de").
const negotiate = (requested) => {
  for (const tag of requested) {
    if (locales.includes(tag)) {
      return tag;
    }
    const language = tag.split("-")[0];
    const match = locales.find(
      (supported) => supported.split("-")[0] === language,
    );
    if (match !== undefined) {
      return match;
    }
  }
  return undefined;
};

const initialLocale = () => {
  const fromCookie = readCookie(cookieName);
  if (fromCookie && locales.includes(fromCookie)) {
    return fromCookie;
  }
  return (
    negotiate(navigator.languages ?? [navigator.language]) ?? defaultLocale
  );
};

export const I18nContext = createContext({
  locale: defaultLocale,
  catalog: undefined,
  setLocale: () => {},
});

// The mounted provider's setter, so a Reflex event (run_script) can switch
// the locale without threading context through the calling component.
let _switchLocale = null;

export function switchLocale(locale) {
  if (_switchLocale) {
    _switchLocale(locale);
  }
}

export function I18nProvider({ children }) {
  // Start from the default locale so the server/first render is
  // deterministic and never touches document/navigator; the cookie- and
  // browser-based locale is resolved client-side in the effect below.
  const [locale, setLocaleState] = useState(defaultLocale);
  const [catalog, setCatalog] = useState(undefined);

  useEffect(() => {
    setLocaleState(initialLocale());
  }, []);

  useEffect(() => {
    let cancelled = false;
    loaders[locale]()
      .then((module_) => {
        if (!cancelled) {
          setCatalog(module_);
        }
      })
      .catch((error) => {
        // A failed chunk load (e.g. a stale hashed chunk after a redeploy)
        // leaves the previous catalog in place; text falls back to the source
        // msgids. Surface it instead of an unhandled rejection.
        console.error(
          `Failed to load i18n catalog for locale "${locale}".`,
          error,
        );
      });
    const root = document.documentElement;
    root.lang = locale;
    root.dir = RTL_LANGUAGES.has(locale.split("-")[0]) ? "rtl" : "ltr";
    return () => {
      cancelled = true;
    };
  }, [locale]);

  const setLocale = useCallback((nextLocale) => {
    if (!locales.includes(nextLocale)) {
      console.error(
        `Invalid locale "${nextLocale}". Supported locales: ${locales.join(", ")}.`,
      );
      return;
    }
    // The cookie is the source of truth for a chosen locale; only an
    // explicit choice writes it, so browser-preference changes keep
    // applying for users who never picked a language.
    writeCookie(cookieName, nextLocale);
    setLocaleState(nextLocale);
  }, []);

  useEffect(() => {
    _switchLocale = setLocale;
    return () => {
      _switchLocale = null;
    };
  }, [setLocale]);

  return createElement(
    I18nContext.Provider,
    { value: { locale, catalog, setLocale } },
    children,
  );
}

// Cached Intl formatter instances, keyed by locale + serialized options, so a
// list of many formatted values reuses one formatter per (locale, options).
const _numberFormatters = new Map();
const _dateFormatters = new Map();

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

export function useFormat() {
  const { locale } = useContext(I18nContext);
  const formatNumber = useCallback(
    (value, options) =>
      getFormatter(
        _numberFormatters,
        Intl.NumberFormat,
        locale,
        options,
      ).format(value),
    [locale],
  );
  const formatDate = useCallback(
    (value, options) =>
      getFormatter(
        _dateFormatters,
        Intl.DateTimeFormat,
        locale,
        options,
      ).format(toDate(value)),
    [locale],
  );
  return [formatNumber, formatDate];
}

export function useLocale() {
  return useContext(I18nContext).locale;
}

export function useTranslation() {
  const { catalog } = useContext(I18nContext);

  const t_ = useCallback(
    (key, params) => {
      const message = catalog?.messages[key] ?? stripContext(key);
      return interpolate(message, params);
    },
    [catalog],
  );

  const tp_ = useCallback(
    (key, pluralMessage, count, params) => {
      const entry = catalog?.messages[key];
      const message = Array.isArray(entry)
        ? (entry[catalog.plural(count)] ?? entry[entry.length - 1])
        : count === 1
          ? stripContext(key)
          : pluralMessage;
      return interpolate(message, params);
    },
    [catalog],
  );

  return [t_, tp_];
}
