import { useEffect } from "react";

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
  return useEffect(() => {
    const handle_paste = (_ev) => {
      event_actions.preventDefault && _ev.preventDefault();
      event_actions.stopPropagation && _ev.stopPropagation();
      handle_paste_data(_ev.clipboardData).then(on_paste);
    };
    const targets = target_ids
      .map((id) => document.getElementById(id))
      .filter((element) => !!element);
    if (target_ids.length === 0) {
      targets.push(document);
    }
    targets.forEach((target) =>
      target.addEventListener("paste", handle_paste, false),
    );
    return () => {
      targets.forEach((target) =>
        target.removeEventListener("paste", handle_paste, false),
      );
    };
  });
}
