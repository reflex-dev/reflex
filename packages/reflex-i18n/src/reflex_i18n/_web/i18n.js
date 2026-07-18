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
