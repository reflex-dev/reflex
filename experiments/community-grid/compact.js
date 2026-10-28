import React from "react";
import { createRoot } from "react-dom/client";
import { CommunityGrid } from "../../packages/reflex-components-internal/src/reflex_components_internal/components/base/CommunityGrid.js";
const rows = Array.from({ length: 100 }, (_, index) => ({
  id: `account-${index}`,
  name: `Account ${String(index).padStart(3, "0")}`,
  region: ["North", "South", "East", "West"][index % 4],
  revenue: (index * 7919) % 100000,
}));
const columns = [
  { field: "name", headerName: "Account", floatingFilter: true },
  { field: "region", headerName: "Region", floatingFilter: true },
  {
    field: "revenue",
    headerName: "Revenue",
    filter: "agNumberColumnFilter",
    floatingFilter: true,
  },
];
createRoot(document.getElementById("app")).render(
  React.createElement(CommunityGrid, {
    rowData: rows,
    columnDefs: columns,
    pagination: false,
    style: { height: "100%", width: "100%" },
  }),
);
