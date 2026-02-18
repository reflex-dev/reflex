import { GridCellKind } from "@glideapps/glide-data-grid";

export function getDEColumn(columns, col) {
  let c = columns[col];
  c.pos = col;
  return c;
}

export function getDERow(data, row) {
  return data[row];
}

export function locateCell(row, column) {
  if (Array.isArray(row)) {
    return row[column.pos];
  } else {
    return row[column.id];
  }
}

export function formatCell(value, column) {
  const editable = column.editable ?? true;
  switch (column.type) {
    case "int":
    case "float":
      return {
        kind: GridCellKind.Number,
        data: value,
        displayData: value + "",
        readonly: !editable,
        allowOverlay: editable,
      };
    case "datetime":
    // value = moment format?
    case "str":
      return {
        kind: GridCellKind.Text,
        data: value,
        displayData: value,
        readonly: !editable,
        allowOverlay: editable,
      };
    case "bool":
      return {
        kind: GridCellKind.Boolean,
        data: value,
        readonly: !editable,
      };
    case "dropdown":
      const cellValue = value ? String(value) : "";
      return {
        kind: GridCellKind.Custom,
        allowOverlay: true,
        copyData: cellValue,
        displayData: cellValue,
        readonly: false,
        data: {
          kind: "dropdown-cell",
          allowedValues: (column.allowedValues || []).map(v => String(v)),
          value: cellValue,
        },
      };
    default:
      console.log(
        "Warning: column.type is undefined for column.title=" + column.title,
      );
      return {
        kind: GridCellKind.Text,
        data: value,
        displayData: column.type,
      };
  }
}

export function formatDataEditorCells(col, row, columns, data) {
  if (row < data.length && col < columns.length) {
    const column = getDEColumn(columns, col);
    const rowData = getDERow(data, row);
    const cellData = locateCell(rowData, column);
    return formatCell(cellData, column);
  }
  return { kind: GridCellKind.Loading };
}
