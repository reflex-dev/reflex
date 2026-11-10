// @vitest-environment-options { "url": "https://app.example.com/dashboard" }
/**
 * `getBackendURL` on a page served over https, where a backend named by a
 * wildcard bind address sits behind the same load balancer as the page.
 */
import { expect, test } from "vitest";

import { getBackendURL } from "$/utils/state";

test("a same-domain backend is reached on the page's host and https port", () => {
  expect(getBackendURL("http://localhost:8000/ping").href).toBe(
    "https://app.example.com/ping",
  );
  expect(getBackendURL("ws://0.0.0.0:8000/_event").href).toBe(
    "wss://app.example.com/_event",
  );
});

test("a backend on its own host keeps its protocol and port", () => {
  expect(getBackendURL("http://api.example.com:8000/ping").href).toBe(
    "http://api.example.com:8000/ping",
  );
});
