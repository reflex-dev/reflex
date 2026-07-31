/**
 * ISR render tier for Reflex.
 *
 * A small HTTP service that renders the react-router **server bundle** to HTML
 * for a given route, so the Python ISR page-server (reflex.isr.HttpRenderer)
 * can cache and serve it.  This is the one component that must run JavaScript;
 * it is deployed as its own service (off the request hot path, scale-to-zero
 * friendly) rather than in every frontend pod.
 *
 * Contract (matches reflex.isr.HttpRenderer):
 *   POST /            { "path": "/blog/hello" }
 *   200  -> { "html": "<!DOCTYPE html>…", "revalidate"?: number, "tags"?: string[] }
 *   non-200          -> ISR treats it as a render failure (serves stale/shell)
 *
 * Requirements:
 *   - An SSR build of the app (react-router build with `ssr: true`) producing
 *     `build/server/index.js`.  The app root `loader()` fetches page state from
 *     the Python `/_ssr_data` endpoint, so this service needs network access to
 *     the backend (set SSR_DATA / the backend URL in the app env).
 *   - Node deps: `react-router`, `express`.
 *
 * Run:  node isr-render.mjs   (listens on $PORT, default 8600)
 *
 * Optional per-page cache hints: the app may set response headers
 *   `X-Reflex-Revalidate: <seconds>`  and  `X-Reflex-Tags: a,b,c`
 * which are forwarded to the ISR cache; otherwise Python applies its defaults.
 */
import { createRequestHandler } from "react-router";
import express from "express";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname =
  import.meta.dirname ?? dirname(fileURLToPath(import.meta.url));

const serverBuild = join(__dirname, "build", "server", "index.js");
const build = await import(serverBuild);
const handler = createRequestHandler(build, "production");

const app = express();
app.use(express.json({ limit: "1mb" }));

// Health endpoint for k8s probes.
app.get("/_health", (_req, res) => res.status(200).send("OK"));

app.post("/", async (req, res) => {
  const path =
    typeof req.body?.path === "string" && req.body.path ? req.body.path : "/";

  try {
    // Render the target route through react-router as a normal GET document
    // request.  The app's loader runs here and pulls state from /_ssr_data.
    const url = new URL(path, "http://reflex-isr-render.local");
    const request = new Request(url, {
      method: "GET",
      headers: {
        "User-Agent": "ReflexISRRenderer/1.0",
        Accept: "text/html",
        // Forward the caller's cookies so authenticated/personalized loaders
        // resolve the same way they would for the original visitor, if the
        // page-server chooses to pass them along.
        ...(req.body?.cookie ? { Cookie: String(req.body.cookie) } : {}),
      },
    });

    const response = await handler(request);
    const html = await response.text();

    if (!response.ok || !html) {
      return res
        .status(502)
        .json({ error: "render_failed", status: response.status });
    }

    const revalidate = headerNumber(response, "x-reflex-revalidate");
    const tags = headerList(response, "x-reflex-tags");

    return res.json({
      html,
      ...(revalidate != null ? { revalidate } : {}),
      ...(tags.length ? { tags } : {}),
    });
  } catch (err) {
    console.error("[isr-render] render error for", path, err);
    return res.status(500).json({ error: String(err) });
  }
});

function headerNumber(response, name) {
  const raw = response.headers.get(name);
  if (raw == null) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function headerList(response, name) {
  const raw = response.headers.get(name);
  return raw
    ? raw
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
    : [];
}

const port = parseInt(process.env.PORT || "8600", 10);
app.listen(port, () => {
  console.log(`[isr-render] listening on http://localhost:${port}`);
});
