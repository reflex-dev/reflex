"use client";

import React, { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

const ALGOLIA_APP_ID = "WLK9YABRW4";
const ALGOLIA_SEARCH_API_KEY = "aa0ebd175fcfb78706a053e5e71f6b58";
const ALGOLIA_INDEX_NAME = "reflex_dev_wlk9yabrw4_pages";
const ALGOLIA_SEARCH_ENDPOINT = `https://${ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/${encodeURIComponent(ALGOLIA_INDEX_NAME)}/query`;

const SEARCH_DEBOUNCE_MS = 350;
const MIN_QUERY_LENGTH = 2;
const MAX_CACHED_QUERIES = 50;
const ROOT_THEME_SELECTOR = '.radix-themes[data-is-root-theme="true"]';

type SearchStatus = "idle" | "loading" | "ready" | "error";

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

function normalizeResultUrl(hit: AlgoliaHit): string | null {
  const candidate = hit.url ?? hit.objectID;
  try {
    const url = new URL(candidate, "https://reflex.dev");
    const isReflexHost =
      url.hostname === "reflex.dev" || url.hostname.endsWith(".reflex.dev");
    if (!isReflexHost || !["http:", "https:"].includes(url.protocol)) {
      return null;
    }
    return url.toString();
  } catch {
    return null;
  }
}

function normalizeHits(hits: AlgoliaHit[]): SearchHit[] {
  return hits.flatMap((hit) => {
    const url = normalizeResultUrl(hit);
    return url ? [{ ...hit, url }] : [];
  });
}

function resultSection(url: string): string {
  const path = new URL(url).pathname;
  if (path.startsWith("/docs/xy/")) {
    return "XY";
  }
  if (path.startsWith("/docs/library/")) {
    return "Components";
  }
  if (path.startsWith("/docs/api-reference/")) {
    return "API Reference";
  }
  if (path.startsWith("/docs/")) {
    return "Docs";
  }
  if (path.startsWith("/blog/")) {
    return "Blog";
  }
  return "Reflex";
}

function resultTitle(hit: SearchHit): string {
  const fallbackHeader = hit.headers?.at(-1);
  return (hit.title || fallbackHeader || "Reflex").replace(
    /\s+·\s+Reflex(?: Docs)?$/i,
    "",
  );
}

function HighlightedText({ text, query }: { text: string; query: string }) {
  const terms = query.trim().split(/\s+/).filter(Boolean);
  if (terms.length === 0) {
    return text;
  }

  const escapedTerms = terms.map((term) =>
    term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
  );
  const pattern = new RegExp(`(${escapedTerms.join("|")})`, "gi");
  const normalizedTerms = new Set(
    terms.map((term) => term.toLocaleLowerCase()),
  );

  return text
    .split(pattern)
    .map((part, index) =>
      normalizedTerms.has(part.toLocaleLowerCase()) ? (
        <mark key={`${part}-${index}`}>{part}</mark>
      ) : (
        part
      ),
    );
}

function SearchIcon({ size = 16 }: { size?: number }) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
    >
      <circle
        cx="11"
        cy="11"
        r="6.75"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="m16 16 4 4"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.5"
      />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height="16"
      viewBox="0 0 24 24"
      width="16"
    >
      <path
        d="m7 7 10 10M17 7 7 17"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.5"
      />
    </svg>
  );
}

function LoadingIcon() {
  return (
    <svg
      aria-label="Searching"
      className="ReflexSearch-spinner"
      fill="none"
      height="16"
      viewBox="0 0 24 24"
      width="16"
    >
      <circle
        cx="12"
        cy="12"
        opacity="0.25"
        r="9"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="2"
      />
    </svg>
  );
}

export function AlgoliaSearch() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [nbHits, setNbHits] = useState(0);
  const [status, setStatus] = useState<SearchStatus>("idle");
  const [modifierKey, setModifierKey] = useState("⌘");
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const cacheRef = useRef(new Map<string, CachedSearch>());
  const titleId = useId();
  const resultsId = useId();

  const openSearch = useCallback(() => setIsOpen(true), []);
  const closeSearch = useCallback(() => {
    setIsOpen(false);
    window.requestAnimationFrame(() => buttonRef.current?.focus());
  }, []);

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
    setModifierKey(
      /Mac|iPhone|iPad|iPod/.test(navigator.platform) ? "⌘" : "Ctrl",
    );
  }, []);

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
      return;
    }

    const cacheKey = trimmedQuery.toLocaleLowerCase();
    const cachedSearch = cacheRef.current.get(cacheKey);
    if (cachedSearch) {
      setHits(cachedSearch.hits);
      setNbHits(cachedSearch.nbHits);
      setStatus("ready");
      return;
    }

    setHits([]);
    setNbHits(0);
    setStatus("loading");

    const controller = new AbortController();
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
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setHits([]);
        setNbHits(0);
        setStatus("error");
      }
    }, SEARCH_DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [isOpen, query]);

  const portalRoot =
    typeof document === "undefined"
      ? null
      : (buttonRef.current?.closest(ROOT_THEME_SELECTOR) ??
        document.querySelector(ROOT_THEME_SELECTOR) ??
        document.body);

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
        <SearchIcon />
        <span className="ReflexSearch-buttonText">Search</span>
        <kbd className="ReflexSearch-shortcut">
          <span>{modifierKey}</span>K
        </kbd>
      </button>

      {isOpen && portalRoot
        ? createPortal(
            <div
              className="ReflexSearch-overlay"
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
                onKeyDown={keepFocusInDialog}
                ref={dialogRef}
                role="dialog"
              >
                <h2 className="ReflexSearch-visuallyHidden" id={titleId}>
                  Search Reflex
                </h2>

                <div className="ReflexSearch-inputRow">
                  <span className="ReflexSearch-inputIcon">
                    <SearchIcon size={20} />
                  </span>
                  <input
                    aria-controls={resultsId}
                    aria-label="Search docs, components, blog, and Reflex pages"
                    autoComplete="off"
                    className="ReflexSearch-input"
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search Reflex"
                    ref={inputRef}
                    spellCheck={false}
                    type="search"
                    value={query}
                  />
                  {status === "loading" ? (
                    <LoadingIcon />
                  ) : query ? (
                    <button
                      aria-label="Clear search"
                      className="ReflexSearch-iconButton"
                      onClick={() => setQuery("")}
                      type="button"
                    >
                      <CloseIcon />
                    </button>
                  ) : null}
                  <button
                    aria-label="Close search"
                    className="ReflexSearch-escape"
                    onClick={closeSearch}
                    type="button"
                  >
                    Esc
                  </button>
                </div>

                <div
                  aria-live="polite"
                  className="ReflexSearch-results"
                  id={resultsId}
                >
                  {status === "idle" ? (
                    <div className="ReflexSearch-emptyState">
                      <span className="ReflexSearch-emptyIcon">
                        <SearchIcon size={22} />
                      </span>
                      <strong>Search all of Reflex</strong>
                      <p>
                        Docs, XY, components, blog posts, and product pages.
                      </p>
                      <span>
                        Type at least {MIN_QUERY_LENGTH} characters to search.
                      </span>
                    </div>
                  ) : status === "loading" ? (
                    <div className="ReflexSearch-emptyState">
                      <LoadingIcon />
                      <strong>Searching…</strong>
                      <p>
                        Looking across docs, XY, the blog, and Reflex pages.
                      </p>
                    </div>
                  ) : status === "error" ? (
                    <div className="ReflexSearch-emptyState" role="alert">
                      <strong>Search is temporarily unavailable</strong>
                      <p>Please check your connection and try again.</p>
                    </div>
                  ) : status === "ready" && hits.length === 0 ? (
                    <div className="ReflexSearch-emptyState">
                      <strong>No results for “{query.trim()}”</strong>
                      <p>Try another term or a shorter phrase.</p>
                    </div>
                  ) : (
                    <ul className="ReflexSearch-hitList">
                      {hits.map((hit) => (
                        <li key={hit.objectID}>
                          <a
                            className="ReflexSearch-hit"
                            href={hit.url}
                            onClick={closeSearch}
                          >
                            <span className="ReflexSearch-hitIcon">
                              <SearchIcon />
                            </span>
                            <span className="ReflexSearch-hitContent">
                              <span className="ReflexSearch-hitMeta">
                                {resultSection(hit.url)}
                              </span>
                              <strong>
                                <HighlightedText
                                  text={resultTitle(hit)}
                                  query={query}
                                />
                              </strong>
                              {hit.description ? (
                                <span className="ReflexSearch-hitDescription">
                                  <HighlightedText
                                    text={hit.description}
                                    query={query}
                                  />
                                </span>
                              ) : null}
                            </span>
                            <span
                              aria-hidden="true"
                              className="ReflexSearch-hitArrow"
                            >
                              ↗
                            </span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <footer className="ReflexSearch-footer">
                  <span>
                    {status === "ready"
                      ? `${nbHits.toLocaleString()} result${nbHits === 1 ? "" : "s"}`
                      : "Keyword search only"}
                  </span>
                  <a
                    href="https://www.algolia.com/"
                    rel="noreferrer"
                    target="_blank"
                  >
                    Search by <strong>Algolia</strong>
                  </a>
                </footer>
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
    display: flex;
    min-width: 0;
  }

  .ReflexSearch-button {
    align-items: center;
    background: var(--secondary-1, #fff);
    border: 0;
    border-radius: 0.5rem;
    box-shadow: 0 -1px 0 rgba(0, 0, 0, 0.08) inset,
      0 0 0 1px rgba(0, 0, 0, 0.08) inset,
      0 1px 4px rgba(0, 0, 0, 0.04);
    color: var(--secondary-11, #646464);
    cursor: pointer;
    display: flex;
    font: 500 0.875rem/1.5rem var(--font-instrument-sans, system-ui, sans-serif);
    gap: 0.5rem;
    height: 2rem;
    justify-content: flex-start;
    max-width: 10rem;
    min-width: 0;
    padding: 0.25rem 0.5rem;
    transition: background-color 120ms ease, box-shadow 120ms ease;
    width: 10rem;
  }

  .ReflexSearch-button:hover {
    background: var(--secondary-2, #f8f8f8);
  }

  .ReflexSearch-button:focus-visible,
  .ReflexSearch-iconButton:focus-visible,
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
    background: transparent;
    border: 0;
    color: var(--secondary-9, #8a8a8a);
    display: inline-flex;
    font: 500 0.6875rem/1 var(--font-instrument-sans, system-ui, sans-serif);
    gap: 0.125rem;
    margin-left: auto;
    padding: 0;
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
    background: var(--secondary-1, #fff);
    border: 1px solid var(--secondary-5, #e8e8e8);
    border-radius: 0.875rem;
    box-shadow: 0 24px 80px rgba(18, 17, 19, 0.22),
      0 2px 8px rgba(18, 17, 19, 0.12);
    color: var(--secondary-12, #202020);
    display: flex;
    flex-direction: column;
    font-family: var(--font-instrument-sans, system-ui, sans-serif);
    max-height: min(42rem, calc(100vh - 2rem));
    overflow: hidden;
    width: min(44rem, 100%);
  }

  .ReflexSearch-inputRow {
    align-items: center;
    border-bottom: 1px solid var(--secondary-5, #e8e8e8);
    display: flex;
    gap: 0.75rem;
    min-height: 4rem;
    padding: 0 1rem;
  }

  .ReflexSearch-inputIcon {
    color: var(--primary-9, #6e56cf);
    display: flex;
  }

  .ReflexSearch-input {
    appearance: none;
    background: transparent;
    border: 0;
    color: var(--secondary-12, #202020);
    flex: 1;
    font: 500 1rem/1.5rem var(--font-instrument-sans, system-ui, sans-serif);
    min-width: 0;
    outline: 0;
    padding: 1.125rem 0;
  }

  .ReflexSearch-input::placeholder {
    color: var(--secondary-9, #8a8a8a);
  }

  .ReflexSearch-input::-webkit-search-cancel-button {
    display: none;
  }

  .ReflexSearch-iconButton,
  .ReflexSearch-escape {
    align-items: center;
    background: var(--secondary-3, #f0f0f0);
    border: 1px solid var(--secondary-5, #e8e8e8);
    border-radius: 0.375rem;
    color: var(--secondary-11, #646464);
    cursor: pointer;
    display: inline-flex;
    justify-content: center;
  }

  .ReflexSearch-iconButton {
    height: 1.75rem;
    width: 1.75rem;
  }

  .ReflexSearch-escape {
    font: 500 0.6875rem/1 var(--font-instrument-sans, system-ui, sans-serif);
    height: 1.75rem;
    padding: 0 0.5rem;
  }

  .ReflexSearch-results {
    min-height: 15rem;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 0.75rem;
  }

  .ReflexSearch-emptyState {
    align-items: center;
    color: var(--secondary-10, #7b7b7b);
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 13.5rem;
    padding: 2rem;
    text-align: center;
  }

  .ReflexSearch-emptyState strong {
    color: var(--secondary-12, #202020);
    font-size: 1rem;
    margin-top: 0.875rem;
  }

  .ReflexSearch-emptyState p {
    font-size: 0.875rem;
    margin: 0.375rem 0;
  }

  .ReflexSearch-emptyState > span:last-child {
    font-size: 0.75rem;
  }

  .ReflexSearch-emptyIcon {
    align-items: center;
    background: var(--primary-3, #f3f0ff);
    border-radius: 999px;
    color: var(--primary-9, #6e56cf);
    display: flex;
    height: 2.75rem;
    justify-content: center;
    width: 2.75rem;
  }

  .ReflexSearch-hitList {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .ReflexSearch-hit {
    align-items: center;
    border-radius: 0.625rem;
    color: inherit;
    display: flex;
    gap: 0.75rem;
    padding: 0.75rem;
    text-decoration: none;
  }

  .ReflexSearch-hit:hover {
    background: var(--primary-3, #f3f0ff);
  }

  .ReflexSearch-hitIcon {
    align-items: center;
    background: var(--secondary-3, #f0f0f0);
    border: 1px solid var(--secondary-5, #e8e8e8);
    border-radius: 0.5rem;
    color: var(--secondary-10, #7b7b7b);
    display: flex;
    flex: 0 0 auto;
    height: 2.25rem;
    justify-content: center;
    width: 2.25rem;
  }

  .ReflexSearch-hitContent {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  .ReflexSearch-hitMeta {
    color: var(--primary-10, #644fc1);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    line-height: 1rem;
    text-transform: uppercase;
  }

  .ReflexSearch-hitContent strong {
    font-size: 0.9375rem;
    line-height: 1.25rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ReflexSearch-hitDescription {
    color: var(--secondary-10, #7b7b7b);
    display: -webkit-box;
    font-size: 0.8125rem;
    line-height: 1.125rem;
    margin-top: 0.125rem;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 1;
  }

  .ReflexSearch-hit mark {
    background: transparent;
    color: var(--primary-10, #644fc1);
    font-weight: 700;
  }

  .ReflexSearch-hitArrow {
    color: var(--secondary-8, #aaa);
    font-size: 0.875rem;
  }

  .ReflexSearch-footer {
    align-items: center;
    border-top: 1px solid var(--secondary-5, #e8e8e8);
    color: var(--secondary-9, #8a8a8a);
    display: flex;
    font-size: 0.6875rem;
    justify-content: space-between;
    min-height: 2.75rem;
    padding: 0 1rem;
  }

  .ReflexSearch-footer a {
    color: var(--secondary-10, #7b7b7b);
    text-decoration: none;
  }

  .ReflexSearch-spinner {
    animation: ReflexSearch-spin 700ms linear infinite;
    color: var(--primary-9, #6e56cf);
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

  @keyframes ReflexSearch-spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (max-width: 80em) {
    .ReflexSearch-button {
      height: 2rem;
      justify-content: center;
      padding: 0;
      width: 2rem;
    }

    .ReflexSearch-buttonText,
    .ReflexSearch-shortcut {
      display: none;
    }
  }

  @media (max-width: 40rem) {
    .ReflexSearch-overlay {
      align-items: stretch;
      padding: 0;
    }

    .ReflexSearch-dialog {
      border: 0;
      border-radius: 0;
      height: 100dvh;
      max-height: none;
      width: 100%;
    }

    .ReflexSearch-results {
      flex: 1;
    }

    .ReflexSearch-escape {
      font-size: 0;
      padding: 0;
      width: 1.75rem;
    }

    .ReflexSearch-escape::after {
      content: "×";
      font-size: 1.125rem;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .ReflexSearch-button {
      transition: none;
    }

    .ReflexSearch-spinner {
      animation-duration: 1400ms;
    }
  }
`;

export default AlgoliaSearch;
