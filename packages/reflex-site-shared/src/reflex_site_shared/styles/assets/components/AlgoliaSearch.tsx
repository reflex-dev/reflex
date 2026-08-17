"use client";

import Alert02Icon from "@hugeicons/core-free-icons/Alert02Icon";
import ApiIcon from "@hugeicons/core-free-icons/ApiIcon";
import ArrowRight01Icon from "@hugeicons/core-free-icons/ArrowRight01Icon";
import BookOpen01Icon from "@hugeicons/core-free-icons/BookOpen01Icon";
import Cancel01Icon from "@hugeicons/core-free-icons/Cancel01Icon";
import ChartLineData01Icon from "@hugeicons/core-free-icons/ChartLineData01Icon";
import ComponentIcon from "@hugeicons/core-free-icons/ComponentIcon";
import CornerDownLeftIcon from "@hugeicons/core-free-icons/CornerDownLeftIcon";
import Notebook01Icon from "@hugeicons/core-free-icons/Notebook01Icon";
import ReflexIcon from "@hugeicons/core-free-icons/ReflexIcon";
import Search01Icon from "@hugeicons/core-free-icons/Search01Icon";
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react";
import React, {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

const ALGOLIA_APP_ID = "WLK9YABRW4";
const ALGOLIA_SEARCH_API_KEY = "7abb638647d3aa25e7a6d29dfdca2212";
const ALGOLIA_INDEX_NAME = "reflex_dev_wlk9yabrw4_pages";
const ALGOLIA_SEARCH_ENDPOINT = `https://${ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/${encodeURIComponent(ALGOLIA_INDEX_NAME)}/query`;

const SEARCH_DEBOUNCE_MS = 350;
const MIN_QUERY_LENGTH = 2;
const MAX_CACHED_QUERIES = 50;
const ROOT_THEME_SELECTOR = '.radix-themes[data-is-root-theme="true"]';
const ORBIT_ORDER = [0, 1, 2, 5, 8, 7, 6, 3];
const ORBIT_DELAYS = Array.from({ length: 9 }, (_, index) => {
  const order = ORBIT_ORDER.indexOf(index);
  return order === -1 ? null : order * 110;
});

type SearchStatus = "idle" | "loading" | "ready" | "error";
type ResultSection =
  | "XY"
  | "Components"
  | "API Reference"
  | "Docs"
  | "Blog"
  | "Reflex";

const RESULT_ICONS: Record<ResultSection, IconSvgElement> = {
  XY: ChartLineData01Icon,
  Components: ComponentIcon,
  "API Reference": ApiIcon,
  Docs: BookOpen01Icon,
  Blog: Notebook01Icon,
  Reflex: ReflexIcon,
};

const RESULT_PATH_PREFIXES: Partial<Record<ResultSection, string[]>> = {
  Docs: ["docs"],
  Components: ["docs", "library"],
  XY: ["docs", "xy"],
  "API Reference": ["docs", "api-reference"],
};

const RESULT_PATH_LABELS: Record<string, string> = {
  ai: "AI",
  api: "API",
  cli: "CLI",
  css: "CSS",
  html: "HTML",
  http: "HTTP",
  https: "HTTPS",
  js: "JS",
  json: "JSON",
  llm: "LLM",
  mcp: "MCP",
  sql: "SQL",
  ui: "UI",
  url: "URL",
  ux: "UX",
  xml: "XML",
  xy: "XY",
};

interface AlgoliaHit {
  objectID: string;
  url?: string;
  path?: string;
  title?: string;
  description?: string;
  headers?: string[];
}

interface SearchHit extends AlgoliaHit {
  url: string;
  section: ResultSection;
  displayTitle: string;
  breadcrumbs: string[];
}

interface AlgoliaResponse {
  hits: AlgoliaHit[];
  nbHits: number;
}

interface CachedSearch {
  hits: SearchHit[];
  nbHits: number;
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return (
    target.isContentEditable ||
    target.tagName === "INPUT" ||
    target.tagName === "SELECT" ||
    target.tagName === "TEXTAREA"
  );
}

function normalizeResultUrl(hit: AlgoliaHit): URL | null {
  const candidate = hit.url ?? hit.objectID;
  try {
    const url = new URL(candidate, "https://reflex.dev");
    const isReflexHost =
      url.hostname === "reflex.dev" || url.hostname.endsWith(".reflex.dev");
    if (!isReflexHost || !["http:", "https:"].includes(url.protocol)) {
      return null;
    }
    return url;
  } catch {
    return null;
  }
}

function resultSection(pathname: string): ResultSection {
  if (pathname.startsWith("/docs/xy/")) {
    return "XY";
  }
  if (pathname.startsWith("/docs/library/")) {
    return "Components";
  }
  if (pathname.startsWith("/docs/api-reference/")) {
    return "API Reference";
  }
  if (pathname.startsWith("/docs/")) {
    return "Docs";
  }
  if (pathname.startsWith("/blog/")) {
    return "Blog";
  }
  return "Reflex";
}

function cleanResultLabel(value: string): string {
  return value.replace(/\s+·\s+Reflex(?: Docs)?$/i, "").trim();
}

function resultTitle(hit: AlgoliaHit): string {
  return cleanResultLabel(hit.title || hit.headers?.at(-1) || "Reflex");
}

function resultPathLabel(pathSegment: string): string {
  return pathSegment
    .split("-")
    .map(
      (word) =>
        RESULT_PATH_LABELS[word] ??
        `${word.charAt(0).toUpperCase()}${word.slice(1)}`,
    )
    .join(" ");
}

function resultPathBreadcrumbs(
  pathname: string,
  section: ResultSection,
): string[] {
  const prefix = RESULT_PATH_PREFIXES[section];
  if (!prefix) {
    return [];
  }

  const pathSegments = pathname.split("/").filter(Boolean);
  if (!prefix.every((segment, index) => pathSegments[index] === segment)) {
    return [];
  }

  return pathSegments.slice(prefix.length, -1).slice(0, 2).map(resultPathLabel);
}

function resultBreadcrumbs(pathname: string, section: ResultSection): string[] {
  const root = section === "Blog" ? "Blogs" : section;
  const normalizedRoot = root.toLowerCase();
  return [
    root,
    ...resultPathBreadcrumbs(pathname, section).filter(
      (breadcrumb) => breadcrumb.toLowerCase() !== normalizedRoot,
    ),
  ];
}

function normalizeHits(hits: AlgoliaHit[]): SearchHit[] {
  return hits.flatMap((hit) => {
    const normalizedUrl = normalizeResultUrl(hit);
    if (!normalizedUrl) {
      return [];
    }

    const url = normalizedUrl.toString();
    const pathname = normalizedUrl.pathname;
    const section = resultSection(pathname);
    const displayTitle = resultTitle(hit);
    return [
      {
        ...hit,
        url,
        section,
        displayTitle,
        breadcrumbs: resultBreadcrumbs(pathname, section),
      },
    ];
  });
}

function LoadingState() {
  return (
    <span aria-hidden="true" className="ReflexSearch-loadingState">
      {ORBIT_DELAYS.map((delay, index) => (
        <span
          className="ReflexSearch-loadingCell"
          key={index}
          style={{
            opacity: delay === null ? 0.07 : 0.15,
            animation:
              delay === null
                ? "none"
                : `loading-state-pixel-on 950ms ease-in-out ${delay}ms infinite`,
          }}
        />
      ))}
    </span>
  );
}

function ResultIcon({ section }: { section: ResultSection }) {
  return (
    <HugeiconsIcon
      aria-hidden="true"
      className="ReflexSearch-resultIcon"
      data-section={section}
      icon={RESULT_ICONS[section]}
      size={20}
      strokeWidth={1.5}
    />
  );
}

export function AlgoliaSearch() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [nbHits, setNbHits] = useState(0);
  const [status, setStatus] = useState<SearchStatus>("idle");
  const [resultsQuery, setResultsQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const [modifierKey] = useState(() =>
    typeof navigator !== "undefined" &&
    /Mac|iPhone|iPad|iPod/.test(navigator.userAgent)
      ? "⌘"
      : "Ctrl",
  );
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hitRefs = useRef<Array<HTMLAnchorElement | null>>([]);
  const cacheRef = useRef(new Map<string, CachedSearch>());
  const requestRef = useRef<AbortController | null>(null);
  const titleId = useId();
  const resultsId = useId();

  const resetSearch = useCallback(() => {
    requestRef.current?.abort();
    requestRef.current = null;
    setQuery("");
    setHits([]);
    setNbHits(0);
    setStatus("idle");
    setResultsQuery("");
    setActiveIndex(-1);
  }, []);
  const openSearch = useCallback(() => setIsOpen(true), []);
  const closeSearch = useCallback(() => {
    setIsOpen(false);
    resetSearch();
    window.requestAnimationFrame(() => buttonRef.current?.focus());
  }, [resetSearch]);
  const resultsAreInteractive =
    status === "ready" && resultsQuery === query.trim().toLocaleLowerCase();

  const moveSelection = useCallback(
    (offset: number) => {
      if (!resultsAreInteractive || hits.length === 0) {
        return;
      }

      setActiveIndex((current) => {
        const nextIndex =
          current < 0
            ? offset > 0
              ? 0
              : hits.length - 1
            : (current + offset + hits.length) % hits.length;
        window.requestAnimationFrame(() =>
          hitRefs.current[nextIndex]?.scrollIntoView({ block: "nearest" }),
        );
        return nextIndex;
      });
    },
    [hits.length, resultsAreInteractive],
  );

  const handleInputKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          moveSelection(1);
          break;
        case "ArrowUp":
          event.preventDefault();
          moveSelection(-1);
          break;
        case "Enter": {
          const activeHit = hits[activeIndex];
          if (!activeHit) {
            return;
          }
          event.preventDefault();
          window.location.assign(activeHit.url);
          break;
        }
      }
    },
    [activeIndex, hits, moveSelection],
  );

  const keepFocusInDialog = useCallback(
    (event: React.KeyboardEvent<HTMLElement>) => {
      if (event.key !== "Tab") {
        return;
      }

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) {
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [],
  );

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      const key = event.key.toLocaleLowerCase();
      const commandSearch = key === "k" && (event.metaKey || event.ctrlKey);
      const slashSearch =
        key === "/" && !isOpen && !isEditableTarget(event.target);

      if (commandSearch || slashSearch) {
        event.preventDefault();
        isOpen ? closeSearch() : openSearch();
      } else if (event.key === "Escape" && isOpen) {
        event.preventDefault();
        closeSearch();
      }
    }

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [closeSearch, isOpen, openSearch]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => inputRef.current?.focus());

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const trimmedQuery = query.trim();
    if (trimmedQuery.length < MIN_QUERY_LENGTH) {
      setHits([]);
      setNbHits(0);
      setStatus("idle");
      setResultsQuery("");
      setActiveIndex(-1);
      return;
    }

    const cacheKey = trimmedQuery.toLocaleLowerCase();
    const cachedSearch = cacheRef.current.get(cacheKey);
    if (cachedSearch) {
      setHits(cachedSearch.hits);
      setNbHits(cachedSearch.nbHits);
      setStatus("ready");
      setResultsQuery(cacheKey);
      setActiveIndex(cachedSearch.hits.length > 0 ? 0 : -1);
      return;
    }

    setStatus("loading");
    setActiveIndex(-1);

    const controller = new AbortController();
    requestRef.current = controller;
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(ALGOLIA_SEARCH_ENDPOINT, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Algolia-API-Key": ALGOLIA_SEARCH_API_KEY,
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
          },
          body: JSON.stringify({
            query: trimmedQuery,
            hitsPerPage: 10,
            attributesToRetrieve: [
              "objectID",
              "url",
              "path",
              "title",
              "description",
              "headers",
            ],
            attributesToHighlight: [],
            analytics: false,
            clickAnalytics: false,
            enablePersonalization: false,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(
            `Search request failed with status ${response.status}`,
          );
        }

        const payload = (await response.json()) as AlgoliaResponse;
        if (controller.signal.aborted) {
          return;
        }
        const search = {
          hits: normalizeHits(payload.hits),
          nbHits: payload.nbHits,
        };

        if (cacheRef.current.size >= MAX_CACHED_QUERIES) {
          const oldestKey = cacheRef.current.keys().next().value;
          if (oldestKey) {
            cacheRef.current.delete(oldestKey);
          }
        }
        cacheRef.current.set(cacheKey, search);

        setHits(search.hits);
        setNbHits(search.nbHits);
        setStatus("ready");
        setResultsQuery(cacheKey);
        setActiveIndex(search.hits.length > 0 ? 0 : -1);
      } catch {
        if (controller.signal.aborted) {
          return;
        }
        setHits([]);
        setNbHits(0);
        setStatus("error");
        setResultsQuery("");
        setActiveIndex(-1);
      } finally {
        if (requestRef.current === controller) {
          requestRef.current = null;
        }
      }
    }, SEARCH_DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
      if (requestRef.current === controller) {
        requestRef.current = null;
      }
    };
  }, [isOpen, query]);

  const portalRoot = useMemo(() => {
    if (!isOpen || typeof document === "undefined") {
      return null;
    }
    return (
      buttonRef.current?.closest(ROOT_THEME_SELECTOR) ??
      document.querySelector(ROOT_THEME_SELECTOR) ??
      document.body
    );
  }, [isOpen]);
  const activeResultId =
    activeIndex >= 0 ? `${resultsId}-result-${activeIndex}` : undefined;
  const showResults =
    status !== "idle" && (status !== "loading" || hits.length > 0);

  return (
    <div className="ReflexSearch-root">
      <style>{SEARCH_STYLES}</style>
      <button
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-label="Search Reflex"
        className="ReflexSearch-button"
        onClick={openSearch}
        ref={buttonRef}
        type="button"
      >
        <HugeiconsIcon
          aria-hidden="true"
          icon={Search01Icon}
          size={16}
          strokeWidth={1.5}
        />
        <span className="ReflexSearch-buttonText">Search</span>
        <kbd className="ReflexSearch-shortcut">
          <span>{modifierKey}</span>K
        </kbd>
      </button>

      {isOpen && portalRoot
        ? createPortal(
            <div
              className="ReflexSearch-overlay"
              data-status={status}
              onMouseDown={(event) => {
                if (event.currentTarget === event.target) {
                  closeSearch();
                }
              }}
            >
              <section
                aria-labelledby={titleId}
                aria-modal="true"
                className="ReflexSearch-dialog"
                data-results-visible={showResults}
                data-status={status}
                onKeyDown={keepFocusInDialog}
                ref={dialogRef}
                role="dialog"
              >
                <h2 className="ReflexSearch-visuallyHidden" id={titleId}>
                  Search Reflex
                </h2>
                <p
                  aria-atomic="true"
                  aria-live="polite"
                  className="ReflexSearch-visuallyHidden ReflexSearch-liveStatus"
                >
                  {status === "loading"
                    ? "Searching Reflex"
                    : status === "error"
                      ? "Search couldn’t load"
                      : status === "ready"
                        ? `${nbHits.toLocaleString()} result${nbHits === 1 ? "" : "s"}`
                        : ""}
                </p>

                <div className="ReflexSearch-inputRow">
                  <span className="ReflexSearch-inputIcon">
                    <HugeiconsIcon
                      aria-hidden="true"
                      icon={Search01Icon}
                      size={16}
                      strokeWidth={1.5}
                    />
                  </span>
                  <input
                    aria-activedescendant={activeResultId}
                    aria-controls={hits.length > 0 ? resultsId : undefined}
                    aria-expanded={hits.length > 0}
                    aria-label="Search docs, components, blog, and Reflex pages"
                    aria-autocomplete="list"
                    autoComplete="off"
                    className="ReflexSearch-input"
                    onChange={(event) => {
                      setQuery(event.target.value);
                      setActiveIndex(-1);
                    }}
                    onKeyDown={handleInputKeyDown}
                    placeholder="What are you searching for?"
                    ref={inputRef}
                    role="combobox"
                    spellCheck={false}
                    type="search"
                    value={query}
                  />
                  <span className="ReflexSearch-actions">
                    <span className="ReflexSearch-actionSlot">
                      {status === "loading" ? <LoadingState /> : null}
                    </span>
                    <button
                      aria-label="Close search"
                      className="ReflexSearch-escape"
                      onClick={closeSearch}
                      type="button"
                    >
                      <span className="ReflexSearch-escapeText">ESC</span>
                      <HugeiconsIcon
                        aria-hidden="true"
                        className="ReflexSearch-escapeIcon"
                        icon={Cancel01Icon}
                        size={18}
                        strokeWidth={1.5}
                      />
                    </button>
                  </span>
                </div>

                {showResults ? (
                  <>
                    <div
                      className="ReflexSearch-results scroll-mask-y-10 overscroll-none"
                      data-populated={hits.length > 0}
                    >
                      {status === "error" ? (
                        <div
                          className="ReflexSearch-emptyState"
                          data-tone="error"
                          role="alert"
                        >
                          <span className="ReflexSearch-emptyIcon">
                            <HugeiconsIcon
                              aria-hidden="true"
                              icon={Alert02Icon}
                              size={20}
                              strokeWidth={1.5}
                            />
                          </span>
                          <strong>Search couldn’t load</strong>
                          <p>Check your connection, then try again.</p>
                        </div>
                      ) : status === "ready" && hits.length === 0 ? (
                        <div
                          className="ReflexSearch-emptyState"
                          data-tone="neutral"
                        >
                          <strong>No results for “{query.trim()}”</strong>
                        </div>
                      ) : (
                        <ul
                          aria-busy={!resultsAreInteractive}
                          aria-label="Search results"
                          className="ReflexSearch-hitList"
                          data-interactive={resultsAreInteractive}
                          id={resultsId}
                          role="listbox"
                        >
                          {hits.map((hit, index) => (
                            <li key={hit.objectID} role="presentation">
                              <a
                                aria-disabled={!resultsAreInteractive}
                                aria-selected={index === activeIndex}
                                className="ReflexSearch-hit"
                                data-selected={index === activeIndex}
                                href={hit.url}
                                id={`${resultsId}-result-${index}`}
                                onClick={(event) => {
                                  if (!resultsAreInteractive) {
                                    event.preventDefault();
                                    return;
                                  }
                                  closeSearch();
                                }}
                                onFocus={() => {
                                  if (resultsAreInteractive) {
                                    setActiveIndex(index);
                                  }
                                }}
                                onMouseEnter={() => {
                                  if (resultsAreInteractive) {
                                    setActiveIndex(index);
                                  }
                                }}
                                ref={(element) => {
                                  hitRefs.current[index] = element;
                                }}
                                role="option"
                                tabIndex={-1}
                              >
                                <span className="ReflexSearch-hitBreadcrumbs">
                                  {hit.breadcrumbs.map((breadcrumb, index) => (
                                    <React.Fragment
                                      key={`${breadcrumb}-${index}`}
                                    >
                                      {index > 0 ? (
                                        <HugeiconsIcon
                                          aria-hidden="true"
                                          icon={ArrowRight01Icon}
                                          size={14}
                                          strokeWidth={1.5}
                                        />
                                      ) : null}
                                      <span>{breadcrumb}</span>
                                    </React.Fragment>
                                  ))}
                                </span>
                                <span className="ReflexSearch-hitTitleRow">
                                  <span className="ReflexSearch-hitIcon">
                                    <ResultIcon section={hit.section} />
                                  </span>
                                  <strong>{hit.displayTitle}</strong>
                                  <span
                                    aria-hidden="true"
                                    className="ReflexSearch-hitArrow"
                                  >
                                    <HugeiconsIcon
                                      icon={CornerDownLeftIcon}
                                      size={18}
                                      strokeWidth={1.5}
                                    />
                                  </span>
                                </span>
                                {hit.description ? (
                                  <span className="ReflexSearch-hitDescription">
                                    {hit.description}
                                  </span>
                                ) : null}
                              </a>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>

                    <footer className="ReflexSearch-footer">
                      {status === "ready" ? (
                        <span>
                          {nbHits.toLocaleString()} result
                          {nbHits === 1 ? "" : "s"}
                        </span>
                      ) : null}
                      <a
                        href="https://www.algolia.com/"
                        rel="noreferrer"
                        target="_blank"
                      >
                        Search by <strong>Algolia</strong>
                      </a>
                    </footer>
                  </>
                ) : null}
              </section>
            </div>,
            portalRoot,
          )
        : null}
    </div>
  );
}

const SEARCH_STYLES = `
  .ReflexSearch-root {
    align-items: center;
    display: flex;
    justify-content: center;
    max-height: 2rem;
    max-width: 10rem;
    min-height: 2rem;
    min-width: 0;
    width: 10rem;
  }

  .ReflexSearch-button {
    align-items: center;
    background: var(--secondary-1, #fff);
    border: 0;
    border-radius: 0.5rem;
    box-shadow: 0 -1px 0 rgba(0, 0, 0, 0.08) inset,
      0 0 0 1px rgba(0, 0, 0, 0.08) inset,
      0 1px 2px 0 rgba(0, 0, 0, 0.02),
      0 1px 4px 0 rgba(0, 0, 0, 0.02);
    color: var(--secondary-11, #646464);
    cursor: pointer;
    display: flex;
    font: 500 0.875rem/1.5rem var(--font-instrument-sans, system-ui, sans-serif);
    gap: 0.5rem;
    height: 2rem;
    justify-content: flex-start;
    max-width: 10rem;
    min-width: 0;
    padding: 0.375rem 0.5rem;
    transition: none;
    width: 100%;
  }

  .ReflexSearch-button:hover {
    background: var(--secondary-2, #f8f8f8);
  }

  .ReflexSearch-button:focus-visible,
  .ReflexSearch-escape:focus-visible,
  .ReflexSearch-hit:focus-visible {
    outline: 2px solid var(--primary-9, #6e56cf);
    outline-offset: 2px;
  }

  .ReflexSearch-buttonText {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ReflexSearch-shortcut {
    align-items: center;
    background: var(--secondary-3, #f0f0f3);
    border: 0;
    color: var(--secondary-9, #8a8a8a);
    box-shadow: none;
    display: inline-flex;
    border-radius: 0.25rem;
    font-family: var(--font-instrument-sans, system-ui, sans-serif);
    font-size: 0.8125rem;
    font-weight: 475;
    gap: 0.125rem;
    height: 1.25rem;
    justify-content: center;
    line-height: 1.25rem;
    margin-left: auto;
    padding: 0 0.25rem;
    width: fit-content;
  }

  .ReflexSearch-overlay {
    align-items: flex-start;
    backdrop-filter: blur(18px);
    background: rgba(18, 17, 19, 0.48);
    display: flex;
    inset: 0;
    justify-content: center;
    padding: min(16vh, 7.5rem) 1rem 1rem;
    position: fixed;
    z-index: 2147483000;
  }

  .ReflexSearch-dialog {
    animation: ReflexSearch-dialog-enter 180ms
      cubic-bezier(0.32, 0.72, 0, 1) both;
    background: var(--secondary-1, #fff);
    border: 1px solid var(--secondary-a4, rgba(0, 0, 0, 0.08));
    border-radius: 0.75rem;
    box-shadow: 0 24px 64px rgba(18, 17, 19, 0.18),
      0 8px 24px rgba(18, 17, 19, 0.1),
      0 2px 8px rgba(18, 17, 19, 0.08);
    color: var(--secondary-12, #202020);
    display: flex;
    flex-direction: column;
    font-family: var(--font-instrument-sans, system-ui, sans-serif);
    max-height: min(42rem, calc(100vh - 2rem));
    overflow: hidden;
    transform-origin: top center;
    width: min(90vw, 720px);
  }

  .ReflexSearch-inputRow {
    align-items: center;
    border-bottom: 1px solid var(--secondary-4, #e8e8e8);
    box-sizing: border-box;
    display: flex;
    gap: 0.75rem;
    height: 3rem;
    min-height: 3rem;
    padding: 0.75rem 1.25rem;
  }

  .ReflexSearch-dialog[data-results-visible="false"] .ReflexSearch-inputRow {
    border-bottom-color: transparent;
  }

  .ReflexSearch-inputIcon {
    color: var(--secondary-11, #646464);
    display: flex;
    flex: 0 0 auto;
  }

  .ReflexSearch-input {
    appearance: none;
    background: transparent;
    border: 0;
    color: var(--secondary-12, #202020);
    flex: 1 1 0%;
    font: 500 1rem/1.5rem var(--font-instrument-sans, system-ui, sans-serif);
    min-width: 0;
    outline: 0;
    padding: 0;
    width: 0;
  }

  .ReflexSearch-input::placeholder {
    color: var(--secondary-9, #8a8a8a);
    font-weight: 500;
  }

  .ReflexSearch-input::-webkit-search-cancel-button {
    display: none;
  }

  .ReflexSearch-actions {
    align-items: center;
    align-self: center;
    display: grid;
    flex: 0 0 auto;
    gap: 0.375rem;
    grid-template-columns: 1.75rem 2.5rem;
    position: static;
    right: auto;
    top: auto;
    transform: none;
  }

  .ReflexSearch-actionSlot {
    align-items: center;
    display: flex;
    flex: 0 0 1.75rem;
    height: 1.75rem;
    justify-content: center;
  }

  .ReflexSearch-escape {
    align-items: center;
    background: var(--c-white-1, #fff);
    border: 1px solid var(--secondary-4, #e8e8e8);
    border-radius: 0.375rem;
    color: var(--secondary-11, #646464);
    cursor: pointer;
    display: flex;
    flex-shrink: 0;
    font: 475 0.75rem/1rem var(--font-instrument-sans, system-ui, sans-serif);
    gap: 0.25rem;
    height: 1.5rem;
    justify-content: center;
    padding: 0 0.375rem;
    width: 2.5rem;
  }

  .ReflexSearch-escapeIcon {
    display: none;
  }

  .ReflexSearch-results {
    height: 34rem;
    overflow-y: auto;
    padding: 1rem;
    position: relative;
    scrollbar-width: thin;
  }

  .ReflexSearch-results[data-populated="false"] {
    height: 20rem;
  }

  .ReflexSearch-results[data-populated="false"] .ReflexSearch-emptyState {
    height: 100%;
    min-height: 0;
  }

  .ReflexSearch-emptyState {
    align-items: center;
    color: var(--secondary-10, #7b7b7b);
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    justify-content: center;
    min-height: 31rem;
    padding: 2rem;
    text-align: center;
  }

  .ReflexSearch-emptyState strong {
    color: var(--secondary-12, #202020);
    font-size: 1.125rem;
    font-weight: 500;
    line-height: 1.5rem;
    margin: 0;
    max-width: 32rem;
    overflow-wrap: anywhere;
    text-wrap: balance;
  }

  .ReflexSearch-emptyState p {
    font-size: 0.9375rem;
    line-height: 1.375rem;
    margin: 0;
    max-width: 32rem;
    text-wrap: pretty;
  }

  .ReflexSearch-emptyIcon {
    align-items: center;
    background: var(--primary-3, #f3f0ff);
    border: 1px solid var(--primary-a5, rgba(110, 86, 207, 0.16));
    border-radius: 999px;
    box-shadow: 0 1px 2px rgba(18, 17, 19, 0.04);
    color: var(--primary-9, #6e56cf);
    display: flex;
    height: 2.5rem;
    justify-content: center;
    margin-bottom: 0.5rem;
    width: 2.5rem;
  }

  .ReflexSearch-emptyState[data-tone="error"] .ReflexSearch-emptyIcon {
    background: var(--red-3, #ffefef);
    border-color: var(--red-a5, rgba(205, 43, 49, 0.2));
    color: var(--red-9, #e5484d);
  }

  .ReflexSearch-hitList {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .ReflexSearch-hitList[data-interactive="false"] {
    pointer-events: none;
  }

  .ReflexSearch-hit {
    align-items: stretch;
    background: var(--secondary-1, #fff);
    border: 1px solid var(--secondary-a4, rgba(0, 0, 0, 0.08));
    border-radius: 0.75rem;
    color: var(--secondary-12, #202020);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    font-weight: 415;
    gap: 0.375rem;
    min-height: 5.5rem;
    padding: 0.75rem 1rem;
    user-select: none;
    text-decoration: none;
  }

  .ReflexSearch-hit[data-selected="true"] {
    background: var(--primary-2, #fbfaff);
    border-color: var(--primary-7, #c9bfff);
  }

  .ReflexSearch-hit:active {
    background: var(--primary-3, #f3f0ff);
  }

  .ReflexSearch-hitBreadcrumbs {
    align-items: center;
    color: var(--secondary-10, #7b7b7b);
    display: flex;
    font-size: 0.75rem;
    gap: 0.375rem;
    line-height: 1.125rem;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
  }

  .ReflexSearch-hitBreadcrumbs > span {
    flex: 0 0 auto;
  }

  .ReflexSearch-hitTitleRow {
    align-items: center;
    display: flex;
    gap: 0.625rem;
    min-width: 0;
  }

  .ReflexSearch-hitIcon {
    align-items: center;
    color: var(--secondary-11, #646464);
    display: flex;
    flex: 0 0 auto;
    height: 1.25rem;
    justify-content: center;
    width: 1.25rem;
  }

  .ReflexSearch-hitTitleRow strong {
    flex: 1;
    font-size: 1rem;
    font-weight: 500;
    line-height: 1.5rem;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ReflexSearch-hitDescription {
    color: var(--secondary-10, #7b7b7b);
    display: block;
    font-size: 0.875rem;
    line-height: 1.25rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ReflexSearch-hitArrow {
    color: var(--secondary-10, #7b7b7b);
    display: flex;
    flex: 0 0 auto;
    margin-left: auto;
    opacity: 0;
    transition: opacity 150ms ease;
  }

  .ReflexSearch-hit[data-selected="true"] .ReflexSearch-hitArrow {
    color: var(--primary-9, #6e56cf);
    opacity: 1;
  }

  .ReflexSearch-footer {
    align-items: center;
    border-top: 1px solid var(--secondary-4, #e8e8e8);
    color: var(--secondary-9, #8a8a8a);
    display: flex;
    font-size: 0.75rem;
    font-variant-numeric: tabular-nums;
    font-weight: 415;
    justify-content: space-between;
    line-height: 1rem;
    min-height: 2.75rem;
    padding: 0 1rem;
  }

  .ReflexSearch-footer a {
    color: var(--secondary-10, #7b7b7b);
    margin-left: auto;
    text-decoration: none;
  }

  .ReflexSearch-loadingState {
    color: var(--secondary-11, #646464);
    display: grid;
    flex: 0 0 auto;
    gap: 2px;
    grid-template-columns: repeat(3, 4px);
    height: 16px;
    pointer-events: none;
    user-select: none;
    width: 16px;
  }

  .ReflexSearch-loadingCell {
    background: currentColor;
    border-radius: 1px;
    height: 4px;
    width: 4px;
  }

  .ReflexSearch-visuallyHidden {
    height: 1px;
    margin: -1px;
    overflow: hidden;
    padding: 0;
    position: absolute;
    width: 1px;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }

  .dark .ReflexSearch-dialog,
  [data-theme="dark"] .ReflexSearch-dialog {
    background: var(--secondary-4, #1e2025);
    border-color: var(--secondary-7, #363c44);
  }

  .dark .ReflexSearch-dialog[data-results-visible="true"] .ReflexSearch-inputRow,
  [data-theme="dark"] .ReflexSearch-dialog[data-results-visible="true"] .ReflexSearch-inputRow {
    border-bottom-color: var(--secondary-7, #363c44);
  }

  .dark .ReflexSearch-footer,
  [data-theme="dark"] .ReflexSearch-footer {
    border-top-color: var(--secondary-7, #363c44);
  }

  .dark .ReflexSearch-button,
  [data-theme="dark"] .ReflexSearch-button {
    background: var(--secondary-2, #242424);
    box-shadow: 0 -1px 0 rgba(255, 255, 255, 0.06) inset,
      0 0 0 1px rgba(255, 255, 255, 0.04) inset;
  }

  .dark .ReflexSearch-button:hover,
  [data-theme="dark"] .ReflexSearch-button:hover {
    background: var(--secondary-3, #2c2c2c);
  }

  @keyframes loading-state-pixel-on {
    0%, 45%, 100% {
      opacity: 0.15;
    }

    18% {
      opacity: 1;
    }
  }

  @keyframes ReflexSearch-dialog-enter {
    from {
      opacity: 0;
      transform: scale(0.96);
    }

    to {
      opacity: 1;
      transform: scale(1);
    }
  }

  @media (max-width: 80em) {
    .ReflexSearch-root {
      width: auto;
    }

    .ReflexSearch-button {
      height: 2rem;
      justify-content: center;
      max-width: 6em;
      padding: 2px 12px;
      width: 2rem;
    }

    .ReflexSearch-button > svg {
      flex-shrink: 0;
      height: 1.25rem;
      margin-right: 0;
      width: 1.25rem;
    }

    .ReflexSearch-buttonText,
    .ReflexSearch-shortcut {
      display: none;
    }
  }

  @media (max-width: 40rem) {
    .ReflexSearch-overlay {
      align-items: flex-start;
      padding: calc(env(safe-area-inset-top, 0px) + 1.5rem) 1rem 1rem;
    }

    .ReflexSearch-dialog {
      border: 1px solid var(--secondary-a4, rgba(0, 0, 0, 0.08));
      border-radius: 0.75rem;
      height: calc(100dvh - env(safe-area-inset-top, 0px) - 2.5rem);
      max-height: none;
      width: 100%;
    }

    .ReflexSearch-dialog[data-status="idle"] {
      height: auto;
    }

    .ReflexSearch-inputIcon > svg {
      height: 1.375rem;
      width: 1.375rem;
    }

    .ReflexSearch-results {
      flex: 1;
      height: auto;
      padding: 1rem;
    }

    .ReflexSearch-hit {
      min-height: 5.5rem;
      padding: 0.75rem;
    }

    .ReflexSearch-hitTitleRow {
      gap: 0.5rem;
    }

    .ReflexSearch-actionSlot {
      flex-basis: 2.25rem;
      height: 2.25rem;
    }

    .ReflexSearch-actions {
      grid-template-columns: 2.25rem 2.25rem;
    }

    .ReflexSearch-escape {
      border-radius: 0.625rem;
      height: 2.25rem;
      padding: 0;
      position: static;
      width: 2.25rem;
    }

    .ReflexSearch-escapeText {
      display: none;
    }

    .ReflexSearch-escapeIcon {
      display: block;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .ReflexSearch-dialog {
      animation: none;
    }

    .ReflexSearch-button {
      transition: none;
    }

    .ReflexSearch-loadingCell {
      animation: none !important;
    }
  }
`;

export default AlgoliaSearch;
