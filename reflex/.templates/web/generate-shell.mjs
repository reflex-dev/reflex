/**
 * Post-build script: generates a static SPA shell (build/client/index.html).
 *
 * With ssr:true, `react-router build` does not emit index.html because all
 * HTML is rendered at request time.  The production server (ssr-serve.js)
 * serves this pre-built shell to regular users for instant load with zero
 * SSR overhead; only bots go through the SSR path.
 *
 * The X-Reflex-Shell-Gen header tells the root loader to short-circuit and
 * return { state: null } without contacting the Python backend.
 */
import { createRequestHandler } from "react-router";
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// Resolve paths relative to this file, not process.cwd().
const __dirname =
  import.meta.dirname ?? dirname(fileURLToPath(import.meta.url));

const build = await import(join(__dirname, "build", "server", "index.js"));
const handler = createRequestHandler(build, "production");

const request = new Request("http://localhost/", {
  headers: {
    "User-Agent": "Mozilla/5.0 Chrome/120 (Shell Generator)",
    "X-Reflex-Shell-Gen": "1",
  },
});

const response = await handler(request);
const html = await response.text();

const outPath = join(__dirname, "build", "client", "index.html");
writeFileSync(outPath, html);
console.log("Generated build/client/index.html");
