import { fileURLToPath, URL } from "url";
import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";
import safariCacheBustPlugin from "./vite-plugin-safari-cachebust.js";

// Ensure that bun always uses the react-dom/server.node functions.
function alwaysUseReactDomServerNode() {
  return {
    name: "vite-plugin-always-use-react-dom-server-node",
    enforce: "pre",

    resolveId: {
      filter: { id: /react-dom\/server/ },
      handler(source, importer) {
        if (
          typeof importer === "string" &&
          importer.endsWith("/entry.server.node.tsx")
        ) {
          return this.resolve("react-dom/server.node", importer, {
            skipSelf: true,
          });
        }
        return null;
      },
    },
  };
}


import path from "path";
import { createRequire } from "module";

function prodReactPrebundle() {
  // Resolve each package the way Node does from where it is actually used,
  // so a nested install (e.g. react-dom/node_modules/scheduler) still works.
  const packageRoot = (name, from) =>
    path.dirname(createRequire(from).resolve(name + "/package.json"));
  const reactRoot = packageRoot("react", import.meta.url);
  const reactDomRoot = packageRoot("react-dom", import.meta.url);
  const schedulerRoot = packageRoot("scheduler", path.join(reactDomRoot, "package.json"));
  const production = {
    react: path.join(reactRoot, "cjs/react.production.js"),
    "react/jsx-runtime": path.join(reactRoot, "cjs/react-jsx-runtime.production.js"),
    "react/jsx-dev-runtime": path.join(reactRoot, "cjs/react-jsx-dev-runtime.production.js"),
    "react-dom": path.join(reactDomRoot, "cjs/react-dom.production.js"),
    "react-dom/client": path.join(reactDomRoot, "cjs/react-dom-client.production.js"),
    scheduler: path.join(schedulerRoot, "cjs/scheduler.production.js"),
  };
  // Optimizer entries arrive as the packages' resolved entry files (with the
  // platform's separators, hence the normalization).
  const key = (file) => {
    const normalized = path.normalize(file);
    return process.platform === "win32" ? normalized.toLowerCase() : normalized;
  };
  const entryFiles = Object.fromEntries(
    Object.entries({
      react: path.join(reactRoot, "index.js"),
      "react/jsx-runtime": path.join(reactRoot, "jsx-runtime.js"),
      "react/jsx-dev-runtime": path.join(reactRoot, "jsx-dev-runtime.js"),
      "react-dom": path.join(reactDomRoot, "index.js"),
      "react-dom/client": path.join(reactDomRoot, "client.js"),
      scheduler: path.join(schedulerRoot, "index.js"),
    }).map(([bare, file]) => [key(file), bare]),
  );
  return {
    name: "reflex-prod-react-prebundle",
    resolveId(id) {
      if (id in production) return production[id];
      const bare = entryFiles[key(id)];
      return bare ? production[bare] : null;
    },
  };
}

function fullReload() {
  return {
    name: "full-reload",
    enforce: "pre",
    handleHotUpdate({ server }) {
      server.ws.send({
        type: "full-reload",
      });
      return [];
    }
  };
}

// React Router queues manifest updates for lazy routes even when their modules
// are not loaded. Its HMR runtime throws on those entries before clearing the
// queue, which blocks every later update until the browser is reloaded.
function patchReactRouterHmrRuntime() {
  const unloadedRouteThrow = /if\s*\(!imported\)\s*\{\s*throw\s+Error\(\s*`\[react-router:hmr\] No module update found for route [^`]+`,\s*\);\s*\}/;
  return {
    name: "reflex-patch-react-router-hmr-runtime",
    apply: "serve",
    enforce: "post",
    transform(code, id) {
      if (id !== "\0virtual:react-router/hmr-runtime") return;
      if (!unloadedRouteThrow.test(code)) {
        this.warn(
          "react-router hmr runtime changed; unloaded-route HMR patch skipped",
        );
        return;
      }
      return {
        code: code.replace(unloadedRouteThrow, "if (!imported) continue;"),
        map: null,
      };
    },
  };
}

export default defineConfig((config) => ({
  base: "/",
  plugins: [
    alwaysUseReactDomServerNode(),
    reactRouter(),
    patchReactRouterHmrRuntime(),
    safariCacheBustPlugin(),
  ].concat([fullReload()]),
  build: {
    minify: true,
    cssMinify: true,
    sourcemap: false,
    rollupOptions: {
      onwarn(warning, warn) {
        if (warning.code === "EVAL" && warning.id && warning.id.endsWith("state.js")) return;
        warn(warning);
      },
      output: {
        codeSplitting: {
          groups: [
            {
              test: /env.json/,
              name: "reflex-env",
            },
          ],
        },
      },
    },
  },
  experimental: {
    enableNativePlugin: false,
    hmr: false,
  },
  oxc: {
    jsx: { development: false },
  },
  optimizeDeps: {
    rolldownOptions: {
      // Not part of the optimizer's cache key (plugins are excluded), so the
      // define below is what invalidates prebundled deps when this toggles.
      transform: { define: { "process.env.REFLEX_DEV_PROD_REACT": '"1"' } },
      plugins: [prodReactPrebundle()],
    },
  },
  server: {
    port: process.env.PORT,
    hmr: true,
    warmup: {
      clientFiles: ["./app/routes/**/*.jsx"],
    },
    watch: {
      ignored: [
        "**/.web/backend/**",
        "**/.web/reflex.install_frontend_packages.cached",
      ],
    },
  },
  // react-router prerenders by fetching pages from a `vite preview` server
  // started with this config. Pin an IPv4 loopback address so the bound
  // socket and the fetched URL cannot resolve `localhost` to different
  // address families (which refuses the connection, e.g. in docker).
  preview: {
    host: "127.0.0.1",
  },
  resolve: {
    mainFields: ["browser", "module", "jsnext"],
    alias: [
      {
        find: "$",
        replacement: fileURLToPath(new URL("./", import.meta.url)),
      },
      {
        find: "@",
        replacement: fileURLToPath(new URL("./public", import.meta.url)),
      },
    ],
  },
}));