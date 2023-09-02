import { createContext, useContext, useEffect, useRef, useState } from "react";
import { useRouter } from "next/router";
import { initialEvents, EventLoopContext } from "/utils/context";

// Stores `routeNotFound` and `setRouteNotFound` state as top-level context.
export const ClientSideRoutingContext = createContext(null)

/**
 * Top-level provider wraps the page component to enable client-side routing.
 *
 * Responsible for sending the initial hydrate events (from /utils/context) to
 * the server once the router is ready, which triggers on_load handlers on the
 * backend.
 *
 * Because on_load handlers are route-specific it is important to capture the
 * current path/route as soon as possible before any other router navigation
 * events occur, so that the initial on_load events triggered by the hydrate
 * event are for the correct page.
 *
 * @param children child components (i.e. the page component)
 * @returns {React.Component} ClientSideRoutingProvider which sets ClientSideRoutingContext to
 *  [routeNotFound, setRouteNotFound, Event]
 */
export function ClientSideRoutingProvider({ children }) {
  // Track routeNotFound at the app-level to avoid resetting it when redirecting.
  const [routeNotFound, setRouteNotFound] = useState(false);
  const [Event] = useContext(EventLoopContext)
  const router = useRouter()
  const sentHydrate = useRef(false);  // Avoid double-hydrate due to React strict-mode
  useEffect(() => {
    if (router.isReady && !sentHydrate.current) {
      Event(initialEvents.map((e) => ({...e})))
      sentHydrate.current = true
    }
  }, [router.isReady])

  return (
    <ClientSideRoutingContext.Provider value={[routeNotFound, setRouteNotFound, Event]}>
      {children}
    </ClientSideRoutingContext.Provider>
  )
}

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
  const [routeNotFound, setRouteNotFound, Event] = useContext(ClientSideRoutingContext)
  const router = useRouter()
  useEffect(() => {  // Effect performs the actual redirection
    if (router.isReady) {
      if (!routeNotFound) {  // have not tried redirecting yet
        if (router.pathname === "/404" && window.location.pathname !== router.pathname) {
          // The 404 page is being loaded, but the browser path is not /404, so
          // attempt to redirect to the browser page once.
          router.replace({
              pathname: window.location.pathname,
              query: window.location.search.slice(1),
          })
          .catch((e) => {
            // When navigation fails, set routeNotFound to true to avoid redirecting again,
            // which causes the "Hard Navigate" invariant error.
            setRouteNotFound(true)
          })
        }
      }
    }
  }, [router.isReady]);

  useEffect(() => {  // Effect handles re-hydration on route change
    const change_complete = () => {
      // re-hydrate when navigating between pages
      Event(initialEvents.map((e) => ({...e})))
    }
    router.events.on('routeChangeComplete', change_complete)
    return () => {
      router.events.off('routeChangeComplete', change_complete)
    }
  }, [router])

  // Return the reactive bool, so we can avoid flashing 404 page until we know
  // for sure the route is not found.
  return routeNotFound
}