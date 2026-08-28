import * as React from "react";

// Records what React.captureOwnerStack() returns *during render*, per marker.
// Owner stacks are only available while React is rendering, so this must run
// in the component body. Results accumulate in window.__ownerStackCaptures.
export function OwnerProbe({ marker }) {
  let stack;
  try {
    stack =
      typeof React.captureOwnerStack === "function"
        ? React.captureOwnerStack()
        : "<no captureOwnerStack API>";
  } catch (e) {
    stack = "<threw: " + (e && e.message) + ">";
  }
  if (typeof window !== "undefined") {
    window.__ownerStackCaptures = window.__ownerStackCaptures || [];
    window.__ownerStackCaptures.push({
      marker: marker,
      t: Date.now(),
      stack: stack,
    });
    // Also expose React itself so the driver can poke at internals.
    window.__probeReact = React;
  }
  return null;
}
