import { lazy, Suspense, useEffect, useState } from "react";

// The grid pulls in all of Lucide, so it loads after hydration instead of
// being preloaded with the page (and is never part of the prerendered HTML).
const IconGrid = lazy(() => import("./IconGrid.jsx"));

export function IconGallery({
  children,
  names,
  onCopy,
  inputClassName,
  gridClassName,
  tileClassName,
}) {
  const [query, setQuery] = useState("");
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return (
    <div className="flex flex-col gap-4">
      <div className="relative flex items-center">
        {/* The search icon, passed in so it stays a static import. */}
        <div className="absolute left-2 top-1/2 transform -translate-y-1/2 z-[1] shrink-0 flex items-center justify-center pb-2">
          {children}
        </div>
        <input
          placeholder="Search icons..."
          className={inputClassName}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      {/* Fixed height so the grid arriving later cannot shift the page. */}
      <div className="overflow-y-auto h-[500px]">
        {mounted && (
          <Suspense fallback={null}>
            <IconGrid
              names={names}
              query={query}
              onCopy={onCopy}
              gridClassName={gridClassName}
              tileClassName={tileClassName}
            />
          </Suspense>
        )}
      </div>
    </div>
  );
}
