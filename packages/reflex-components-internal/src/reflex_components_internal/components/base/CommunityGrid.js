import React, { useMemo, useRef, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import { AllCommunityModule, themeQuartz } from "ag-grid-community";

const modules = [AllCommunityModule];
const theme = themeQuartz.withParams({
  fontFamily: "var(--font-sans, Inter, system-ui, sans-serif)",
  fontSize: 13,
  accentColor: "var(--primary-9, #6e56cf)",
  backgroundColor: "var(--secondary-1, #ffffff)",
  foregroundColor: "var(--secondary-12, #202020)",
  borderColor: "var(--secondary-6, #e2e2e2)",
  headerBackgroundColor: "var(--secondary-2, #f9f9f9)",
  headerTextColor: "var(--secondary-11, #646464)",
  headerFontWeight: 450,
  wrapperBorderRadius: "var(--radius-ui-md, 8px)",
  spacing: 6,
  rowHeight: 36,
  headerHeight: 38,
});
const defaultColDef = {
  sortable: true,
  resizable: true,
  filter: "agTextColumnFilter",
  flex: 1,
  minWidth: 120,
};
const columnKeys = [
  "field",
  "colId",
  "headerName",
  "width",
  "minWidth",
  "maxWidth",
  "flex",
  "hide",
  "pinned",
  "sort",
  "sortIndex",
  "sortable",
  "resizable",
  "filter",
  "floatingFilter",
  "cellDataType",
  "wrapText",
  "autoHeight",
];
const filters = new Set([
  false,
  "agTextColumnFilter",
  "agNumberColumnFilter",
  "agDateColumnFilter",
]);

export function communityColumns(columns) {
  return columns.map((column) => {
    const unknown = Object.keys(column).filter(
      (key) => !columnKeys.includes(key),
    );
    if (unknown.length)
      throw new Error(
        `Unsupported Community column options: ${unknown.join(", ")}`,
      );
    const result = Object.fromEntries(
      columnKeys
        .filter((key) => key in column)
        .map((key) => [key, column[key]]),
    );
    if ("filter" in result && !filters.has(result.filter)) {
      throw new Error(`Unsupported Community filter: ${result.filter}`);
    }
    return result;
  });
}

export function validateRowIds(rows, key) {
  const seen = new Set();
  for (const row of rows) {
    const id = row[key];
    if (
      (typeof id !== "string" && typeof id !== "number") ||
      !Number.isFinite(typeof id === "number" ? id : 0)
    ) {
      throw new Error(
        `CommunityGrid requires a stable string or number in ${key} for every row`,
      );
    }
    const value = String(id);
    if (seen.has(value))
      throw new Error(`Duplicate CommunityGrid row ID: ${value}`);
    seen.add(value);
  }
  return rows;
}

export function CommunityGrid({
  rowData = [],
  columnDefs = [],
  rowIdKey = "id",
  selectionMode = "none",
  pagination = true,
  pageSize = 25,
  quickFilter = "",
  loading = false,
  initialState,
  onStateChanged,
  onSelectionChanged,
  className,
  style,
  id,
}) {
  const grid = useRef(null);
  const [, refreshColumns] = useState(0);
  const rows = useMemo(
    () => validateRowIds(rowData, rowIdKey),
    [rowData, rowIdKey],
  );
  const columns = useMemo(() => communityColumns(columnDefs), [columnDefs]);
  const selection = useMemo(
    () =>
      selectionMode === "none"
        ? undefined
        : {
            mode: selectionMode,
            enableClickSelection: true,
          },
    [selectionMode],
  );
  const getRowId = useMemo(
    () =>
      ({ data }) =>
        String(data[rowIdKey]),
    [rowIdKey],
  );
  const authoredIds = new Set(columns.map((col) => col.colId ?? col.field));
  const fullColumnState =
    grid.current?.api?.getColumnState() ??
    columns.map((col) => ({ ...col, colId: col.colId ?? col.field }));
  const columnState = fullColumnState.filter((col) =>
    authoredIds.has(col.colId),
  );
  const applyColumn = (colId, change) => {
    grid.current.api.applyColumnState({
      state: [{ colId, ...change, ...(change.pinned ? { flex: null } : {}) }],
    });
    refreshColumns((n) => n + 1);
  };
  const moveColumn = (index, delta) => {
    const order = [...columnState];
    [order[index], order[index + delta]] = [order[index + delta], order[index]];
    grid.current.api.applyColumnState({
      state: [
        ...fullColumnState.filter((col) => !authoredIds.has(col.colId)),
        ...order,
      ].map(({ colId }) => ({ colId })),
      applyOrder: true,
    });
    refreshColumns((n) => n + 1);
  };
  const controlStyle = {
    font: "inherit",
    color: "inherit",
    background: "var(--secondary-1, white)",
    border: "1px solid var(--secondary-6, #ddd)",
    borderRadius: 4,
    padding: "3px 6px",
  };
  return React.createElement(
    "div",
    {
      id,
      className,
      style: {
        ...style,
        display: "flex",
        flexDirection: "column",
        minWidth: 0,
        fontFamily: "var(--font-sans, Inter, system-ui, sans-serif)",
        fontSize: 13,
        color: "var(--secondary-12, #202020)",
      },
    },
    React.createElement(
      "details",
      {
        style: { position: "relative", alignSelf: "flex-end", marginBottom: 8 },
      },
      React.createElement(
        "summary",
        { style: { ...controlStyle, cursor: "pointer" } },
        "Columns",
      ),
      React.createElement(
        "div",
        {
          style: {
            position: "absolute",
            right: 0,
            top: "100%",
            zIndex: 3,
            background: "var(--secondary-1, white)",
            border: "1px solid var(--secondary-6, #ddd)",
            borderRadius: "var(--radius-ui-md, 8px)",
            padding: 12,
            maxHeight: 280,
            overflow: "auto",
            width: 300,
            boxShadow: "0 4px 16px #0002",
          },
        },
        ...columnState.map((col, index) =>
          React.createElement(
            "div",
            {
              key: col.colId,
              style: {
                display: "flex",
                gap: 6,
                alignItems: "center",
                marginBottom: 8,
              },
            },
            React.createElement(
              "label",
              { style: { flex: 1 } },
              React.createElement("input", {
                type: "checkbox",
                checked: !col.hide,
                onChange: (event) =>
                  applyColumn(col.colId, { hide: !event.target.checked }),
              }),
              columns.find((item) => (item.colId ?? item.field) === col.colId)
                ?.headerName ?? col.colId,
            ),
            React.createElement(
              "select",
              {
                "aria-label": `Pin ${col.colId}`,
                value: col.pinned ?? "",
                style: controlStyle,
                onChange: (event) =>
                  applyColumn(col.colId, {
                    pinned: event.target.value || null,
                  }),
              },
              ...[
                ["", "Unpinned"],
                ["left", "Pin left"],
                ["right", "Pin right"],
              ].map(([value, label]) =>
                React.createElement("option", { key: value, value }, label),
              ),
            ),
            React.createElement(
              "button",
              {
                type: "button",
                "aria-label": `Move ${col.colId} earlier`,
                style: controlStyle,
                disabled: index === 0,
                onClick: () => moveColumn(index, -1),
              },
              "↑",
            ),
            React.createElement(
              "button",
              {
                type: "button",
                "aria-label": `Move ${col.colId} later`,
                style: controlStyle,
                disabled: index === columnState.length - 1,
                onClick: () => moveColumn(index, 1),
              },
              "↓",
            ),
          ),
        ),
      ),
    ),
    React.createElement(
      "div",
      { style: { flex: 1, minHeight: 0 } },
      React.createElement(AgGridReact, {
        ref: grid,
        modules,
        theme,
        rowData: rows,
        columnDefs: columns,
        defaultColDef,
        getRowId,
        rowSelection: selection,
        pagination,
        paginationPageSize: pageSize,
        paginationPageSizeSelector: false,
        quickFilterText: quickFilter,
        loading,
        initialState,
        suppressFieldDotNotation: true,
        onGridReady: () => refreshColumns((n) => n + 1),
        onColumnMoved: () => refreshColumns((n) => n + 1),
        onColumnPinned: () => refreshColumns((n) => n + 1),
        onColumnVisible: () => refreshColumns((n) => n + 1),
        onStateUpdated: onStateChanged
          ? ({ state }) => onStateChanged(state)
          : undefined,
        onSelectionChanged: onSelectionChanged
          ? ({ api }) =>
              onSelectionChanged(api.getSelectedNodes().map((node) => node.id))
          : undefined,
      }),
    ),
  );
}
