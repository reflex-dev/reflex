"""Runtime tests for the browser-side inspector script."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap

import pytest
from reflex_base.plugins.frontend_inspector import _asset_source_dir


def _run_inspector_harness(scenario: str):
    """Run an inspector browser-script scenario in Node.

    Args:
        scenario: JavaScript body to run after the fake browser environment loads.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for inspector browser runtime tests")

    inspector_path = _asset_source_dir() / "inspector.js"
    script = f"""
const fs = require("fs");
const vm = require("vm");

const inspectorSource = fs.readFileSync({json.dumps(str(inspector_path))}, "utf8");

class Element {{
  constructor(tagName) {{
    this.tagName = tagName.toUpperCase();
    this.nodeType = 1;
    this.id = "";
    this.type = "";
    this.rel = "";
    this.href = "";
    this.textContent = "";
    this.innerHTML = "";
    this.className = "";
    this.parentElement = null;
    this.children = [];
    this.style = {{}};
    this.dataset = {{}};
    this.attributes = new Map();
    this.listeners = new Map();
  }}

  appendChild(child) {{
    child.parentElement = this;
    this.children.push(child);
    return child;
  }}

  addEventListener(type, listener) {{
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }}

  hasAttribute(name) {{
    return this.attributes.has(name);
  }}

  getAttribute(name) {{
    return this.attributes.get(name) || null;
  }}

  setAttribute(name, value) {{
    this.attributes.set(name, String(value));
  }}

  getBoundingClientRect() {{
    return {{ top: 12, left: 34, width: 56, height: 78 }};
  }}
}}

const walk = (node, callback) => {{
  if (callback(node)) return node;
  for (const child of node.children) {{
    const found = walk(child, callback);
    if (found) return found;
  }}
  return null;
}};

const makeEvent = (overrides) => {{
  const event = {{
    target: null,
    key: "",
    code: "",
    repeat: false,
    altKey: false,
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
    defaultPrevented: false,
    propagationStopped: false,
    preventDefault() {{
      this.defaultPrevented = true;
    }},
    stopPropagation() {{
      this.propagationStopped = true;
    }},
  }};
  return Object.assign(event, overrides);
}};

const createHarness = (config, maps) => {{
  const documentListeners = new Map();
  const windowListeners = new Map();
  const sourceMapFetches = [];
  const editorFetches = [];
  const head = new Element("head");
  const body = new Element("body");

  const document = {{
    readyState: "complete",
    head,
    body,
    createElement(tagName) {{
      return new Element(tagName);
    }},
    getElementById(id) {{
      return (
        walk(head, (node) => node.id === id) ||
        walk(body, (node) => node.id === id)
      );
    }},
    addEventListener(type, listener) {{
      const listeners = documentListeners.get(type) || [];
      listeners.push(listener);
      documentListeners.set(type, listeners);
    }},
  }};

  const session = new Map();
  const sessionStorage = {{
    getItem(key) {{
      return session.has(key) ? session.get(key) : null;
    }},
    setItem(key, value) {{
      session.set(key, String(value));
    }},
  }};

  const window = {{
    __REFLEX_INSPECTOR_CONFIG__: config,
    location: {{ search: "" }},
    addEventListener(type, listener) {{
      const listeners = windowListeners.get(type) || [];
      listeners.push(listener);
      windowListeners.set(type, listeners);
    }},
  }};

  let mapIndex = 0;
  const fetch = async (url, options) => {{
    const textUrl = String(url);
    if (textUrl.startsWith(config.editorUrl)) {{
      editorFetches.push({{ url: textUrl, options }});
      return {{ ok: true, json: async () => ({{}}) }};
    }}
    sourceMapFetches.push({{ url: textUrl, options }});
    const map = maps[Math.min(mapIndex, maps.length - 1)] || {{}};
    mapIndex += 1;
    return {{ ok: true, json: async () => map }};
  }};

  const context = vm.createContext({{
    console,
    Date,
    document,
    fetch,
    navigator: {{ clipboard: {{ writeText: async () => undefined }} }},
    sessionStorage,
    URLSearchParams,
    window,
  }});
  vm.runInContext(inspectorSource, context);

  return {{
    body,
    document,
    editorFetches,
    makeEvent,
    sourceMapFetches,
    window,
    dispatchDocument(type, event) {{
      for (const listener of documentListeners.get(type) || []) {{
        listener(event);
      }}
      return event;
    }},
  }};
}};

const assert = (condition, message) => {{
  if (!condition) throw new Error(message);
}};

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

(async () => {{
{textwrap.indent(scenario, "  ")}
}})().catch((error) => {{
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
}});
"""
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_browser_script_uses_configured_modifier_for_hover_and_click():
    """Hover/click inspection uses the configured shortcut modifier."""
    _run_inspector_harness("""
const harness = createHarness(
  {
    sourceMapUrl: "/__reflex/source-map.json",
    cssUrl: "/__reflex/inspector.css",
    editorUrl: "/__open-in-editor",
    shortcut: { key: "x", alt: false, ctrl: true, meta: false, shift: false },
  },
  [{ "1": { component: "Button", file: "/app/page.py", line: 7, column: 3 } }]
);

const target = harness.document.createElement("button");
target.setAttribute("data-rx", "1");
harness.body.appendChild(target);

harness.dispatchDocument(
  "keydown",
  harness.makeEvent({ key: "Control", code: "ControlLeft", ctrlKey: true })
);
await flush();

harness.dispatchDocument(
  "mousemove",
  harness.makeEvent({ target, ctrlKey: true })
);
const label = harness.document.getElementById("__reflex_inspector_label");
assert(label.style.display === "block", "Ctrl hover did not show the overlay");

const clickEvent = harness.dispatchDocument(
  "click",
  harness.makeEvent({ target, ctrlKey: true })
);
await flush();
assert(clickEvent.defaultPrevented, "Ctrl click did not become an inspector action");
const openedUrl = harness.editorFetches[0] ? harness.editorFetches[0].url : "";
assert(
  harness.editorFetches.length === 1 &&
    decodeURIComponent(openedUrl).includes("/app/page.py:7:3"),
  "Ctrl click did not open the configured source location"
);

harness.dispatchDocument(
  "keyup",
  harness.makeEvent({ key: "Control", code: "ControlLeft" })
);
assert(label.style.display === "none", "Ctrl release did not hide the overlay");
""")


def test_browser_script_refetches_source_map_on_reactivation():
    """Re-enabling the persistent inspector fetches a fresh source map."""
    _run_inspector_harness("""
const harness = createHarness(
  {
    sourceMapUrl: "/__reflex/source-map.json",
    cssUrl: "/__reflex/inspector.css",
    editorUrl: "/__open-in-editor",
    shortcut: { key: "x", alt: true, ctrl: false, meta: false, shift: false },
  },
  [
    { "1": { component: "Box", file: "/app/old.py", line: 1, column: 1 } },
    {
      "1": { component: "Box", file: "/app/new.py", line: 2, column: 1 },
      "2": { component: "Text", file: "/app/new.py", line: 3, column: 1 },
    },
  ]
);

await harness.window.__REFLEX_INSPECTOR__.enable();
assert(harness.window.__REFLEX_INSPECTOR__.sourceCount() === 1, "first map not loaded");
await harness.window.__REFLEX_INSPECTOR__.disable();
await harness.window.__REFLEX_INSPECTOR__.enable();

assert(harness.sourceMapFetches.length === 2, "source map was not re-fetched");
assert(
  harness.window.__REFLEX_INSPECTOR__.sourceCount() === 2,
  "reactivation kept the stale source map"
);
""")
