---
title: Tables and Data Grids
meta_description: "Display and edit tabular data in Python with Reflex. Choose between a composable table, a searchable and sortable data table for pandas DataFrames, and an editable data grid — all in pure Python."
---

# Tables and Data Grids in Reflex

Reflex gives you three ways to work with tabular data in pure Python — no JavaScript required. Pick the component that matches your use case:

- [Table](/docs/library/tables-and-data-grids/table) — a semantic, composable React/HTML table you build from headers, rows, and cells. Best when you want full control over the markup and styling.
- [Data Table](/docs/library/tables-and-data-grids/data-table) — display a pandas DataFrame as an interactive data table with built-in search, sorting, and pagination. Best for read-only views of static data.
- [Data Editor](/docs/library/tables-and-data-grids/data-editor) — a fast, editable, spreadsheet-like data grid (based on Glide Data Grid) for adding and editing tabular data across many rows and columns.

## Which one should I use?

- Use the [Table](/docs/library/tables-and-data-grids/table) when you render your own rows and want a lightweight, fully styleable table component.
- Use the [Data Table](/docs/library/tables-and-data-grids/data-table) when your data is already in a pandas DataFrame and you want search, sort, and pagination out of the box.
- Use the [Data Editor](/docs/library/tables-and-data-grids/data-editor) when users need to edit cells interactively, like a spreadsheet.
