import { useEffect, useRef } from "react";

const handle_paste_data = (clipboardData) =>
  new Promise((resolve, reject) => {
    const pasted_data = [];
    const n_items = clipboardData.items.length;
    const extract_data = (item) => {
      const type = item.type;
      if (item.kind === "string") {
        item.getAsString((data) => {
          pasted_data.push([type, data]);
          if (pasted_data.length === n_items) {
            resolve(pasted_data);
          }
        });
      } else if (item.kind === "file") {
        const file = item.getAsFile();
        const reader = new FileReader();
        reader.onload = (e) => {
          pasted_data.push([type, e.target.result]);
          if (pasted_data.length === n_items) {
            resolve(pasted_data);
          }
        };
        if (type.indexOf("text/") === 0) {
          reader.readAsText(file);
        } else {
          reader.readAsDataURL(file);
        }
      }
    };
    for (const item of clipboardData.items) {
      extract_data(item);
    }
  });

export default function usePasteHandler(target_ids, event_actions, on_paste) {
  const onPasteRef = useRef(on_paste);
  const eventActionsRef = useRef(event_actions);

  useEffect(() => {
    onPasteRef.current = on_paste;
  }, [on_paste]);
  useEffect(() => {
    eventActionsRef.current = event_actions;
  }, [event_actions]);

  useEffect(() => {
    const handle_paste = (_ev) => {
      eventActionsRef.current?.preventDefault && _ev.preventDefault();
      eventActionsRef.current?.stopPropagation && _ev.stopPropagation();
      handle_paste_data(_ev.clipboardData).then(onPasteRef.current);
    };

    let cleanupListeners = null;
    let observer = null;

    const attachListeners = (targets) => {
      targets.forEach((target) =>
        target.addEventListener("paste", handle_paste, false),
      );
      return () => {
        targets.forEach((target) =>
          target.removeEventListener("paste", handle_paste, false),
        );
      };
    };

    const tryAttach = () => {
      if (target_ids.length === 0) {
        cleanupListeners = attachListeners([document]);
        return true;
      }
      const targets = target_ids
        .map((id) => document.getElementById(id))
        .filter((element) => !!element);

      if (targets.length === target_ids.length) {
        cleanupListeners = attachListeners(targets);
        return true;
      }

      return false;
    };

    if (!tryAttach()) {
      observer = new MutationObserver(() => {
        if (tryAttach()) {
          observer.disconnect();
          observer = null;
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }

    return () => {
      if (observer) {
        observer.disconnect();
      }
      if (cleanupListeners) {
        cleanupListeners();
      }
    };
  }, [target_ids]);
}
