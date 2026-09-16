import { useState, type ReactNode } from "react";

import { useIsomorphicLayoutEffect } from "$/public/homepage/lib/use-isomorphic-layout-effect";

/** A release identifier lets each new announcement appear after an older dismissal. */
const ANNOUNCEMENT_STORAGE_KEY = "reflex_announcement_dismissed_release";

function isAnnouncementDismissed(
  storage: Pick<Storage, "getItem">,
  release: string,
) {
  try {
    return storage.getItem(ANNOUNCEMENT_STORAGE_KEY) === release;
  } catch {
    return false;
  }
}

function persistAnnouncementDismissal(
  storage: Pick<Storage, "setItem">,
  release: string,
) {
  try {
    storage.setItem(ANNOUNCEMENT_STORAGE_KEY, release);
  } catch {
    // Storage may be unavailable; dismissal still works for this page visit.
  }
}

/** Read before paint and reserve no space for announcements already dismissed. */
export function AnnouncementVisibility({
  children,
  release,
}: {
  children: ReactNode;
  release: string;
}) {
  const [visible, setVisible] = useState(true);

  useIsomorphicLayoutEffect(() => {
    const sync = () => {
      try {
        const dismissed = isAnnouncementDismissed(window.localStorage, release);
        if (dismissed)
          document.documentElement.dataset.announcementDismissed = "true";
        else delete document.documentElement.dataset.announcementDismissed;
        setVisible(!dismissed);
      } catch {
        setVisible(true);
      }
    };
    sync();
    const onStorage = (event: StorageEvent) => {
      if (event.key === ANNOUNCEMENT_STORAGE_KEY || event.key === null) sync();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [release]);

  return (
    <div
      className={visible ? "contents" : "hidden"}
      data-announcement-visibility={visible ? "visible" : "hidden"}
      onClickCapture={(event) => {
        if (
          !(event.target instanceof Element) ||
          !event.target.closest("[data-announcement-dismiss]")
        )
          return;
        try {
          persistAnnouncementDismissal(window.localStorage, release);
        } catch {
          // Accessing localStorage itself can fail in restricted browsers.
        }
        document.documentElement.dataset.announcementDismissed = "true";
        setVisible(false);
      }}
    >
      {children}
    </div>
  );
}
