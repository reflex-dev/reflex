import * as build from "./build/server/index.js";
import { createRequestHandler } from "react-router";
const handler = createRequestHandler(build, "production");
for (const path of process.argv.slice(2)) {
  try {
    const res = await handler(new Request("http://localhost" + path));
    const text = await res.text();
    console.log("==", path, res.status, text.length, "bytes", text.includes("Internal Server Error") ? "ISE" : "");
  } catch (e) {
    console.log("==", path, "THREW", e && e.stack ? e.stack.split("\n").slice(0, 8).join("\n") : e);
  }
}
