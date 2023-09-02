import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/router";

/**
 * React hook for use in page components to enable client-side routing.
 *
 * Uses the next/router to redirect to the provided URL when loading
 * the 404 page (for example as a fallback in static hosting situations).
 * Resets the `routeNotFound` state when navigating to a non-404 page.
 * Registers for `routeChangeComplete` events to re-hydrate the state when
 * navigating between pages.
 *
 * @returns {boolean} routeNotFound - true if the current route is an actual 404
 */
export const useClientSideRouting = () => {
  const [routeNotFound, setRouteNotFound] = useState(false)
  const didRedirect = useRef(false)
  const router = useRouter()
  useEffect(() => {  // Effect performs the actual redirection
    if (
      router.isReady &&
      !didRedirect.current  // have not tried redirecting yet
    ) {
      // attempt to redirect to the route in the browser address bar once
      didRedirect.current = true
      router.replace({
          pathname: window.location.pathname,
          query: window.location.search.slice(1),
      })
      .catch((e) => {
        // When navigation fails, set routeNotFound to true to avoid redirecting again,
        // which avoids hitting the "Hard Navigate" invariant error.
        setRouteNotFound(true)
      })
    }
  }, [router.isReady]);

  // Return the reactive bool, so we can avoid flashing 404 page until we know
  // for sure the route is not found.
  return routeNotFound
}