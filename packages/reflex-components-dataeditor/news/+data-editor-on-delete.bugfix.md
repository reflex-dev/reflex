Pressing Delete in an `rx.data_editor` with `on_delete` bound now clears the selected cells instead of throwing a `TypeError` in the browser; the handler still receives the deleted selection.
