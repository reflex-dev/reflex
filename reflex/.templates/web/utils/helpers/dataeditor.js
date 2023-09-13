import { GridCellKind } from "@glideapps/glide-data-grid"

export function formatCell(value, column) {
    switch (column.type) {
        case "int":
        case "float":
            return {
                kind: GridCellKind.Number,
                data: value,
                displayData: value + "",
                readonly: false,
                allowOverlay: true
            }
        case "datetime":
        // value = moment format?
        case "str":
            return {
                kind: GridCellKind.Text,
                data: value,
                displayData: value,
                readonly: false,
                allowOverlay: true
            }
        case "bool":
            return {
                kind: GridCellKind.Boolean,
                data: value,
                readonly: false,
                // allowOverlay: true
            }
        default:
            console.log(type, value);
    };
    return {
        kind: GridCellKind.Text,
        data: "foo",
        displayData: "unknown render method"
    }
};
