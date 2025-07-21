import { startTransition } from "react";
import { hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";
import { createElement } from "react";
import { defaultColorMode } from "$/utils/context";

// Pre-hydration theme script - runs before React hydrates
(function () {
  try {
    const theme = localStorage.getItem("theme") || defaultColorMode || "light";
    const systemPreference = window.matchMedia("(prefers-color-scheme: dark)")
      .matches
      ? "dark"
      : "light";
    const resolvedTheme = theme === "system" ? systemPreference : theme;
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(resolvedTheme);
    root.style.colorScheme = resolvedTheme;
  } catch (e) {
    document.documentElement.classList.add(defaultColorMode || "light");
  }
})();

startTransition(() => {
  hydrateRoot(document, createElement(HydratedRouter));
});
