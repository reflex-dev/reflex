const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

export function cellValue(row, key) {
  return Object.hasOwn(row, key) ? row[key] : null;
}

export function validateTable(rows, columns, rowIdKey) {
  const keys = new Set();
  for (const column of columns) {
    if (typeof column.key !== 'string' || !column.key || keys.has(column.key) || !['text', 'number'].includes(column.type ?? 'text')) {
      throw new Error('Columns need unique keys and a text or number type.');
    }
    if (column.width !== undefined && (!Number.isFinite(column.width) || column.width < 90 || column.width > 480)) {
      throw new Error('Column width must be a finite number between 90 and 480.');
    }
    keys.add(column.key);
  }
  const ids = new Set();
  for (const row of rows) {
    const id = cellValue(row, rowIdKey);
    if (!['string', 'number'].includes(typeof id) || id === '' || (typeof id === 'number' && !Number.isFinite(id)) || ids.has(String(id))) {
      throw new Error('Rows need unique nonempty string or finite number IDs.');
    }
    ids.add(String(id));
  }
}

export function deriveRows(rows, columns, query, sort) {
  const needle = query.trim().toLocaleLowerCase();
  const filtered = needle ? rows.filter(row => columns.some(column => String(cellValue(row, column.key) ?? '').toLocaleLowerCase().includes(needle))) : rows;
  if (!sort) return filtered;
  const column = columns.find(column => column.key === sort.key);
  if (!column) return filtered;
  return [...filtered].sort((a, b) => {
    const av = cellValue(a, column.key), bv = cellValue(b, column.key);
    const amissing = av == null || (column.type === 'number' && !Number.isFinite(av));
    const bmissing = bv == null || (column.type === 'number' && !Number.isFinite(bv));
    if (amissing || bmissing) return Number(amissing) - Number(bmissing);
    const compared = column.type === 'number' ? av - bv : collator.compare(String(av), String(bv));
    return sort.direction === 'asc' ? compared : -compared;
  });
}
