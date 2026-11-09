import { useEffect, useLayoutEffect } from "react";

/**
 * useLayoutEffect warns when React renders on the server, where it is a
 * no-op anyway. Fall back to useEffect there and keep the pre-paint read on
 * the client, which is the only place it can do anything.
 */
export const useIsomorphicLayoutEffect =
  typeof window === "undefined" ? useEffect : useLayoutEffect;
