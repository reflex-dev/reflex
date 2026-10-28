import React, { useEffect, useMemo, useState } from 'react';

import { cellValue, deriveRows, validateTable } from "./nativeTableModel.js";

const h = React.createElement;

const css = `
.rx-native-table{font:13px var(--font-sans,Inter,system-ui,sans-serif);color:var(--secondary-12,#202020);background:var(--secondary-1,#fff);border:1px solid var(--secondary-6,#ddd);border-radius:var(--radius-ui-md,10px);overflow:hidden}
.rx-native-table button,.rx-native-table input,.rx-native-table select{font:inherit;color:inherit}.rx-native-table button,.rx-native-table select,.rx-native-table input[type=search]{border:1px solid var(--secondary-6,#ddd);border-radius:6px;background:var(--secondary-1,#fff);padding:7px 9px}.rx-native-table button{cursor:pointer}.rx-native-table button:disabled{opacity:.45;cursor:default}.rx-native-table :focus-visible{outline:2px solid var(--primary-9,#6e56cf);outline-offset:2px}.rx-native-table .tools,.rx-native-table footer{display:flex;align-items:center;flex-wrap:wrap;gap:10px;padding:12px}.rx-native-table .tools{border-bottom:1px solid var(--secondary-6,#ddd)}.rx-native-table .tools input{max-width:100%;box-sizing:border-box}.rx-native-table .column-panel{padding:12px;background:var(--secondary-2,#fafafa);border-bottom:1px solid var(--secondary-6,#ddd)}.rx-native-table .column-setting{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:6px 0}.rx-native-table .column-setting>label:first-child{min-width:130px}.rx-native-table .scroller{overflow:auto;max-height:450px}.rx-native-table table{border-collapse:collapse;table-layout:fixed;min-width:100%}.rx-native-table th,.rx-native-table td{text-align:left;box-sizing:border-box;padding:10px 12px;border-bottom:1px solid var(--secondary-4,#eee);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rx-native-table th{position:sticky;top:0;background:var(--secondary-2,#fafafa);font-weight:500;z-index:1}.rx-native-table th button{border:0;background:transparent;padding:2px 0}.rx-native-table td:first-child,.rx-native-table th:first-child{width:44px}.rx-native-table tr[data-selected=true]{background:var(--primary-3,#f3f0ff)}.rx-native-table .message{padding:30px;text-align:center;color:var(--secondary-11,#666)}.rx-native-table footer{justify-content:space-between}.rx-native-table footer nav{display:flex;gap:8px;align-items:center}
`;

export function NativeTable({ rows = [], columns = [], rowIdKey = 'id', pageSize = 25, loading = false, error = '', onSelectionChanged, id, style, className = '' }) {
  useMemo(() => validateTable(rows, columns, rowIdKey), [rows, columns, rowIdKey]);
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState(null);
  const [order, setOrder] = useState(() => columns.map(column => column.key));
  const [hidden, setHidden] = useState([]);
  const [widths, setWidths] = useState(() => new Map());
  const [selected, setSelected] = useState([]);
  const [page, setPage] = useState(0);
  const [panel, setPanel] = useState(false);
  const existingIds = useMemo(() => new Set(rows.map(row => String(row[rowIdKey]))), [rows, rowIdKey]);
  const selectedIds = useMemo(() => new Set(selected.filter(key => existingIds.has(key))), [selected, existingIds]);
  useEffect(() => {
    const next = selected.filter(key => existingIds.has(key));
    if (next.length !== selected.length) {
      setSelected(next);
      onSelectionChanged?.(next);
    }
  }, [existingIds, selected, onSelectionChanged]);
  const filtered = useMemo(() => deriveRows(rows, columns, query, sort), [rows, columns, query, sort]);
  if (!Number.isInteger(pageSize) || pageSize < 1) throw new Error('pageSize must be a positive integer.');
  const size = pageSize;
  const pages = Math.max(1, Math.ceil(filtered.length / size));
  const currentPage = Math.min(page, pages - 1);
  const displayed = filtered.slice(currentPage * size, (currentPage + 1) * size);
  const byKey = new Map(columns.map(column => [column.key, column]));
  const ordered = [...order.filter(key => byKey.has(key)), ...columns.map(column => column.key).filter(key => !order.includes(key))];
  const visible = ordered.filter(key => !hidden.includes(key));
  const changeSelection = (key, checked) => {
    const next = [...selectedIds].filter(value => value !== key);
    if (checked) next.push(key);
    setSelected(next);
    onSelectionChanged?.(next);
  };
  const moveColumn = (key, delta) => {
    const from = ordered.indexOf(key), to = from + delta;
    if (to < 0 || to >= ordered.length) return;
    const next = [...ordered];
    [next[from], next[to]] = [next[to], next[from]];
    setOrder(next);
  };
  const header = h('tr', null, h('th', { scope: 'col' }, h('span', { 'aria-label': 'Selection' }, '✓')), ...visible.map(key => {
    const column = byKey.get(key), active = sort?.key === key;
    return h('th', { key, scope: 'col', style: { width: widths.get(key) ?? column.width ?? 180 }, 'aria-sort': active ? sort.direction === 'asc' ? 'ascending' : 'descending' : 'none' }, h('button', { type: 'button', onClick: () => { setSort(active && sort.direction === 'desc' ? null : { key, direction: active ? 'desc' : 'asc' }); setPage(0); } }, `${column.label ?? key}${active ? sort.direction === 'asc' ? ' ↑' : ' ↓' : ''}`));
  }));
  const body = displayed.map(row => h('tr', { key: String(row[rowIdKey]), 'data-selected': selectedIds.has(String(row[rowIdKey])) },
    h('td', null, h('input', { type: 'checkbox', 'aria-label': `Select row ${row[rowIdKey]}`, checked: selectedIds.has(String(row[rowIdKey])), onChange: event => changeSelection(String(row[rowIdKey]), event.target.checked) })),
    ...visible.map(key => h('td', { key, title: String(cellValue(row, key) ?? '') }, String(cellValue(row, key) ?? '')))));
  const table = h('div', { className: 'scroller' }, h('table', { 'aria-label': 'Records', style: { width: 44 + visible.reduce((total, key) => total + (widths.get(key) ?? byKey.get(key).width ?? 180), 0) } }, h('thead', null, header), h('tbody', null, body)));
  const content = error ? h('div', { className: 'message', role: 'alert' }, error) : loading ? h('div', { className: 'message', role: 'status' }, 'Loading rows…') : !filtered.length ? h('div', { className: 'message', role: 'status' }, query ? 'No matching rows.' : 'No rows yet.') : table;
  return h('section', { id, className: `rx-native-table ${className}`, style, 'aria-label': 'Data table' },
    h('style', null, css),
    h('div', { className: 'tools' },
      h('input', { type: 'search', 'aria-label': 'Filter rows', placeholder: 'Filter rows…', value: query, onChange: event => { setQuery(event.target.value); setPage(0); } }),
      h('button', { type: 'button', 'aria-expanded': panel, onClick: () => setPanel(!panel) }, 'Columns'),
      h('span', { role: 'status', 'aria-live': 'polite' }, `${filtered.length} rows · ${selectedIds.size} selected`)),
    panel && h('div', { className: 'column-panel', 'aria-label': 'Column settings' }, ordered.map((key, index) => {
      const column = byKey.get(key);
      return h('div', { className: 'column-setting', key },
        h('label', null, h('input', { type: 'checkbox', checked: !hidden.includes(key), disabled: visible.length === 1 && visible.includes(key), onChange: event => setHidden(event.target.checked ? hidden.filter(value => value !== key) : [...hidden, key]) }), ` ${column.label ?? key}`),
        h('button', { type: 'button', 'aria-label': `Move ${column.label ?? key} before`, disabled: index === 0, onClick: () => moveColumn(key, -1) }, '←'),
        h('button', { type: 'button', 'aria-label': `Move ${column.label ?? key} after`, disabled: index === ordered.length - 1, onClick: () => moveColumn(key, 1) }, '→'),
        h('label', null, 'Width ', h('input', { type: 'range', min: 90, max: 480, step: 10, 'aria-label': `Width of ${column.label ?? key}`, value: widths.get(key) ?? column.width ?? 180, onChange: event => setWidths(new Map(widths).set(key, Number(event.target.value))) })));
    })),
    content,
    h('footer', null, h('span', null, 'Experimental · read only'), h('nav', { 'aria-label': 'Table pages' },
      h('button', { type: 'button', disabled: currentPage === 0, onClick: () => setPage(currentPage - 1) }, 'Previous'),
      h('span', { 'aria-live': 'polite' }, `Page ${currentPage + 1} of ${pages}`),
      h('button', { type: 'button', disabled: currentPage >= pages - 1, onClick: () => setPage(currentPage + 1) }, 'Next'))));
}
