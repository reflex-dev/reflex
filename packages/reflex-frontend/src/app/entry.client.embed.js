import { startTransition, createElement } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";
import env from "$/env.json";

const selector = env.MOUNT_TARGET;

if (selector) {
  const target = document.querySelector(selector);
  if (!target) {
    console.error(
      `[Reflex embed] No element matching MOUNT_TARGET selector ${JSON.stringify(selector)}; widget will not mount.`,
    );
  } else {
    // @react-router/dev injects a preamble check at the top of every
    // transformed JSX module that throws when this flag is unset. Framework-
    // mode prerendered HTML installs it via <Scripts>; embed mode does not,
    // so we install it before any user JSX module loads (the imports below
    // are dynamic).
    window.__vite_plugin_react_preamble_installed__ = true;
    window.$RefreshReg$ = () => {};
    window.$RefreshSig$ = () => (type) => type;

    // No __reactRouterContext on the host page; mount through a memory data
    // router so the widget owns its URL space (host's window.location is
    // unrelated) and react-router hooks like useLoaderData resolve. The route
    // table is generated at compile time into __reflex_embed_manifest.js.
    Promise.all([
      import("$/styles/__reflex_global_styles.css"),
      import("react-router"),
      import("$/app/root"),
      import("$/app/__reflex_embed_manifest"),
    ])
      .then(([, reactRouter, root, manifest]) => {
        const { createMemoryRouter, RouterProvider, Outlet } = reactRouter;
        const children = manifest.default.map(({ path, load }) => {
          const lazy = async () => ({ Component: (await load()).default });
          if (path === "") return { index: true, lazy };
          return { path, lazy };
        });
        const router = createMemoryRouter(
          [
            {
              Component: () =>
                createElement(root.EmbedLayout, null, createElement(Outlet)),
              children,
            },
          ],
          { initialEntries: ["/"] },
        );
        startTransition(() => {
          createRoot(target).render(createElement(RouterProvider, { router }));
        });
      })
      .catch((err) => {
        console.error("[Reflex embed] Failed to load:", err);
      });
  }
} else {
  startTransition(() => {
    hydrateRoot(document, createElement(HydratedRouter));
  });
}
