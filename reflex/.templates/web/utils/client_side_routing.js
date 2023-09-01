import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/router";
import { initialEvents, EventLoopContext } from "/utils/context";

// Stores `routeNotFound` and `setRouteNotFound` state as top-level context.
export const ClientSideRoutingContext = createContext(null)

// Wrap the app in this provider to enable client-side routing via
// `useClientSideRouting` hook in a page component.
export function ClientSideRoutingProvider({ children }) {
  const [routeNotFound, setRouteNotFound] = useState(false);
  const [Event] = useContext(EventLoopContext)
  const router = useRouter()
  let sent_hydrate = false;  // avoid strict-mode side-effect double-hydrate
  useEffect(() => {
    if (router.isReady && !sent_hydrate) {
      Event(initialEvents)
      sent_hydrate = true
    }
  }, [router.isReady])

  return (
    <ClientSideRoutingContext.Provider value={[routeNotFound, setRouteNotFound, Event]}>
      {children}
    </ClientSideRoutingContext.Provider>
  )
}

// React hook for page components to redirect to the given URL when loading
// the 404 page. Also resets the `routeNotFound` state when navigating to a
// non-404 page.
export const useClientSideRouting = () => {
  const [routeNotFound, setRouteNotFound, Event] = useContext(ClientSideRoutingContext)
  const router = useRouter()
  useEffect(() => {
    if (!routeNotFound) {
      if (router.pathname === "/404" && window.location.pathname !== router.pathname) {
        router.replace({
            pathname: window.location.pathname,
            query: window.location.search.slice(1),
        })
        .catch((e) => {
          setRouteNotFound(true)  // couldn't navigate, show 404
        })
      }
    } else if (router.pathname !== "/404") {
      setRouteNotFound(false)  // non-404 page, route _was_ found
    }
  }, []);
  useEffect(() => {
    const change_complete = () => {
      Event(initialEvents)
      if (routeNotFound && router.pathname !== "/404") {
        setRouteNotFound(false)  // non-404 page, route _was_ found (via navigation)
      }
    }
    router.events.on('routeChangeComplete', change_complete)
    return () => {
      router.events.off('routeChangeComplete', change_complete)
    }
  }, [router])
  return routeNotFound
}