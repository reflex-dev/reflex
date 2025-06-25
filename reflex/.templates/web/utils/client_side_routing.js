import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/**
 * React hook for use in NotFound page to enable client-side routing.
 *
 * Uses React Router to redirect to the provided URL when loading
 * the NotFound page (for example as a fallback in static hosting situations).
 *
 * @returns {boolean} routeNotFound - true if the current route is an actual 404
 */
export const useClientSideRouting = () => {
  const [routeNotFound, setRouteNotFound] = useState(false);
  const didRedirect = useRef(false);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!didRedirect.current) {
      // have not tried redirecting yet
      didRedirect.current = true; // never redirect twice to avoid navigation loops

      // attempt to redirect to the route in the browser address bar once
      const path = window.location.pathname;
      const search = window.location.search;

      // Use navigate instead of replace
      navigate(path + search, { replace: true, state: { fromNotFound: true } })
        .then(() => {
          // Check if we're still on a NotFound route
          // Note: This depends on how your routes are set up
          if (location.pathname === path) {
            setRouteNotFound(true); // Mark as an actual 404
          }
        })
        .catch(() => {
          setRouteNotFound(true); // navigation failed, so this is a real 404
        });
    }
  }, [location, navigate]);

  // Return the reactive bool, to avoid flashing 404 page until we know for sure
  // the route is not found.
  return routeNotFound;
};
