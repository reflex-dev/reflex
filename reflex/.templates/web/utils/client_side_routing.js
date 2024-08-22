import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/router";

/**
 * React hook for use in /404 page to enable client-side routing.
 *
 * Uses the next/router to redirect to the provided URL when loading
 * the 404 page (for example as a fallback in static hosting situations).
 *
 * @returns {boolean} routeNotFound - true if the current route is an actual 404
 */
export const useClientSideRouting = () => {
  const [routeNotFound, setRouteNotFound] = useState(false)
  const didRedirect = useRef(false)
  const router = useRouter()
  useEffect(() => {
    if (
      router.isReady &&
      !didRedirect.current  // have not tried redirecting yet
    ) {
      didRedirect.current = true  // never redirect twice to avoid "Hard Navigate" error
      // attempt to redirect to the route in the browser address bar once
      router.replace({
          pathname: window.location.pathname,
          query: window.location.search.slice(1),
      }).then(()=>{
          // Check if the current route is /404
        if (router.pathname === '/404') {
          setRouteNotFound(true); // Mark as an actual 404
        }
    })
      .catch((e) => {
        setRouteNotFound(true)  // navigation failed, so this is a real 404
      })
    }
  }, [router.isReady]);

  // Return the reactive bool, to avoid flashing 404 page until we know for sure
  // the route is not found.
  return routeNotFound
}