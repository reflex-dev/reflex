// The reference page: the stylesheet of @radix-ui/themes and its `Theme`
// component, which decides the attributes the stylesheet selects on.

import "@radix-ui/themes/styles.css";

import { Theme } from "@radix-ui/themes";
import { createElement } from "react";
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";

import { install } from "./page.js";

const root = createRoot(
  /** @type {Element} */ (document.getElementById("root")),
);

install(({ theme, nested }) => {
  const target = createElement("div", { id: "target" });
  flushSync(() =>
    root.render(
      createElement(
        Theme,
        // A root `Theme` copies its props into state after it has painted. A
        // new one for each theme starts from the props it is given.
        /** @type {import("@radix-ui/themes").ThemeProps} */ ({
          key: JSON.stringify(theme),
          ...theme,
        }),
        nested
          ? createElement(
              Theme,
              /** @type {import("@radix-ui/themes").ThemeProps} */ (nested),
              target,
            )
          : target,
      ),
    ),
  );
  return /** @type {Element} */ (
    document.querySelector(".radix-themes:has(> #target)")
  );
});
