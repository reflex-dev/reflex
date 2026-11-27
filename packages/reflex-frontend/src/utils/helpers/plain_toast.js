// A plain notice with the call signature of the toaster's `toast`, for a build
// that leaves the toaster out. The compiler leaves it out when it finds no use
// of `rx.toast`, which it cannot rule out for code that runs on the backend, so
// a toast sent anyway, or a connection error, is shown here rather than lost.
//
// Plain DOM rather than a React component: there is no provider to render it.

const ACCENTS = {
  info: "#0090ff",
  success: "#30a46c",
  warning: "#ffc53d",
  error: "#e5484d",
};
const DEFAULT_DURATION = 4000;

// The notices on the page by id, with what removes each.
const notices = new Map();
let lastId = 0;
let warned = false;

/**
 * Get the element stacking the notices of one position, creating it if needed.
 * @param {string} position A toaster position, e.g. "bottom-right".
 * @returns {HTMLElement} The element.
 */
const stackAt = (position) => {
  const id = `reflex-plain-toasts-${position}`;
  let stack = document.getElementById(id);
  if (!stack) {
    const [vertical, horizontal] = position.split("-");
    stack = document.createElement("div");
    stack.id = id;
    stack.style.cssText =
      "position:fixed;z-index:2147483647;display:flex;flex-direction:column;" +
      `gap:0.5rem;padding:1rem;max-width:min(24rem,100vw);${vertical}:0;` +
      (horizontal === "center"
        ? "left:50%;transform:translateX(-50%);"
        : `${horizontal}:0;`);
    document.body.append(stack);
  }
  return stack;
};

/**
 * Remove a notice from the page.
 * @param {string|number} [id] The id of the notice, or nothing for all of them.
 */
const dismiss = (id) => {
  for (const key of id === undefined ? [...notices.keys()] : [id]) {
    notices.get(key)?.();
  }
};

/**
 * Add a button to a notice.
 * @param {HTMLElement} notice The notice.
 * @param {string} label The text of the button.
 * @param {(event: MouseEvent) => void} onClick What the button does.
 */
const addButton = (notice, label, onClick) => {
  const button = document.createElement("button");
  button.textContent = label;
  button.style.cssText =
    "margin:0.5rem 0.5rem 0 0;padding:0.125rem 0.5rem;border:1px solid;" +
    "border-radius:4px;background:transparent;color:inherit;font:inherit;" +
    "cursor:pointer;";
  button.onclick = onClick;
  notice.append(button);
};

/**
 * Build the function showing notices of one level.
 * @param {string} [level] The toast level, or nothing for a plain toast.
 * @returns {(message?: string, options?: Record<string, any>) => string|number} The function, which returns the id of the notice.
 */
const show =
  (level) =>
  (message, options = {}) => {
    if (!warned) {
      warned = true;
      console.warn(
        "The toaster is not part of this build, because no use of rx.toast " +
          "was found when the app was compiled, so a plain notice is shown " +
          "instead. Pass toaster=rx.toast.provider() to rx.App to include it.",
      );
    }
    const id = options.id ?? ++lastId;
    // A notice with the id of one on the page takes its place.
    notices.get(id)?.();

    const notice = document.createElement("div");
    notice.setAttribute("role", level === "error" ? "alert" : "status");
    notice.style.cssText =
      "padding:0.75rem 1rem;border:1px solid;border-radius:8px;" +
      `border-left:4px solid ${ACCENTS[level] ?? "currentColor"};` +
      "background:Canvas;color:CanvasText;font:0.875rem system-ui,sans-serif;" +
      "white-space:pre-wrap;box-shadow:0 4px 12px rgba(0,0,0,0.1);";
    const title = document.createElement("div");
    title.style.fontWeight = "600";
    title.append(options.title ?? message ?? "");
    notice.append(title);
    if (options.description) {
      const description = document.createElement("div");
      description.append(options.description);
      notice.append(description);
    }

    const seen = { id, title: title.textContent };
    let timer;
    const remove = () => {
      clearTimeout(timer);
      notices.delete(id);
      notice.remove();
    };
    notices.set(id, remove);
    const close = () => {
      remove();
      options.onDismiss?.(seen);
    };
    for (const button of [options.action, options.cancel]) {
      if (button?.label) {
        addButton(notice, button.label, (event) => {
          button.onClick?.(event);
          if (!event.defaultPrevented) close();
        });
      }
    }
    if (options.closeButton) {
      addButton(notice, "×", close);
    }

    const duration = options.duration ?? DEFAULT_DURATION;
    if (level !== "loading" && Number.isFinite(duration)) {
      timer = setTimeout(() => {
        remove();
        options.onAutoClose?.(seen);
      }, duration);
    }
    stackAt(options.position ?? "bottom-right").append(notice);
    return id;
  };

export default Object.assign(show(), {
  info: show("info"),
  success: show("success"),
  warning: show("warning"),
  error: show("error"),
  loading: show("loading"),
  dismiss,
});
