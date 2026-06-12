/* Reflex frontend inspector — dev-only browser script.
 *
 * Reads `data-rx` from rendered elements, looks them up in the source map
 * served at /__reflex/source-map.json, draws a hover outline + label, and
 * sends clicks to /__open-in-editor so the user's editor can jump to the
 * Python call site.
 *
 * Loaded by the inspector Vite plugin (or Astro integration). The plugin
 * also installs the editor middleware on the dev server.
 */

const RX_DATA_ATTR = "data-rx";
const SESSION_KEY = "__reflex_inspector_persistent";
const OUTLINE_ID = "__reflex_inspector_outline";
const LABEL_ID = "__reflex_inspector_label";
const TOGGLE_ID = "__reflex_inspector_toggle";

const config = window.__REFLEX_INSPECTOR_CONFIG__ || {};
const SOURCE_MAP_URL = config.sourceMapUrl || "/__reflex/source-map.json";
const CSS_URL = config.cssUrl || "/__reflex/inspector.css";
const EDITOR_URL = config.editorUrl || "/__open-in-editor";
const shortcut = config.shortcut || {
  key: "x",
  alt: true,
  ctrl: false,
  meta: false,
  shift: false,
};

let sourceMap = null;
let sourceMapPromise = null;
let persistent = false;
let modifierHeld = false;
let lastTarget = null;
let outlineEl = null;
let labelEl = null;
let toggleEl = null;
let focusGuardUntil = 0;
let sourceMapRequestId = 0;

const clearSourceMap = () => {
  sourceMap = null;
  sourceMapPromise = null;
  sourceMapRequestId += 1;
};

const loadSourceMap = (fresh = false) => {
  if (fresh) clearSourceMap();
  if (sourceMap) return Promise.resolve(sourceMap);
  if (sourceMapPromise) return sourceMapPromise;
  const requestId = sourceMapRequestId;
  sourceMapPromise = fetch(SOURCE_MAP_URL, { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : {}))
    .catch(() => ({}))
    .then((map) => {
      if (requestId === sourceMapRequestId) sourceMap = map;
      return map;
    })
    .finally(() => {
      if (requestId === sourceMapRequestId) sourceMapPromise = null;
    });
  return sourceMapPromise;
};

const ensureStylesheet = () => {
  const existing = document.getElementById("__reflex_inspector_css");
  if (existing) return;
  const link = document.createElement("link");
  link.id = "__reflex_inspector_css";
  link.rel = "stylesheet";
  link.href = CSS_URL;
  document.head.appendChild(link);
};

const ensureOverlayElements = () => {
  ensureStylesheet();
  if (!outlineEl) {
    outlineEl = document.createElement("div");
    outlineEl.id = OUTLINE_ID;
    document.body.appendChild(outlineEl);
  }
  if (!labelEl) {
    labelEl = document.createElement("div");
    labelEl.id = LABEL_ID;
    document.body.appendChild(labelEl);
  }
  if (!toggleEl) {
    toggleEl = document.createElement("button");
    toggleEl.id = TOGGLE_ID;
    toggleEl.type = "button";
    toggleEl.textContent = "rx-inspect";
    toggleEl.addEventListener("click", () => setPersistent(!persistent));
    document.body.appendChild(toggleEl);
  }
};

const findInspected = (node) => {
  while (node && node.nodeType === 1) {
    if (node.hasAttribute(RX_DATA_ATTR)) return node;
    node = node.parentElement;
  }
  return null;
};

const ancestorChain = (el, depth) => {
  const chain = [];
  let cur = el.parentElement;
  while (cur && chain.length < depth) {
    if (cur.hasAttribute(RX_DATA_ATTR)) {
      const id = cur.getAttribute(RX_DATA_ATTR);
      const info = sourceMap && sourceMap[id];
      if (info && info.component) chain.push(info.component);
    }
    cur = cur.parentElement;
  }
  return chain.reverse();
};

const baseName = (file) => {
  if (!file) return "";
  const i = Math.max(file.lastIndexOf("/"), file.lastIndexOf("\\"));
  return i === -1 ? file : file.slice(i + 1);
};

const showOverlayFor = (el) => {
  if (!el || !sourceMap) return;
  const id = el.getAttribute(RX_DATA_ATTR);
  const info = sourceMap[id];
  if (!info) {
    hideOverlay();
    return;
  }
  ensureOverlayElements();
  const rect = el.getBoundingClientRect();
  outlineEl.style.display = "block";
  outlineEl.style.top = `${rect.top}px`;
  outlineEl.style.left = `${rect.left}px`;
  outlineEl.style.width = `${rect.width}px`;
  outlineEl.style.height = `${rect.height}px`;

  const chain = ancestorChain(el, 3);
  const breadcrumb = chain.length > 0 ? chain.join(" › ") + " › " : "";
  const file = baseName(info.file);
  labelEl.innerHTML = "";
  if (breadcrumb) {
    const span = document.createElement("span");
    span.className = "__reflex_inspector_chain";
    span.textContent = breadcrumb;
    labelEl.appendChild(span);
  }
  const name = document.createElement("span");
  name.textContent = `${info.component} `;
  labelEl.appendChild(name);
  const fileSpan = document.createElement("span");
  fileSpan.className = "__reflex_inspector_file";
  fileSpan.textContent = `${file}:${info.line}`;
  labelEl.appendChild(fileSpan);

  labelEl.style.display = "block";
  const labelTop = Math.max(0, rect.top - 24);
  labelEl.style.top = `${labelTop}px`;
  labelEl.style.left = `${rect.left}px`;
};

const hideOverlay = () => {
  if (outlineEl) outlineEl.style.display = "none";
  if (labelEl) labelEl.style.display = "none";
};

const openInEditor = async (info) => {
  if (!info) return;
  const params = new URLSearchParams({
    file: `${info.file}:${info.line}:${info.column || 1}`,
  });
  try {
    await fetch(`${EDITOR_URL}?${params.toString()}`, { method: "GET" });
  } catch (err) {
    console.warn("[reflex-inspector] open-in-editor failed", err);
  }
};

const copyPath = (info) => {
  if (!info || !navigator.clipboard) return;
  const text = `${info.file}:${info.line}:${info.column || 1}`;
  navigator.clipboard.writeText(text).catch(() => undefined);
};

const expectedCode = (key) => {
  // Layout-independent code for the configured shortcut key, used as a
  // primary match: holding Alt on macOS/Linux can mutate event.key into
  // dead/compose characters (e.g. Option+X → "≈"), which would otherwise
  // make the second press silently miss.
  if (key.length !== 1) return null;
  if (key >= "a" && key <= "z") return `Key${key.toUpperCase()}`;
  if (key >= "0" && key <= "9") return `Digit${key}`;
  return null;
};

const matchesShortcut = (event) => {
  if (event.repeat) return false;
  const code = expectedCode(shortcut.key);
  const keyMatch = event.key.toLowerCase() === shortcut.key;
  const codeMatch = code !== null && event.code === code;
  if (!keyMatch && !codeMatch) return false;
  return (
    !!event.altKey === !!shortcut.alt &&
    !!event.ctrlKey === !!shortcut.ctrl &&
    !!event.metaKey === !!shortcut.meta &&
    !!event.shiftKey === !!shortcut.shift
  );
};

const hasConfiguredModifier =
  !!shortcut.alt || !!shortcut.ctrl || !!shortcut.meta || !!shortcut.shift;

const requiredModifiersHeld = (event) =>
  hasConfiguredModifier &&
  (!shortcut.alt || event.altKey) &&
  (!shortcut.ctrl || event.ctrlKey) &&
  (!shortcut.meta || event.metaKey) &&
  (!shortcut.shift || event.shiftKey);

const isActive = () => persistent || modifierHeld;

const updateToggle = () => {
  if (!toggleEl) return;
  toggleEl.dataset.active = String(persistent);
};

const setPersistent = async (on) => {
  const wasPersistent = persistent;
  persistent = !!on;
  try {
    sessionStorage.setItem(SESSION_KEY, persistent ? "1" : "0");
  } catch (_) {
    // sessionStorage may be disabled — ignore.
  }
  if (persistent) await loadSourceMap(!wasPersistent);
  updateToggle();
  if (!isActive()) hideOverlay();
};

const onMouseMove = (event) => {
  if (!isActive()) return;
  if (Date.now() < focusGuardUntil) return;
  if (isInspectorChrome(event.target)) {
    hideOverlay();
    lastTarget = null;
    return;
  }
  const target = findInspected(event.target);
  lastTarget = target;
  if (target) showOverlayFor(target);
  else hideOverlay();
};

const isInspectorChrome = (node) => {
  while (node && node.nodeType === 1) {
    if (
      node.id === TOGGLE_ID ||
      node.id === OUTLINE_ID ||
      node.id === LABEL_ID
    ) {
      return true;
    }
    node = node.parentElement;
  }
  return false;
};

const onClick = async (event) => {
  if (!isActive()) return;
  if (isInspectorChrome(event.target)) return;
  // Require the configured modifier at click time so re-focusing the
  // window or clicking through the page doesn't hijack normal clicks.
  if (!requiredModifiersHeld(event)) return;
  // Swallow the very first click after the window regains focus — the
  // browser fires it as part of the focus transition and the user almost
  // never means it as an inspector action.
  if (Date.now() < focusGuardUntil) {
    focusGuardUntil = 0;
    return;
  }
  const target = findInspected(event.target);
  if (!target) return;
  event.preventDefault();
  event.stopPropagation();
  const map = await loadSourceMap(true);
  const info = map && map[target.getAttribute(RX_DATA_ATTR)];
  openInEditor(info);
};

const onKeyDown = (event) => {
  if (matchesShortcut(event)) {
    event.stopPropagation();
    event.preventDefault();
    setPersistent(!persistent);
    return;
  }
  if (requiredModifiersHeld(event) && !modifierHeld) {
    modifierHeld = true;
    loadSourceMap(true);
  }
  if (event.key === "Escape" && persistent) {
    setPersistent(false);
  }
  if (event.key.toLowerCase() === "c" && lastTarget && isActive()) {
    const info = sourceMap && sourceMap[lastTarget.getAttribute(RX_DATA_ATTR)];
    copyPath(info);
  }
};

const onKeyUp = (event) => {
  if (!requiredModifiersHeld(event) && modifierHeld) {
    modifierHeld = false;
    if (!persistent) hideOverlay();
  }
};

const installEvents = () => {
  document.addEventListener("mousemove", onMouseMove, true);
  document.addEventListener("click", onClick, true);
  document.addEventListener("keydown", onKeyDown, true);
  document.addEventListener("keyup", onKeyUp, true);
  window.addEventListener("blur", () => {
    modifierHeld = false;
    hideOverlay();
  });
  window.addEventListener("focus", () => {
    focusGuardUntil = Date.now() + 350;
  });
};

const init = () => {
  if (window.__REFLEX_INSPECTOR__) return;
  ensureOverlayElements();
  installEvents();

  let initial = false;
  try {
    initial = sessionStorage.getItem(SESSION_KEY) === "1";
  } catch (_) {
    initial = false;
  }
  if (window.location.search.includes("reflex-inspector")) initial = true;

  window.__REFLEX_INSPECTOR__ = {
    enable: () => setPersistent(true),
    disable: () => setPersistent(false),
    toggle: () => setPersistent(!persistent),
    isEnabled: () => persistent,
    sourceCount: () => (sourceMap ? Object.keys(sourceMap).length : 0),
  };

  if (initial) setPersistent(true);
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init, { once: true });
} else {
  init();
}
