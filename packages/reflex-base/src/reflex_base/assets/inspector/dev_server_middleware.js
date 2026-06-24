/* Dev-server middleware that opens a file:line:column in the user's editor.
 *
 * Mounted by the inspector Vite plugin (and the equivalent Astro hook).
 * The browser sends `GET /__open-in-editor?file=<path>:<line>:<col>`.
 */

import launch from "launch-editor";

const reflexEditorMiddleware = (req, res, next) => {
  if (!req.url || !req.url.includes("/__open-in-editor")) {
    return next();
  }
  let url;
  try {
    url = new URL(req.url, "http://localhost");
  } catch (err) {
    res.statusCode = 400;
    res.end("Invalid URL");
    return;
  }
  const file = url.searchParams.get("file");
  if (!file) {
    res.statusCode = 400;
    res.end("Missing 'file' query parameter");
    return;
  }
  const editor = process.env.REFLEX_EDITOR || undefined;
  launch(file, editor, (fileName, errorMsg) => {
    if (errorMsg) {
      // eslint-disable-next-line no-console
      console.error("[reflex-inspector] launch-editor:", errorMsg);
    }
  });
  res.statusCode = 204;
  res.end();
};

export default reflexEditorMiddleware;
