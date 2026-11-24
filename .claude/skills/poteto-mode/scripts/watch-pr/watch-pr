#!/usr/bin/env bun
import { ensureDependenciesInstalled } from "../bootstrap.ts";

ensureDependenciesInstalled();
const { main } = await import("./cli.ts");
process.exitCode = await main(process.argv.slice(2));
