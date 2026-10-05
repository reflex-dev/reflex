// Installed by reflex-bench as an init script: it runs before any page script in
// every document of a benchmark's browser context, reloaded ones included.
// Marks record when the page itself saw a condition hold, on two clocks:
// performance.now() (since navigation start) and Date.now() (the epoch, which
// the harness maps onto its own clock), with the document's __BENCH_ALIVE tag
// (null in a reloaded document, which lost it).
(() => {
  if (window.__bench) return;
  // Watches armed with persist survive a reload in sessionStorage and are
  // re-armed in the next document, so a hot reload that turns into a full
  // reload still gets its mark; their marks are kept there too, so a document
  // reloaded right after one recorded a mark still reports it.
  const PENDING = "__bench_pending";
  const MARKS = "__bench_marks";
  const read = (key) => {
    try {
      return JSON.parse(sessionStorage.getItem(key) || "{}");
    } catch {
      return {};
    }
  };
  const write = (key, value) => {
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch {}
  };
  const update = (key, change) => {
    const value = read(key);
    change(value);
    write(key, value);
  };
  const observed = { childList: true, subtree: true, characterData: true };
  // The observer and animation frame of each armed watch, to stop it.
  const active = {};
  const stop = (id) => {
    active[id]?.observer?.disconnect();
    cancelAnimationFrame(active[id]?.frame ?? 0);
    delete active[id];
  };
  const bench = {
    marks: read(MARKS),
    paints: {},
    lcp: null,
    longtasks: [],
    loafs: [],
    // performance.now() of the last DOM mutation.
    activity: 0,
    // What a watch compares: the element's text, a computed style property
    // ("style:<prop>") or a loaded image's natural width; null without the
    // element (or the image).
    value(kind, selector) {
      const el = document.querySelector(selector);
      if (el === null) return null;
      if (kind === "text" || kind === "changed") return el.textContent;
      if (kind === "naturalWidth") {
        return el.complete && el.naturalWidth ? String(el.naturalWidth) : null;
      }
      if (kind.startsWith("style:")) {
        return getComputedStyle(el).getPropertyValue(kind.slice(6));
      }
      throw new Error(`unknown watch kind ${kind}`);
    },
    holds(kind, selector, expected) {
      if (kind === "present") return document.querySelector(selector) !== null;
      const value = bench.value(kind, selector);
      if (value === null) return false;
      return kind === "changed" ? value !== expected : value === expected;
    },
    // Record marks[id] the first time the condition holds: checked on every
    // DOM mutation and every animation frame (a computed style or an image
    // loading is no mutation). "present" works for an element that does not
    // exist yet and is empty. Arming an id again replaces its watch.
    watch(id, kind, selector, expected, persist = true) {
      stop(id);
      delete bench.marks[id];
      if (persist) {
        update(PENDING, (pending) => {
          pending[id] = [kind, selector, expected];
        });
        update(MARKS, (marks) => {
          delete marks[id];
        });
      }
      const check = () => {
        if (!bench.holds(kind, selector, expected)) return false;
        const mark = {
          perf: performance.now(),
          epoch: Date.now(),
          alive: window.__BENCH_ALIVE ?? null,
        };
        bench.marks[id] = mark;
        if (persist) {
          update(MARKS, (marks) => {
            marks[id] = mark;
          });
        }
        bench.unwatch(id);
        return true;
      };
      if (check()) return;
      const watching = (active[id] = {
        observer: new MutationObserver(check),
        frame: 0,
      });
      watching.observer.observe(document, observed);
      const poll = () => {
        if (!check()) watching.frame = requestAnimationFrame(poll);
      };
      watching.frame = requestAnimationFrame(poll);
    },
    // Stop a watch and forget it (its mark, if recorded, stays).
    unwatch(id) {
      stop(id);
      update(PENDING, (pending) => {
        delete pending[id];
      });
    },
    pending() {
      return Object.keys(read(PENDING));
    },
    quiet(ms) {
      return performance.now() - bench.activity >= ms;
    },
  };
  window.__bench = bench;
  new MutationObserver(() => {
    bench.activity = performance.now();
  }).observe(document, { ...observed, attributes: true });
  const supported = PerformanceObserver.supportedEntryTypes || [];
  const observe = (type, handle) => {
    if (supported.includes(type)) {
      new PerformanceObserver((list) =>
        list.getEntries().forEach(handle),
      ).observe({ type, buffered: true });
    }
  };
  observe("paint", (entry) => {
    bench.paints[entry.name] = entry.startTime;
  });
  observe("largest-contentful-paint", (entry) => {
    bench.lcp = entry.startTime;
  });
  observe("longtask", (entry) => {
    bench.longtasks.push({ start: entry.startTime, duration: entry.duration });
  });
  observe("long-animation-frame", (entry) => {
    bench.loafs.push({ start: entry.startTime, duration: entry.duration });
  });
  // The playground renders #bench-hydrated once the websocket is connected and
  // the first state update applied: tier 3 of every document.
  bench.watch("hydrated", "present", "#bench-hydrated", null, false);
  for (const [id, [kind, selector, expected]] of Object.entries(
    read(PENDING),
  )) {
    bench.watch(id, kind, selector, expected);
  }
})();
