import fs from "node:fs";
import { finished } from "node:stream/promises";
import { killGroup } from "./kill.ts";

const [pid, ...dirs] = process.argv.slice(2);

let input = "";
process.stdin.setEncoding("utf8").on("data", (chunk: string) => (input += chunk));
await finished(process.stdin).catch(() => {});
const running = !input.includes("exited");
const groupOutlivesWorker = process.platform !== "win32";
if (running || groupOutlivesWorker) await killGroup(Number(pid));
for (const dir of dirs) fs.rmSync(dir, { recursive: true, force: true });
