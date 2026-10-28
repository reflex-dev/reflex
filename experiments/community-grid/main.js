import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { CommunityGrid } from "../../packages/reflex-components-internal/src/reflex_components_internal/components/base/CommunityGrid.js";

const rows = Array.from({ length: 10000 }, (_, index) => ({
  id: `row-${index}`,
  name: `Account ${String(index).padStart(4, "0")}`,
  region: ["North", "South", "West", "East"][index % 4],
  revenue: (index * 7919) % 100000,
  active: index % 3 === 0,
}));
const reversedRows = [...rows].reverse();
const columns = [
  {
    field: "name",
    headerName: "Account",
    width: 210,
    flex: 0,
    floatingFilter: true,
  },
  { field: "region", headerName: "Region", floatingFilter: true },
  {
    field: "revenue",
    headerName: "Revenue",
    filter: "agNumberColumnFilter",
    floatingFilter: true,
  },
  { field: "active", headerName: "Active", filter: false },
];
window.gridEvents = [];
function App() {
  const [paginated, setPaginated] = useState(true);
  const [reverse, setReverse] = useState(false);
  const [query, setQuery] = useState("");
  const [saved, setSaved] = useState(undefined);
  const [current, setCurrent] = useState({});
  const [generation, setGeneration] = useState(0);
  const [empty, setEmpty] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState([]);
  const recordState = (state) => {
    setCurrent(state);
    window.lastGridState = state;
    window.gridEvents.push({ type: "state", state });
  };
  return React.createElement(
    React.Fragment,
    null,
    React.createElement(
      "header",
      null,
      React.createElement(
        "button",
        { onClick: () => setPaginated((v) => !v) },
        "Toggle pagination",
      ),
      React.createElement(
        "button",
        { onClick: () => setReverse((v) => !v) },
        "Reverse source rows",
      ),
      React.createElement("input", {
        "aria-label": "Search rows",
        placeholder: "Search rows",
        value: query,
        onChange: (e) => setQuery(e.target.value),
      }),
      React.createElement(
        "button",
        {
          onClick: () => {
            setSaved(current);
            window.savedGridState = current;
          },
        },
        "Save view",
      ),
      React.createElement(
        "button",
        { onClick: () => setGeneration((n) => n + 1), disabled: !saved },
        "Restore saved view",
      ),
      React.createElement(
        "button",
        { onClick: () => setEmpty((v) => !v) },
        "Toggle empty",
      ),
      React.createElement(
        "button",
        { onClick: () => setLoading((v) => !v) },
        "Toggle loading",
      ),
      React.createElement(
        "button",
        { onClick: () => document.body.classList.toggle("dark") },
        "Toggle dark",
      ),
    ),
    React.createElement(CommunityGrid, {
      key: generation,
      rowData: empty ? [] : reverse ? reversedRows : rows,
      columnDefs: columns,
      selectionMode: "multiRow",
      pageSize: 25,
      pagination: paginated,
      quickFilter: query,
      loading,
      initialState: saved,
      onStateChanged: recordState,
      onSelectionChanged: (ids) => {
        setSelected(ids);
        window.selectedIds = ids;
      },
      style: { height: 520, width: "100%" },
    }),
    React.createElement(
      "p",
      { role: "status" },
      `Selected rows: ${selected.length}`,
    ),
  );
}
createRoot(document.getElementById("app")).render(React.createElement(App));
